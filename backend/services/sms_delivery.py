"""
SMS delivery — the single seam between "we decided to send a text" and "a message
actually left the building" (mirrors the pattern in ai-pos's crm_delivery.py), so
Twilio specifics stay isolated from callers in the API layer.
"""
from __future__ import annotations

import logging
from datetime import date

from sqlalchemy.orm import Session

from db.models import Business, Employee, SmsMessage
from integrations.twilio_client import send_sms

logger = logging.getLogger("ai_scheduler.sms_delivery")


def _deliver(
    db: Session,
    business_id: int,
    employee: Employee,
    message_type: str,
    body: str,
    related_schedule_id: int | None = None,
    related_availability_submission_id: int | None = None,
) -> SmsMessage:
    msg = SmsMessage(
        business_id=business_id,
        employee_id=employee.id,
        direction="outbound",
        phone_number=employee.phone_number,
        message_type=message_type,
        body_text=body,
        status="queued",
        related_schedule_id=related_schedule_id,
        related_availability_submission_id=related_availability_submission_id,
    )
    db.add(msg)
    db.flush()

    try:
        sid = send_sms(employee.phone_number, body)
        msg.twilio_sid = sid
        msg.status = "sent"
    except Exception as e:
        logger.error("SMS send failed for employee %s: %s", employee.id, e)
        msg.status = "failed"
        msg.error_message = str(e)

    db.commit()
    return msg


def send_availability_request(
    db: Session,
    business_id: int,
    employee: Employee,
    week_start_date: date,
    submission_id: int | None = None,
) -> SmsMessage:
    first_name = employee.full_name.split()[0] if employee.full_name else "there"
    week_label = week_start_date.strftime("%b %d")
    body = (
        f"Hi {first_name}, what's your availability for the week of {week_label}? "
        "Reply with your available days and times. Reply STOP to opt out."
    )
    return _deliver(
        db, business_id, employee, "availability_request", body,
        related_availability_submission_id=submission_id,
    )


def send_enrollment_confirmation(db: Session, business_id: int, employee: Employee) -> SmsMessage:
    """Sent the moment a manager adds an employee — the text-based confirmation
    half of a verbal + text double opt-in. Verbal consent alone is the hardest
    opt-in method to get through A2P 10DLC campaign review because there's
    nothing external to check; this message is what actually gives a reviewer
    (and the employee) a real, Twilio-logged record that consent happened and
    what they signed up for, restating message types/frequency/rates/opt-out
    right in the first text they ever receive."""
    business = db.query(Business).filter(Business.id == business_id).first()
    business_name = business.name if business else "your employer"
    first_name = employee.full_name.split()[0] if employee.full_name else "there"
    body = (
        f"Hi {first_name}, you've been added to {business_name}'s text scheduling alerts. "
        "You'll get texts about your work availability and schedule, about 2-4 msgs/week. "
        "Msg&data rates may apply. Reply STOP to opt out, HELP for help."
    )
    return _deliver(db, business_id, employee, "enrollment_confirmation", body)
