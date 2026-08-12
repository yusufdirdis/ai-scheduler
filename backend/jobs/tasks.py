"""Availability-request orchestration: the weekly automated trigger, the manager's
ad-hoc 'request now' button, and the one-time non-responder reminder."""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session

from db.models import AvailabilitySubmission, Business, Employee, SmsMessage
from db.session import SessionLocal
from jobs.timing import is_request_due
from services.sms_delivery import send_availability_request
from services.weeks import week_start_on_or_before

logger = logging.getLogger(__name__)

REMINDER_DELAY_HOURS = 24.0
NO_RESPONSE_AFTER_HOURS = 72.0


def _next_target_week(business: Business, today: date) -> date:
    """The week we're collecting availability FOR — one week out from the current
    week, so employees have advance notice before a schedule gets built."""
    this_week = week_start_on_or_before(today, business.week_start_day)
    return this_week + timedelta(days=7)


def _request_count(db: Session, submission_id: int) -> int:
    return (
        db.query(SmsMessage)
        .filter(
            SmsMessage.related_availability_submission_id == submission_id,
            SmsMessage.message_type == "availability_request",
            SmsMessage.direction == "outbound",
        )
        .count()
    )


def _send_initial_request_for_employee(db: Session, business: Business, employee: Employee, target_week) -> bool:
    """Weekly-job path: strictly idempotent — skipped if ANY submission already
    exists for this employee+week, pending or otherwise. This is what makes a
    tick firing twice in the same hour (or overlapping with an ad-hoc request)
    safe: the initial request only ever goes out once per employee per week."""
    existing = (
        db.query(AvailabilitySubmission)
        .filter(
            AvailabilitySubmission.employee_id == employee.id,
            AvailabilitySubmission.week_start_date == target_week,
        )
        .first()
    )
    if existing:
        return False

    submission = AvailabilitySubmission(
        business_id=business.id,
        employee_id=employee.id,
        week_start_date=target_week,
        requested_at=datetime.now(timezone.utc),
        status="pending",
    )
    db.add(submission)
    db.flush()
    send_availability_request(db, business.id, employee, target_week, submission_id=submission.id)
    return True


def _send_adhoc_request_for_employee(db: Session, business: Business, employee: Employee, target_week) -> bool:
    """'Request now' path: allowed to (re-)send even if a submission is already
    pending — the manager is explicitly asking to nudge. Still skipped if the
    employee already answered (a terminal status), since there's nothing left
    to ask."""
    submission = (
        db.query(AvailabilitySubmission)
        .filter(
            AvailabilitySubmission.employee_id == employee.id,
            AvailabilitySubmission.week_start_date == target_week,
        )
        .first()
    )
    if submission and submission.status != "pending":
        return False  # already submitted/manual_entry/parse_failed/no_response

    if not submission:
        submission = AvailabilitySubmission(
            business_id=business.id,
            employee_id=employee.id,
            week_start_date=target_week,
            requested_at=datetime.now(timezone.utc),
            status="pending",
        )
        db.add(submission)
        db.flush()

    send_availability_request(db, business.id, employee, target_week, submission_id=submission.id)
    return True


def run_weekly_availability_requests(db: Session, now_utc: datetime) -> dict:
    """Hourly-tick entry point: for every active business whose configured
    request day/time matches now (in the business's own timezone), send the
    initial availability request for next week to every active employee who
    doesn't already have one. Naturally idempotent — an employee who already
    has a submission for the target week (pending or otherwise) is skipped, so
    a tick firing twice in the same hour, or a manual 'request now' having
    already covered someone, never double-sends.
    """
    sent = 0
    businesses = db.query(Business).filter(Business.is_active.is_(True)).all()
    for business in businesses:
        try:
            due = is_request_due(
                business.timezone, business.availability_request_day_of_week, business.availability_request_time, now_utc
            )
        except Exception as e:
            # A bad business.timezone (e.g. hand-typed, not a real IANA zone) must
            # never take down the tick for every other business.
            logger.error("Skipping business %s in availability tick — bad schedule config: %s", business.id, e)
            continue
        if not due:
            continue

        target_week = _next_target_week(business, now_utc.date())
        employees = db.query(Employee).filter(Employee.business_id == business.id, Employee.is_active.is_(True)).all()
        for employee in employees:
            if _send_initial_request_for_employee(db, business, employee, target_week):
                sent += 1

    db.commit()
    logger.info("Weekly availability request tick: sent %d message(s)", sent)
    return {"sent": sent}


def trigger_availability_request_now(db: Session, business_id: int) -> dict:
    """Manager-initiated ad-hoc trigger — allowed to nudge employees who are
    already pending (unlike the weekly job), but still skips anyone who already
    answered. Ignores the day/time window entirely."""
    business = db.query(Business).filter(Business.id == business_id).first()
    if not business:
        return {"sent": 0}

    target_week = _next_target_week(business, datetime.now(timezone.utc).date())
    sent = 0
    employees = db.query(Employee).filter(Employee.business_id == business.id, Employee.is_active.is_(True)).all()
    for employee in employees:
        if _send_adhoc_request_for_employee(db, business, employee, target_week):
            sent += 1

    db.commit()
    logger.info("Ad-hoc availability request for business %s: sent %d message(s)", business_id, sent)
    return {"sent": sent}


def run_availability_reminders(db: Session, now_utc: datetime) -> dict:
    """One-time re-ping for non-responders: submissions still 'pending'
    REMINDER_DELAY_HOURS after the original request get exactly one reminder
    text (guarded by _request_count == 1, so this can never fire twice), and
    submissions still pending NO_RESPONSE_AFTER_HOURS after that get marked
    'no_response' so the manager's status grid reflects reality instead of a
    perpetual 'pending'.
    """
    reminded = 0
    marked_no_response = 0

    pending = db.query(AvailabilitySubmission).filter(AvailabilitySubmission.status == "pending").all()
    for submission in pending:
        if not submission.requested_at:
            continue
        age_hours = (now_utc - submission.requested_at).total_seconds() / 3600
        request_count = _request_count(db, submission.id)

        if request_count >= 2 and age_hours >= NO_RESPONSE_AFTER_HOURS:
            submission.status = "no_response"
            marked_no_response += 1
            continue

        if request_count == 1 and age_hours >= REMINDER_DELAY_HOURS:
            employee = db.query(Employee).filter(Employee.id == submission.employee_id).first()
            business = db.query(Business).filter(Business.id == submission.business_id).first()
            if employee and employee.is_active and business:
                send_availability_request(
                    db, business.id, employee, submission.week_start_date, submission_id=submission.id
                )
                reminded += 1

    db.commit()
    logger.info(
        "Availability reminder tick: reminded %d, marked %d as no_response", reminded, marked_no_response
    )
    return {"reminded": reminded, "no_response": marked_no_response}


def run_scheduled_tick() -> None:
    """Entry point called by APScheduler — owns its own DB session since it runs
    outside any request context."""
    db = SessionLocal()
    try:
        now_utc = datetime.now(timezone.utc)
        run_weekly_availability_requests(db, now_utc)
        run_availability_reminders(db, now_utc)
    finally:
        db.close()
