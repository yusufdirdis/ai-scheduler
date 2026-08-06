"""Hard-constraint baseline solver (OR-Tools CP-SAT). Coverage-maximizing only —
no preference weighting here, that's the LLM ranker's job on top of this baseline."""
from __future__ import annotations

from datetime import date as date_type

from ortools.sat.python import cp_model

from .timeutil import duration_minutes, to_minutes, window_covers_slot
from .types import EmployeeSpec, LaborRules, SlotSpec, SolverResult
from .validator import employee_slots_valid


def compute_eligibility(slots: list[SlotSpec], employees: list[EmployeeSpec]) -> dict[int, list[int]]:
    """A slot's eligible employees: hold the required role, meet any hard skill/cert
    floor, and have submitted availability that fully covers the shift window."""
    eligible: dict[int, list[int]] = {}
    for slot in slots:
        elig = []
        for emp in employees:
            if slot.role_id not in emp.role_ids:
                continue
            if slot.skill_id is not None:
                rating = emp.skill_ratings.get(slot.skill_id, 0)
                if rating < (slot.min_skill_rating or 1):
                    continue
            if not any(window_covers_slot(w.date, w.start_time, w.end_time, slot) for w in emp.availability):
                continue
            elig.append(emp.id)
        eligible[slot.id] = elig
    return eligible


def solve_baseline(
    slots: list[SlotSpec],
    employees: list[EmployeeSpec],
    labor_rules: LaborRules,
    week_start_date: date_type,
    time_limit_seconds: float = 10.0,
) -> SolverResult:
    eligible = compute_eligibility(slots, employees)
    slots_by_id = {s.id: s for s in slots}

    model = cp_model.CpModel()
    x: dict[tuple[int, int], cp_model.IntVar] = {}
    for slot in slots:
        for emp_id in eligible[slot.id]:
            x[(slot.id, emp_id)] = model.new_bool_var(f"x_s{slot.id}_e{emp_id}")

    # At most one assignee per slot (a slot with no eligible employees just has no
    # variables at all — vacuously satisfied, surfaced separately as "structurally unfilled").
    for slot in slots:
        vars_for_slot = [x[(slot.id, emp_id)] for emp_id in eligible[slot.id]]
        if vars_for_slot:
            model.add(sum(vars_for_slot) <= 1)

    rest_minutes = round(labor_rules.min_rest_hours_between_shifts * 60)
    ot_minutes = round(labor_rules.weekly_overtime_threshold_hours * 60)

    for emp in employees:
        emp_slot_ids = [s.id for s in slots if emp.id in eligible[s.id]]
        if not emp_slot_ids:
            continue

        # No-overlap + minimum rest in one constraint: pad each optional interval's end
        # by the rest buffer for the overlap check only (the buffer isn't part of the
        # persisted shift time) — AddNoOverlap then guarantees any two shifts this
        # employee is assigned both respect the gap.
        intervals = []
        for slot_id in emp_slot_ids:
            slot = slots_by_id[slot_id]
            start = to_minutes(slot.date, slot.start_time, week_start_date)
            padded_duration = duration_minutes(slot) + rest_minutes
            intervals.append(
                model.new_optional_interval_var(
                    start, padded_duration, start + padded_duration, x[(slot_id, emp.id)], f"iv_s{slot_id}_e{emp.id}"
                )
            )
        model.add_no_overlap(intervals)

        # Weekly overtime cap.
        duration_terms = [x[(slot_id, emp.id)] * duration_minutes(slots_by_id[slot_id]) for slot_id in emp_slot_ids]
        model.add(sum(duration_terms) <= ot_minutes)

    model.maximize(sum(x.values()) if x else 0)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_seconds
    status = solver.solve(model)

    assignments: dict[int, int | None] = {slot.id: None for slot in slots}
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        for (slot_id, emp_id), var in x.items():
            if solver.value(var) == 1:
                assignments[slot_id] = emp_id

    structurally_unfilled = [slot.id for slot in slots if not eligible[slot.id]]
    return SolverResult(assignments=assignments, eligible=eligible, structurally_unfilled_slot_ids=structurally_unfilled)


def compute_candidates(
    result: SolverResult,
    slots: list[SlotSpec],
    labor_rules: LaborRules,
    week_start_date,
) -> dict[int, list[int]]:
    """For each filled slot, the baseline assignee plus other eligible employees who
    could swap in without breaking their own schedule (cheap per-slot check against the
    baseline, not a re-solve). Candidate lists always start with the baseline assignee —
    that's what makes it the ranker's natural fallback."""
    slots_by_id = {s.id: s for s in slots}
    assignments_by_employee: dict[int, list[int]] = {}
    for slot_id, emp_id in result.assignments.items():
        if emp_id is not None:
            assignments_by_employee.setdefault(emp_id, []).append(slot_id)

    candidates: dict[int, list[int]] = {}
    for slot in slots:
        baseline_emp = result.assignments[slot.id]
        if baseline_emp is None:
            continue
        options = [baseline_emp]
        for alt_emp in result.eligible[slot.id]:
            if alt_emp == baseline_emp:
                continue
            alt_current_slot_ids = assignments_by_employee.get(alt_emp, [])
            trial_slots = [slots_by_id[sid] for sid in alt_current_slot_ids] + [slot]
            if employee_slots_valid(trial_slots, labor_rules, week_start_date):
                options.append(alt_emp)
        candidates[slot.id] = options
    return candidates
