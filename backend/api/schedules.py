from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.deps import AuthDep
from api.schemas import ManualAssignmentUpdate, ScheduleCreate
from db.models import (
    Business,
    Employee,
    LaborRule,
    Role,
    Schedule,
    ShiftAssignment,
    ShiftSlot,
    Skill,
)
from db.session import get_db
from services.scheduling.pipeline import build_schedule
from services.scheduling.slot_generator import generate_slots_for_week
from services.scheduling.types import LaborRules, SlotSpec
from services.scheduling.validator import employee_slots_valid
from services.weeks import is_valid_week_start

router = APIRouter(prefix="/schedules", tags=["schedules"])


def _scoped_schedule(db: Session, business_id: int, schedule_id: int) -> Schedule:
    schedule = (
        db.query(Schedule).filter(Schedule.id == schedule_id, Schedule.business_id == business_id).first()
    )
    if not schedule:
        raise HTTPException(404, "Schedule not found")
    return schedule


def _schedule_summary(s: Schedule) -> dict:
    return {
        "id": s.id,
        "week_start_date": s.week_start_date.isoformat(),
        "status": s.status,
        "unfilled_slot_count": s.unfilled_slot_count,
        "generated_at": s.generated_at.isoformat() if s.generated_at else None,
        "published_at": s.published_at.isoformat() if s.published_at else None,
    }


def _schedule_detail(db: Session, schedule: Schedule) -> dict:
    slots = db.query(ShiftSlot).filter(ShiftSlot.schedule_id == schedule.id).order_by(ShiftSlot.date, ShiftSlot.start_time).all()
    slot_ids = [s.id for s in slots]
    assignments = {
        a.shift_slot_id: a
        for a in (db.query(ShiftAssignment).filter(ShiftAssignment.shift_slot_id.in_(slot_ids)) if slot_ids else [])
    }
    role_names = {r.id: r.name for r in db.query(Role).filter(Role.business_id == schedule.business_id)}
    skill_names = {sk.id: sk.name for sk in db.query(Skill).filter(Skill.business_id == schedule.business_id)}
    employee_ids = {a.employee_id for a in assignments.values() if a.employee_id is not None}
    employee_names = (
        {e.id: e.full_name for e in db.query(Employee).filter(Employee.id.in_(employee_ids))} if employee_ids else {}
    )

    slot_payload = []
    for slot in slots:
        assignment = assignments.get(slot.id)
        slot_payload.append(
            {
                "id": slot.id,
                "role_id": slot.role_id,
                "role_name": role_names.get(slot.role_id, f"role#{slot.role_id}"),
                "skill_id": slot.skill_id,
                "skill_name": skill_names.get(slot.skill_id) if slot.skill_id else None,
                "min_skill_rating": slot.min_skill_rating,
                "date": slot.date.isoformat(),
                "start_time": slot.start_time.isoformat(timespec="minutes"),
                "end_time": slot.end_time.isoformat(timespec="minutes"),
                "assignment": (
                    {
                        "employee_id": assignment.employee_id,
                        "employee_name": employee_names.get(assignment.employee_id) if assignment.employee_id else None,
                        "assigned_by": assignment.assigned_by,
                        "rationale": assignment.rationale,
                        "is_manually_edited": assignment.is_manually_edited,
                    }
                    if assignment
                    else None
                ),
            }
        )

    return {**_schedule_summary(schedule), "slots": slot_payload}


@router.get("")
def list_schedules(auth: AuthDep, db: Session = Depends(get_db)):
    schedules = (
        db.query(Schedule)
        .filter(Schedule.business_id == auth.business_id)
        .order_by(Schedule.week_start_date.desc())
        .all()
    )
    return [_schedule_summary(s) for s in schedules]


@router.post("")
def create_schedule(payload: ScheduleCreate, auth: AuthDep, db: Session = Depends(get_db)):
    business = db.query(Business).filter(Business.id == auth.business_id).first()
    if not is_valid_week_start(payload.week_start_date, business.week_start_day):
        raise HTTPException(
            422,
            f"week_start_date must fall on the business's configured week-start weekday "
            f"(weekday={business.week_start_day})",
        )

    schedule = Schedule(
        business_id=auth.business_id,
        week_start_date=payload.week_start_date,
        status="draft",
        created_by_user_id=auth.user_id,
    )
    db.add(schedule)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A schedule already exists for this week")

    generate_slots_for_week(db, auth.business_id, schedule.id, payload.week_start_date)
    db.commit()
    db.refresh(schedule)
    return _schedule_detail(db, schedule)


