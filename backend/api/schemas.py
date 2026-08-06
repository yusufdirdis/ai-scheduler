"""Shared request/response schemas for the manager dashboard API."""
from __future__ import annotations

from datetime import date, time
from typing import Optional

from pydantic import BaseModel, Field, model_validator


# ---- Business + labor rules -------------------------------------------------

class BusinessUpdate(BaseModel):
    name: Optional[str] = None
    timezone: Optional[str] = None
    location_name: Optional[str] = None
    address: Optional[str] = None
    week_start_day: Optional[int] = Field(None, ge=0, le=6)
    availability_request_day_of_week: Optional[int] = Field(None, ge=0, le=6)
    availability_request_time: Optional[str] = None


class LaborRuleUpdate(BaseModel):
    weekly_overtime_threshold_hours: Optional[float] = Field(None, gt=0)
    min_rest_hours_between_shifts: Optional[float] = Field(None, ge=0)


# ---- Roles + skills (coverage taxonomy) -------------------------------------

class RoleCreate(BaseModel):
    name: str = Field(min_length=1)


class SkillCreate(BaseModel):
    name: str = Field(min_length=1)


# ---- Shift templates ----------------------------------------------------------

class ShiftTemplateRequirementIn(BaseModel):
    role_id: int
    count_required: int = Field(gt=0)
    skill_id: Optional[int] = None
    min_skill_rating: Optional[int] = Field(None, ge=1, le=5)


class ShiftTemplateCreate(BaseModel):
    name: Optional[str] = None
    day_of_week: int = Field(ge=0, le=6)
    start_time: time
    end_time: time
    requirements: list[ShiftTemplateRequirementIn] = Field(default_factory=list)


class ShiftTemplateUpdate(BaseModel):
    name: Optional[str] = None
    day_of_week: Optional[int] = Field(None, ge=0, le=6)
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    is_active: Optional[bool] = None


# ---- Employees ----------------------------------------------------------------

class EmployeeCreate(BaseModel):
    full_name: str = Field(min_length=1)
    phone_number: str = Field(min_length=1)


class EmployeeUpdate(BaseModel):
    full_name: Optional[str] = None
    phone_number: Optional[str] = None
    is_active: Optional[bool] = None


class EmployeeRoleIn(BaseModel):
    role_id: int
    is_primary: bool = False


class SkillRatingIn(BaseModel):
    rating: int = Field(ge=1, le=5)
    notes: Optional[str] = None


class ManagerNoteCreate(BaseModel):
    note_text: str = Field(min_length=1)


class AttendanceRecordCreate(BaseModel):
    status: str = Field(pattern="^(on_time|late|no_show|called_out|left_early)$")
    minutes_late: Optional[int] = Field(None, ge=0)
    notes: Optional[str] = None


# ---- Availability (manual entry — Phase 3; SMS-sourced entries land in Phase 5) ----

class AvailabilityDaySlotIn(BaseModel):
    """One available window on one date. A day with no slot is simply absent —
    it's not an explicit 'unavailable' record, just nothing offered."""
    date: date
    start_time: time
    end_time: time

    @model_validator(mode="after")
    def _check_order(self):
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class AvailabilityEntryIn(BaseModel):
    """Full replace of one employee's availability for one week."""
    slots: list[AvailabilityDaySlotIn] = Field(default_factory=list)
