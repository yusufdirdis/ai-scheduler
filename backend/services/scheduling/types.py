"""Plain dataclasses the solver/ranker/validator operate on — no DB/ORM dependency,
so the scheduling logic is unit-testable without a database."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date as date_type
from datetime import time as time_type


@dataclass(frozen=True)
class SlotSpec:
    id: int
    role_id: int
    date: date_type
    start_time: time_type
    end_time: time_type
    skill_id: int | None = None
    min_skill_rating: int | None = None


@dataclass(frozen=True)
class AvailabilityWindow:
    date: date_type
    start_time: time_type
    end_time: time_type


@dataclass(frozen=True)
class EmployeeSpec:
    id: int
    role_ids: frozenset[int]
    skill_ratings: dict[int, int] = field(default_factory=dict)  # skill_id -> 1-5
    availability: tuple[AvailabilityWindow, ...] = ()


@dataclass(frozen=True)
class LaborRules:
    weekly_overtime_threshold_hours: float
    min_rest_hours_between_shifts: float


@dataclass
class SolverResult:
    assignments: dict[int, int | None]  # slot_id -> employee_id, None if unfilled
    eligible: dict[int, list[int]]  # slot_id -> eligible employee_ids
    structurally_unfilled_slot_ids: list[int]  # no eligible employee at all
