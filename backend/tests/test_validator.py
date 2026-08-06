from datetime import date, time

from services.scheduling.types import LaborRules, SlotSpec
from services.scheduling.validator import apply_proposed_assignments, employee_slots_valid

MONDAY = date(2026, 8, 3)
COOK = 1

LAX_RULES = LaborRules(weekly_overtime_threshold_hours=100, min_rest_hours_between_shifts=0)


def slot(id_, start_h, end_h, d=MONDAY):
    return SlotSpec(id=id_, role_id=COOK, date=d, start_time=time(start_h, 0), end_time=time(end_h, 0))


def test_employee_slots_valid_rejects_overlap():
    slots = [slot(1, 9, 17), slot(2, 15, 22)]
    assert not employee_slots_valid(slots, LAX_RULES, MONDAY)


def test_employee_slots_valid_rejects_insufficient_rest():
    slots = [slot(1, 9, 17), slot(2, 20, 23)]
    rules = LaborRules(weekly_overtime_threshold_hours=100, min_rest_hours_between_shifts=10)
    assert not employee_slots_valid(slots, rules, MONDAY)


def test_employee_slots_valid_rejects_overtime():
    slots = [slot(1, 0, 8), slot(2, 0, 8, date(2026, 8, 4)), slot(3, 0, 8, date(2026, 8, 5))]
    rules = LaborRules(weekly_overtime_threshold_hours=20, min_rest_hours_between_shifts=0)
    assert not employee_slots_valid(slots, rules, MONDAY)


def test_apply_proposed_keeps_valid_swap():
    slots_by_id = {1: slot(1, 9, 17)}
    baseline = {1: 100}
    proposed = {1: 200}  # employee 200 has no other shifts -> always valid
    final, reverted = apply_proposed_assignments(baseline, proposed, slots_by_id, LAX_RULES, MONDAY)
    assert final[1] == 200
    assert reverted == []


def test_apply_proposed_reverts_swap_that_creates_double_booking():
    # Employee 200 already has slot 2 (15-22); swapping them into slot 1 (9-17) overlaps.
    slots_by_id = {1: slot(1, 9, 17), 2: slot(2, 15, 22)}
    baseline = {1: 100, 2: 200}
    proposed = {1: 200}  # would give employee 200 both slot 1 and slot 2 -> overlap
    final, reverted = apply_proposed_assignments(baseline, proposed, slots_by_id, LAX_RULES, MONDAY)
    assert final[1] == 100, "invalid swap must revert to the solver's baseline, not persist a violation"
    assert reverted == [1]


def test_apply_proposed_second_of_two_locally_fine_swaps_reverts_when_combined_violate():
    # Two independent swaps that are each fine vs. the ORIGINAL baseline, but together
    # give employee 300 an overlapping pair of shifts.
    slots_by_id = {1: slot(1, 9, 13), 2: slot(2, 12, 17)}
    baseline = {1: 100, 2: 200}
    proposed = {1: 300, 2: 300}
    final, reverted = apply_proposed_assignments(baseline, proposed, slots_by_id, LAX_RULES, MONDAY)
    # First swap (slot 1) applies cleanly; second swap (slot 2) would overlap with it and reverts.
    assert final[1] == 300
    assert final[2] == 200
    assert reverted == [2]
