from datetime import date, time

from services.scheduling.solver import compute_eligibility, solve_baseline
from services.scheduling.types import AvailabilityWindow, EmployeeSpec, LaborRules, SlotSpec

MONDAY = date(2026, 8, 3)
TUESDAY = date(2026, 8, 4)
COOK = 1
SERVER = 2
GRILL = 100

LAX_RULES = LaborRules(weekly_overtime_threshold_hours=100, min_rest_hours_between_shifts=0)


def full_day_window(d: date) -> AvailabilityWindow:
    return AvailabilityWindow(date=d, start_time=time(0, 0), end_time=time(23, 59))


def test_fills_slot_with_sole_eligible_employee():
    slot = SlotSpec(id=1, role_id=COOK, date=MONDAY, start_time=time(9, 0), end_time=time(17, 0))
    emp = EmployeeSpec(id=1, role_ids=frozenset({COOK}), availability=(full_day_window(MONDAY),))
    result = solve_baseline([slot], [emp], LAX_RULES, MONDAY)
    assert result.assignments[1] == 1
    assert result.structurally_unfilled_slot_ids == []


def test_no_eligible_employee_is_structurally_unfilled_not_a_crash():
    slot = SlotSpec(id=1, role_id=COOK, date=MONDAY, start_time=time(9, 0), end_time=time(17, 0))
    emp = EmployeeSpec(id=1, role_ids=frozenset({SERVER}), availability=(full_day_window(MONDAY),))
    result = solve_baseline([slot], [emp], LAX_RULES, MONDAY)
    assert result.assignments[1] is None
    assert result.structurally_unfilled_slot_ids == [1]


def test_never_assigns_outside_submitted_availability():
    slot = SlotSpec(id=1, role_id=COOK, date=MONDAY, start_time=time(9, 0), end_time=time(17, 0))
    # Employee is only available Tuesday, not Monday.
    emp = EmployeeSpec(id=1, role_ids=frozenset({COOK}), availability=(full_day_window(TUESDAY),))
    result = solve_baseline([slot], [emp], LAX_RULES, MONDAY)
    assert result.assignments[1] is None
    assert result.structurally_unfilled_slot_ids == [1]


def test_no_double_booking_same_employee_overlapping_slots():
    slot_a = SlotSpec(id=1, role_id=COOK, date=MONDAY, start_time=time(9, 0), end_time=time(17, 0))
    slot_b = SlotSpec(id=2, role_id=SERVER, date=MONDAY, start_time=time(15, 0), end_time=time(22, 0))
    emp = EmployeeSpec(
        id=1, role_ids=frozenset({COOK, SERVER}), availability=(full_day_window(MONDAY),)
    )
    result = solve_baseline([slot_a, slot_b], [emp], LAX_RULES, MONDAY)
    filled = [sid for sid, e in result.assignments.items() if e is not None]
    assert len(filled) == 1, "overlapping shifts must never both be assigned to the same employee"


def test_min_rest_between_shifts_respected_across_slots():
    # 8-hour shift ending 17:00, next shift starting 20:00 -> only a 3h gap.
    slot_a = SlotSpec(id=1, role_id=COOK, date=MONDAY, start_time=time(9, 0), end_time=time(17, 0))
    slot_b = SlotSpec(id=2, role_id=COOK, date=MONDAY, start_time=time(20, 0), end_time=time(23, 0))
    rules = LaborRules(weekly_overtime_threshold_hours=100, min_rest_hours_between_shifts=10)
    emp = EmployeeSpec(id=1, role_ids=frozenset({COOK}), availability=(full_day_window(MONDAY),))
    result = solve_baseline([slot_a, slot_b], [emp], rules, MONDAY)
    filled = [sid for sid, e in result.assignments.items() if e is not None]
    assert len(filled) == 1, "a 3h gap must not satisfy a 10h minimum rest requirement"


def test_min_rest_satisfied_across_day_boundary():
    # Monday 17:00-22:00, next slot Tuesday 09:00-17:00 -> 11h gap, satisfies a 10h rest rule.
    slot_a = SlotSpec(id=1, role_id=COOK, date=MONDAY, start_time=time(17, 0), end_time=time(22, 0))
    slot_b = SlotSpec(id=2, role_id=COOK, date=TUESDAY, start_time=time(9, 0), end_time=time(17, 0))
    rules = LaborRules(weekly_overtime_threshold_hours=100, min_rest_hours_between_shifts=10)
    emp = EmployeeSpec(
        id=1, role_ids=frozenset({COOK}), availability=(full_day_window(MONDAY), full_day_window(TUESDAY))
    )
    result = solve_baseline([slot_a, slot_b], [emp], rules, MONDAY)
    assert result.assignments[1] == 1
    assert result.assignments[2] == 1


