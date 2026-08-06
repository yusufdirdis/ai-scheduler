"""Hard-constraint validation, shared by the AI pipeline's re-validation step and
manual manager reassignment — the one place 'is this schedule allowed' is decided."""
from __future__ import annotations

from datetime import date as date_type

from .timeutil import duration_minutes, to_minutes
from .types import LaborRules, SlotSpec


def employee_slots_valid(
    emp_slots: list[SlotSpec], labor_rules: LaborRules, week_start_date: date_type
) -> bool:
    """True if this set of slots, all assigned to one employee, violates no hard rule:
    weekly overtime cap, and minimum rest between any two shifts (no overlap is the
    rest=0 special case, so it's covered by the same check)."""
    total_minutes = sum(duration_minutes(s) for s in emp_slots)
    if total_minutes > round(labor_rules.weekly_overtime_threshold_hours * 60):
        return False

    intervals = sorted(
        (to_minutes(s.date, s.start_time, week_start_date), duration_minutes(s)) for s in emp_slots
    )
    rest_minutes = round(labor_rules.min_rest_hours_between_shifts * 60)
    for i in range(len(intervals) - 1):
        start_i, dur_i = intervals[i]
        start_next, _ = intervals[i + 1]
        if start_i + dur_i + rest_minutes > start_next:
            return False
    return True


def apply_proposed_assignments(
    baseline: dict[int, int | None],
    proposed: dict[int, int],
    slots_by_id: dict[int, SlotSpec],
    labor_rules: LaborRules,
    week_start_date: date_type,
) -> tuple[dict[int, int | None], list[int]]:
    """Starting from `baseline`, apply each proposed (slot_id -> employee_id) swap one at
    a time, in slot_id order, keeping a swap only if it leaves the *newly assigned*
    employee's full schedule valid. This is deterministic and catches swaps that are each
    individually fine vs. baseline but combine to break a constraint (the later one in
    slot_id order is the one that gets reverted) — the baseline itself, by construction,
    already satisfies every hard constraint, so it's always a safe fallback per slot.

    Returns (final_assignments, reverted_slot_ids).
    """
    current = dict(baseline)
    reverted: list[int] = []

    for slot_id in sorted(proposed.keys()):
        new_emp = proposed[slot_id]
        if current.get(slot_id) == new_emp:
            continue

        trial = dict(current)
        trial[slot_id] = new_emp
        emp_slots = [slots_by_id[sid] for sid, e in trial.items() if e == new_emp]

        if employee_slots_valid(emp_slots, labor_rules, week_start_date):
            current[slot_id] = new_emp
        else:
            reverted.append(slot_id)

    return current, reverted
