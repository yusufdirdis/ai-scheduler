"""Orchestrates: load DB state -> solve (hard constraints) -> LLM rank (soft
preferences) -> global re-validate -> persist. The solver's baseline is always the
fallback of last resort; nothing the LLM returns is trusted until re-validated."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from db.models import (
    AvailabilitySlot,
    AvailabilitySubmission,
    Employee,
    EmployeeRole,
    EmployeeSkillRating,
    LaborRule,
    ManagerNote,
    Role,
    Schedule,
    ShiftAssignment,
    ShiftSlot,
    Skill,
)
from services.ai_client import AIClient

from .ranker import CandidateInfo, RankingJob, rank_schedule
from .solver import compute_candidates, solve_baseline
from .types import AvailabilityWindow, EmployeeSpec, LaborRules, SlotSpec
from .validator import apply_proposed_assignments

logger = logging.getLogger(__name__)

MAX_NOTES_PER_CANDIDATE = 5


def _load_slots(db: Session, schedule_id: int) -> list[SlotSpec]:
    rows = db.query(ShiftSlot).filter(ShiftSlot.schedule_id == schedule_id).all()
    return [
        SlotSpec(
            id=r.id,
            role_id=r.role_id,
            date=r.date,
            start_time=r.start_time,
            end_time=r.end_time,
            skill_id=r.skill_id,
            min_skill_rating=r.min_skill_rating,
        )
        for r in rows
    ]


def _load_employee_specs(db: Session, business_id: int, week_start_date) -> list[EmployeeSpec]:
    employees = (
        db.query(Employee).filter(Employee.business_id == business_id, Employee.is_active.is_(True)).all()
    )
    if not employees:
        return []
    employee_ids = [e.id for e in employees]

    role_ids_by_employee: dict[int, set[int]] = {eid: set() for eid in employee_ids}
    for er in db.query(EmployeeRole).filter(EmployeeRole.employee_id.in_(employee_ids)):
        role_ids_by_employee[er.employee_id].add(er.role_id)

    ratings_by_employee: dict[int, dict[int, int]] = {eid: {} for eid in employee_ids}
    for r in db.query(EmployeeSkillRating).filter(EmployeeSkillRating.employee_id.in_(employee_ids)):
        ratings_by_employee[r.employee_id][r.skill_id] = r.rating

    submissions = (
        db.query(AvailabilitySubmission)
        .filter(
            AvailabilitySubmission.employee_id.in_(employee_ids),
            AvailabilitySubmission.week_start_date == week_start_date,
        )
        .all()
    )
    submission_ids_by_employee = {s.employee_id: s.id for s in submissions}
    availability_by_employee: dict[int, list[AvailabilityWindow]] = {eid: [] for eid in employee_ids}
    if submission_ids_by_employee:
        slots = (
            db.query(AvailabilitySlot)
            .filter(
                AvailabilitySlot.availability_submission_id.in_(submission_ids_by_employee.values()),
                AvailabilitySlot.is_available.is_(True),
            )
            .all()
        )
        submission_to_employee = {sid: eid for eid, sid in submission_ids_by_employee.items()}
        for s in slots:
            eid = submission_to_employee[s.availability_submission_id]
            availability_by_employee[eid].append(
                AvailabilityWindow(date=s.date, start_time=s.start_time, end_time=s.end_time)
            )

    return [
        EmployeeSpec(
            id=e.id,
            role_ids=frozenset(role_ids_by_employee[e.id]),
            skill_ratings=ratings_by_employee[e.id],
            availability=tuple(availability_by_employee[e.id]),
        )
        for e in employees
    ]


def _load_labor_rules(db: Session, business_id: int) -> LaborRules:
    rule = db.query(LaborRule).filter(LaborRule.business_id == business_id).first()
    return LaborRules(
        weekly_overtime_threshold_hours=rule.weekly_overtime_threshold_hours,
        min_rest_hours_between_shifts=rule.min_rest_hours_between_shifts,
    )


def _build_candidate_info_map(db: Session, business_id: int, employee_ids: set[int]) -> dict[int, CandidateInfo]:
    employees = db.query(Employee).filter(Employee.id.in_(employee_ids)).all() if employee_ids else []

    skill_names = {s.id: s.name for s in db.query(Skill).filter(Skill.business_id == business_id)}
    ratings_by_employee: dict[int, dict[str, int]] = {eid: {} for eid in employee_ids}
    for r in db.query(EmployeeSkillRating).filter(EmployeeSkillRating.employee_id.in_(employee_ids)):
        name = skill_names.get(r.skill_id, f"skill#{r.skill_id}")
        ratings_by_employee[r.employee_id][name] = r.rating

    notes_by_employee: dict[int, list[str]] = {eid: [] for eid in employee_ids}
    if employee_ids:
        notes = (
            db.query(ManagerNote)
            .filter(ManagerNote.employee_id.in_(employee_ids), ManagerNote.is_active.is_(True))
            .order_by(ManagerNote.created_at.desc())
            .all()
        )
        for n in notes:
            if len(notes_by_employee[n.employee_id]) < MAX_NOTES_PER_CANDIDATE:
                notes_by_employee[n.employee_id].append(n.note_text)

    return {
        e.id: CandidateInfo(
            employee_id=e.id,
            full_name=e.full_name,
            skill_ratings=ratings_by_employee.get(e.id, {}),
            reliability_score=e.reliability_score,
            manager_notes=tuple(notes_by_employee.get(e.id, [])),
        )
        for e in employees
    }


def build_schedule(db: Session, schedule: Schedule) -> Schedule:
    slots = _load_slots(db, schedule.id)
    employees = _load_employee_specs(db, schedule.business_id, schedule.week_start_date)
    labor_rules = _load_labor_rules(db, schedule.business_id)

    result = solve_baseline(slots, employees, labor_rules, schedule.week_start_date)
    candidates_map = compute_candidates(result, slots, labor_rules, schedule.week_start_date)

    role_names = {r.id: r.name for r in db.query(Role).filter(Role.business_id == schedule.business_id)}
    candidate_employee_ids = {eid for opts in candidates_map.values() for eid in opts}
    candidate_info_map = _build_candidate_info_map(db, schedule.business_id, candidate_employee_ids)

    jobs = []
    slots_by_id = {s.id: s for s in slots}
    for slot_id, candidate_ids in candidates_map.items():
        slot = slots_by_id[slot_id]
        jobs.append(
            RankingJob(
                slot_id=slot_id,
                role_name=role_names.get(slot.role_id, f"role#{slot.role_id}"),
                date=slot.date.isoformat(),
                start_time=slot.start_time.isoformat(timespec="minutes"),
                end_time=slot.end_time.isoformat(timespec="minutes"),
                candidates=tuple(candidate_info_map[eid] for eid in candidate_ids if eid in candidate_info_map),
            )
        )

    ai_client = AIClient()
    outcomes = rank_schedule(ai_client, jobs)

    proposed = {slot_id: outcome.employee_id for slot_id, outcome in outcomes.items()}
    final_assignments, reverted_slot_ids = apply_proposed_assignments(
        result.assignments, proposed, slots_by_id, labor_rules, schedule.week_start_date
    )
    if reverted_slot_ids:
        logger.info("Schedule %s: reverted %d LLM swap(s) that failed global re-validation", schedule.id, len(reverted_slot_ids))

    existing_assignments = {
        a.shift_slot_id: a
        for a in db.query(ShiftAssignment).filter(ShiftAssignment.shift_slot_id.in_(list(slots_by_id.keys())))
    }

    for slot_id, employee_id in final_assignments.items():
        baseline_employee_id = result.assignments[slot_id]
        outcome = outcomes.get(slot_id)
        if employee_id == baseline_employee_id:
            assigned_by = "solver"
            if outcome is None:
                rationale = None
            elif slot_id in reverted_slot_ids:
                rationale = (
                    f"AI suggested a swap ({outcome.rationale}), but it would have violated a hard "
                    "constraint once combined with other picks — kept the solver's baseline instead."
                )
            else:
                rationale = outcome.rationale
        else:
            assigned_by = "llm"
            rationale = outcome.rationale if outcome else None

        existing = existing_assignments.get(slot_id)
        if existing:
            existing.employee_id = employee_id
            existing.assigned_by = assigned_by
            existing.rationale = rationale
            existing.is_manually_edited = False
        else:
            db.add(
                ShiftAssignment(
                    shift_slot_id=slot_id,
                    employee_id=employee_id,
                    assigned_by=assigned_by,
                    rationale=rationale,
                    is_manually_edited=False,
                )
            )

    schedule.status = "ai_generated"
    schedule.generated_at = datetime.now(timezone.utc)
    schedule.unfilled_slot_count = sum(1 for e in final_assignments.values() if e is None)

    db.commit()
    db.refresh(schedule)
    return schedule