def test_weekly_overtime_cap_respected():
    # Three 8h shifts = 24h; cap of 20h should leave one unfilled for this sole employee.
    slots = [
        SlotSpec(id=i, role_id=COOK, date=MONDAY, start_time=time(h, 0), end_time=time(h + 8, 0))
        for i, h in enumerate([0], start=1)
    ] + [
        SlotSpec(id=2, role_id=COOK, date=TUESDAY, start_time=time(0, 0), end_time=time(8, 0)),
        SlotSpec(id=3, role_id=COOK, date=date(2026, 8, 5), start_time=time(0, 0), end_time=time(8, 0)),
    ]
    rules = LaborRules(weekly_overtime_threshold_hours=20, min_rest_hours_between_shifts=0)
    emp = EmployeeSpec(
        id=1,
        role_ids=frozenset({COOK}),
        availability=(full_day_window(MONDAY), full_day_window(TUESDAY), full_day_window(date(2026, 8, 5))),
    )
    result = solve_baseline(slots, [emp], rules, MONDAY)
    filled = [sid for sid, e in result.assignments.items() if e is not None]
    assert len(filled) == 2, "24h of shifts against a 20h cap must leave exactly one slot unfilled"


def test_hard_skill_requirement_excludes_underqualified_employee():
    slot = SlotSpec(id=1, role_id=COOK, date=MONDAY, start_time=time(9, 0), end_time=time(17, 0), skill_id=GRILL, min_skill_rating=4)
    underqualified = EmployeeSpec(
        id=1, role_ids=frozenset({COOK}), skill_ratings={GRILL: 2}, availability=(full_day_window(MONDAY),)
    )
    qualified = EmployeeSpec(
        id=2, role_ids=frozenset({COOK}), skill_ratings={GRILL: 4}, availability=(full_day_window(MONDAY),)
    )
    eligible = compute_eligibility([slot], [underqualified, qualified])
    assert eligible[1] == [2]

    result = solve_baseline([slot], [underqualified, qualified], LAX_RULES, MONDAY)
    assert result.assignments[1] == 2


def test_maximizes_coverage_when_employees_are_scarce():
    # Two slots, two employees each eligible for only one -> both should get filled.
    slot_a = SlotSpec(id=1, role_id=COOK, date=MONDAY, start_time=time(9, 0), end_time=time(17, 0))
    slot_b = SlotSpec(id=2, role_id=SERVER, date=MONDAY, start_time=time(9, 0), end_time=time(17, 0))
    cook = EmployeeSpec(id=1, role_ids=frozenset({COOK}), availability=(full_day_window(MONDAY),))
    server = EmployeeSpec(id=2, role_ids=frozenset({SERVER}), availability=(full_day_window(MONDAY),))
    result = solve_baseline([slot_a, slot_b], [cook, server], LAX_RULES, MONDAY)
    assert result.assignments[1] == 1
    assert result.assignments[2] == 2


def test_compute_candidates_includes_baseline_and_feasible_alternate():
    from services.scheduling.solver import compute_candidates

    slot = SlotSpec(id=1, role_id=COOK, date=MONDAY, start_time=time(9, 0), end_time=time(17, 0))
    baseline = EmployeeSpec(id=1, role_ids=frozenset({COOK}), availability=(full_day_window(MONDAY),))
    alt = EmployeeSpec(id=2, role_ids=frozenset({COOK}), availability=(full_day_window(MONDAY),))
    result = solve_baseline([slot], [baseline, alt], LAX_RULES, MONDAY)
    winner = result.assignments[1]
    assert winner in (1, 2)  # CP-SAT doesn't guarantee tie-break order between symmetric optima
    other = 2 if winner == 1 else 1

    candidates = compute_candidates(result, [slot], LAX_RULES, MONDAY)
    assert candidates[1][0] == winner, "baseline assignee must be first"
    assert other in candidates[1], "the other employee has no conflicting shifts, so should be a feasible alternate"


def test_compute_candidates_excludes_alternate_with_conflicting_shift():
    slot_a = SlotSpec(id=1, role_id=COOK, date=MONDAY, start_time=time(9, 0), end_time=time(17, 0))
    slot_b = SlotSpec(id=2, role_id=COOK, date=MONDAY, start_time=time(15, 0), end_time=time(22, 0))
    from services.scheduling.solver import compute_candidates

    emp1 = EmployeeSpec(id=1, role_ids=frozenset({COOK}), availability=(full_day_window(MONDAY),))
    emp2 = EmployeeSpec(id=2, role_ids=frozenset({COOK}), availability=(full_day_window(MONDAY),))
    result = solve_baseline([slot_a, slot_b], [emp1, emp2], LAX_RULES, MONDAY)
    # Solver fills both slots (maximizing coverage): one employee per slot.
    assert result.assignments[1] is not None and result.assignments[2] is not None
    assert result.assignments[1] != result.assignments[2]

    candidates = compute_candidates(result, [slot_a, slot_b], LAX_RULES, MONDAY)
    # Whoever is NOT baseline for slot 1 already works the overlapping slot 2, so they
    # can't be offered as an alternate for slot 1.
    other_emp = 2 if result.assignments[1] == 1 else 1
    assert other_emp not in candidates[1]
