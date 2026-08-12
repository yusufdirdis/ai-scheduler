"""
Inbound SMS from employees. Twilio POSTs form-encoded fields to this endpoint —
every request must carry a valid X-Twilio-Signature or it's rejected outright.

Employees are matched purely by phone number (globally unique — see
Employee.phone_number), not scoped by business, since all businesses currently
share one platform Twilio number (see db/models.py's note on Business.twilio_phone_number).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import Response

from core.config import settings
from db.models import AvailabilitySlot, AvailabilitySubmission, Business, Employee, SmsMessage
from db.session import SessionLocal
from integrations.twilio_client import validate_webhook_signature
from services.ai_client import AIClient
from services.availability_parser import parse_availability_reply
from services.phone import normalize_phone_number
from services.weeks import week_start_on_or_before

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks/twilio", tags=["webhooks"])

_EMPTY_TWIML = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'


def _twiml_response(status_code: int = 200) -> Response:
    return Response(content=_EMPTY_TWIML, media_type="application/xml", status_code=status_code)


@router.post("/inbound")
async def inbound_sms(request: Request):
    form = await request.form()
    params = {k: str(v) for k, v in form.items()}
    signature = request.headers.get("X-Twilio-Signature")
    public_url = f"{settings.PUBLIC_API_URL.rstrip('/')}/api/webhooks/twilio/inbound"

    if not validate_webhook_signature(public_url, params, signature):
        logger.warning("Rejected inbound SMS webhook: invalid signature")
        return _twiml_response(status_code=403)

    try:
        from_number = normalize_phone_number(params.get("From", ""))
    except ValueError:
        from_number = None
    body_text = params.get("Body", "")
    message_sid = params.get("MessageSid")
    # Present when Advanced Opt-Out is enabled on the Messaging Service (it is, per our
    # A2P registration) — Twilio still forwards STOP/START/HELP here for our audit log,
    # but has already handled suppressing/resuming future sends and the auto-reply itself.
    opt_out_type = params.get("OptOutType")

    db = SessionLocal()
    try:
        employee = (
            db.query(Employee).filter(Employee.phone_number == from_number).first() if from_number else None
        )

        if not employee:
            logger.warning("Inbound SMS from unrecognized number %s — dropping", from_number)
            return _twiml_response()

        if opt_out_type:
            # Twilio already handled the actual opt-out/opt-in mechanics and sent its own
            # confirmation reply — just log it, and explicitly do NOT run this through the
            # availability parser (a "STOP" reply is not an availability answer).
            db.add(
                SmsMessage(
                    business_id=employee.business_id,
                    employee_id=employee.id,
                    direction="inbound",
                    phone_number=from_number,
                    twilio_sid=message_sid,
                    message_type=f"opt_{opt_out_type.lower()}",
                    body_text=body_text,
                    status="received",
                )
            )
            db.commit()
            return _twiml_response()

        business = db.query(Business).filter(Business.id == employee.business_id).first()
        today = datetime.now(timezone.utc).date()
        week_start = week_start_on_or_before(today, business.week_start_day)

        submission = (
            db.query(AvailabilitySubmission)
            .filter(
                AvailabilitySubmission.employee_id == employee.id,
                AvailabilitySubmission.week_start_date == week_start,
            )
            .first()
        )
        if not submission:
            submission = AvailabilitySubmission(
                business_id=employee.business_id,
                employee_id=employee.id,
                week_start_date=week_start,
            )
            db.add(submission)
            db.flush()

        submission.raw_sms_text = body_text
        submission.submitted_at = datetime.now(timezone.utc)

        parsed = parse_availability_reply(AIClient(), week_start, body_text)

        db.query(AvailabilitySlot).filter(
            AvailabilitySlot.availability_submission_id == submission.id
        ).delete(synchronize_session=False)
        for slot in parsed.slots:
            db.add(
                AvailabilitySlot(
                    availability_submission_id=submission.id,
                    date=slot.date,
                    start_time=slot.start_time,
                    end_time=slot.end_time,
                    is_available=True,
                )
            )

        submission.parse_confidence = parsed.confidence
        submission.status = "submitted" if (parsed.slots and parsed.confidence >= 0.5) else "parse_failed"

        db.add(
            SmsMessage(
                business_id=employee.business_id,
                employee_id=employee.id,
                direction="inbound",
                phone_number=from_number,
                twilio_sid=message_sid,
                message_type="availability_reply",
                body_text=body_text,
                status="received",
                related_availability_submission_id=submission.id,
            )
        )

        db.commit()
    finally:
        db.close()

    return _twiml_response()
