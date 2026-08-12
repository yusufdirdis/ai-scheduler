from __future__ import annotations

from datetime import date as date_type
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from api.deps import AuthDep
from api.schemas import AvailabilityEntryIn
from db.models import AvailabilitySlot, AvailabilitySubmission, Business, Employee
from db.session import SessionLocal, get_db
from jobs.tasks import trigger_availability_request_now
from services.weeks import is_valid_week_start

router = APIRouter(prefix="/availability", tags=["availability"])


def _require_valid_week_start(db: Session, business_id: int, week_start_date: date_type) -> None:
    business = db.query(Business).filter(Business.id == business_id).first()
    if not is_valid_week_start(week_start_date, business.week_start_day):
        raise HTTPException(
            422,
            f"week_start_date must fall on the business's configured week-start weekday "
            f"(weekday={business.week_start_day})",
        )


def _scoped_employee(db: Session, business_id: int, employee_id: int) -> Employee:
    employee = (
        db.query(Employee)
        .filter(Employee.id == employee_id, Employee.business_id == business_id)
        .first()
    )
    if not employee:
        raise HTTPException(404, "Employee not found")
    return employee


@router.get("/status")
def get_availability_status(
    auth: AuthDep,
    week_start_date: date_type = Query(...),
    db: Session = Depends(get_db),
):
    _require_valid_week_start(db, auth.business_id, week_start_date)

    employees = (
        db.query(Employee)
        .filter(Employee.business_id == auth.business_id, Employee.is_active.is_(True))
        .order_by(Employee.full_name)
        .all()
    )
    submissions = {
        s.employee_id: s
        for s in db.query(AvailabilitySubmission).filter(
            AvailabilitySubmission.business_id == auth.business_id,
            AvailabilitySubmission.week_start_date == week_start_date,
        )
    }
    submission_ids = [s.id for s in submissions.values()]
    slot_counts: dict[int, int] = {}
    if submission_ids:
        for sub_id, _slot_id in (
            db.query(AvailabilitySlot.availability_submission_id, AvailabilitySlot.id)
            .filter(AvailabilitySlot.availability_submission_id.in_(submission_ids))
            .all()
        ):
            slot_counts[sub_id] = slot_counts.get(sub_id, 0) + 1

    result = []
    for emp in employees:
        sub = submissions.get(emp.id)
        result.append(
            {
                "employee_id": emp.id,
                "full_name": emp.full_name,
                "status": sub.status if sub else "pending",
                "submitted_at": sub.submitted_at.isoformat() if sub and sub.submitted_at else None,
                "slot_count": slot_counts.get(sub.id, 0) if sub else 0,
            }
        )
    return result


@router.get("/{employee_id}")
def get_employee_availability(
    employee_id: int,
    auth: AuthDep,
    week_start_date: date_type = Query(...),
    db: Session = Depends(get_db),
):
    _require_valid_week_start(db, auth.business_id, week_start_date)
    _scoped_employee(db, auth.business_id, employee_id)

    sub = (
        db.query(AvailabilitySubmission)
        .filter(
            AvailabilitySubmission.employee_id == employee_id,
            AvailabilitySubmission.week_start_date == week_start_date,
        )
        .first()
    )
    if not sub:
        return {"status": "pending", "submitted_at": None, "slots": []}

    slots = (
        db.query(AvailabilitySlot)
        .filter(AvailabilitySlot.availability_submission_id == sub.id)
        .order_by(AvailabilitySlot.date, AvailabilitySlot.start_time)
        .all()
    )
    return {
        "status": sub.status,
        "submitted_at": sub.submitted_at.isoformat() if sub.submitted_at else None,
        "slots": [
            {
                "date": s.date.isoformat(),
                "start_time": s.start_time.isoformat(timespec="minutes"),
                "end_time": s.end_time.isoformat(timespec="minutes"),
            }
            for s in slots
            if s.is_available
        ],
    }


@router.put("/{employee_id}")
def set_employee_availability(
    employee_id: int,
    payload: AvailabilityEntryIn,
    auth: AuthDep,
    week_start_date: date_type = Query(...),
    db: Session = Depends(get_db),
):
    _require_valid_week_start(db, auth.business_id, week_start_date)
    _scoped_employee(db, auth.business_id, employee_id)

    week_end = week_start_date + timedelta(days=6)
    for slot in payload.slots:
        if not (week_start_date <= slot.date <= week_end):
            raise HTTPException(
                422, f"slot date {slot.date} falls outside the selected week ({week_start_date}–{week_end})"
            )

    sub = (
        db.query(AvailabilitySubmission)
        .filter(
            AvailabilitySubmission.employee_id == employee_id,
            AvailabilitySubmission.week_start_date == week_start_date,
        )
        .first()
    )
    if not sub:
        sub = AvailabilitySubmission(
            business_id=auth.business_id,
            employee_id=employee_id,
            week_start_date=week_start_date,
        )
        db.add(sub)
        db.flush()

    sub.status = "manual_entry"
    sub.submitted_at = datetime.now(timezone.utc)
    sub.raw_sms_text = None
    sub.parse_confidence = None

    db.query(AvailabilitySlot).filter(AvailabilitySlot.availability_submission_id == sub.id).delete(
        synchronize_session=False
    )
    for slot in payload.slots:
        db.add(
            AvailabilitySlot(
                availability_submission_id=sub.id,
                date=slot.date,
                start_time=slot.start_time,
                end_time=slot.end_time,
                is_available=True,
            )
        )

    db.commit()
    return get_employee_availability(employee_id, auth, week_start_date, db)


def _run_request_now_task(business_id: int) -> None:
    """Runs after the HTTP response has already been sent — opens its own DB
    session since the request's session is closed by then."""
    db = SessionLocal()
    try:
        trigger_availability_request_now(db, business_id)
    finally:
        db.close()


@router.post("/request-now")
def request_availability_now(auth: AuthDep, background_tasks: BackgroundTasks):
    """Ad-hoc trigger for the manager's 'Request availability now' button — fires
    the same eligibility logic as the weekly job (skip anyone who already
    answered), for every active employee, regardless of the configured day/time."""
    background_tasks.add_task(_run_request_now_task, auth.business_id)
    return {"status": "queued"}