@router.get("/{schedule_id}")
def get_schedule(schedule_id: int, auth: AuthDep, db: Session = Depends(get_db)):
    schedule = _scoped_schedule(db, auth.business_id, schedule_id)
    return _schedule_detail(db, schedule)


@router.post("/{schedule_id}/build")
def build_schedule_endpoint(schedule_id: int, auth: AuthDep, db: Session = Depends(get_db)):
    schedule = _scoped_schedule(db, auth.business_id, schedule_id)
    if schedule.status == "published":
        raise HTTPException(409, "Cannot rebuild a published schedule")
    build_schedule(db, schedule)
    return _schedule_detail(db, schedule)


@router.patch("/{schedule_id}/assignments/{slot_id}")
def update_assignment(
    schedule_id: int,
    slot_id: int,
    payload: ManualAssignmentUpdate,
    auth: AuthDep,
    db: Session = Depends(get_db),
):
    schedule = _scoped_schedule(db, auth.business_id, schedule_id)
    if schedule.status == "published":
        raise HTTPException(409, "Cannot edit a published schedule")

    slot = db.query(ShiftSlot).filter(ShiftSlot.id == slot_id, ShiftSlot.schedule_id == schedule.id).first()
    if not slot:
        raise HTTPException(404, "Slot not found")

    if payload.employee_id is not None:
        employee = (
            db.query(Employee)
            .filter(Employee.id == payload.employee_id, Employee.business_id == auth.business_id, Employee.is_active.is_(True))
            .first()
        )
        if not employee:
            raise HTTPException(422, "Unknown or inactive employee_id")

        rule = db.query(LaborRule).filter(LaborRule.business_id == auth.business_id).first()
        labor_rules = LaborRules(
            weekly_overtime_threshold_hours=rule.weekly_overtime_threshold_hours,
            min_rest_hours_between_shifts=rule.min_rest_hours_between_shifts,
        )

        other_assignments = (
            db.query(ShiftAssignment, ShiftSlot)
            .join(ShiftSlot, ShiftSlot.id == ShiftAssignment.shift_slot_id)
            .filter(
                ShiftSlot.schedule_id == schedule.id,
                ShiftAssignment.employee_id == payload.employee_id,
                ShiftSlot.id != slot_id,
            )
            .all()
        )
        emp_slots = [
            SlotSpec(id=s.id, role_id=s.role_id, date=s.date, start_time=s.start_time, end_time=s.end_time)
            for _a, s in other_assignments
        ] + [SlotSpec(id=slot.id, role_id=slot.role_id, date=slot.date, start_time=slot.start_time, end_time=slot.end_time)]

        if not employee_slots_valid(emp_slots, labor_rules, schedule.week_start_date):
            raise HTTPException(
                409, "This assignment would violate a hard constraint (overlap, minimum rest, or weekly overtime cap)"
            )

    assignment = db.query(ShiftAssignment).filter(ShiftAssignment.shift_slot_id == slot_id).first()
    if assignment:
        assignment.employee_id = payload.employee_id
        assignment.assigned_by = "manager_manual"
        assignment.rationale = None
        assignment.is_manually_edited = True
    else:
        db.add(
            ShiftAssignment(
                shift_slot_id=slot_id,
                employee_id=payload.employee_id,
                assigned_by="manager_manual",
                is_manually_edited=True,
            )
        )

    db.flush()
    unfilled = (
        db.query(ShiftSlot)
        .outerjoin(ShiftAssignment, ShiftAssignment.shift_slot_id == ShiftSlot.id)
        .filter(ShiftSlot.schedule_id == schedule.id)
        .filter((ShiftAssignment.employee_id.is_(None)) | (ShiftAssignment.id.is_(None)))
        .count()
    )
    schedule.unfilled_slot_count = unfilled
    db.commit()
    return _schedule_detail(db, schedule)
