from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
    func,
)

from db.session import Base


class Business(Base):
    __tablename__ = "businesses"

    id = Column(Integer, primary_key=True, index=True)
    owner_user_id = Column(String, unique=True, index=True)  # Supabase user UUID
    name = Column(String, index=True)
    timezone = Column(String, default="America/New_York")
    business_type = Column(String, default="restaurant")  # future: other verticals

    # v1 is single-location — kept as flat columns rather than a separate
    # Location table. If multi-location is ever needed, extract a
    # Location(business_id, name, address, timezone) table and add nullable
    # location_id FKs to Employee/ShiftTemplate/ShiftSlot.
    location_name = Column(String, nullable=True)
    address = Column(String, nullable=True)

    # v1 uses one shared platform Twilio number (settings.TWILIO_FROM_NUMBER);
    # this column is the schema hook for per-tenant numbers later.
    twilio_phone_number = Column(String, nullable=True)

    week_start_day = Column(Integer, default=0)  # 0=Monday
    availability_request_day_of_week = Column(Integer, default=2)
    availability_request_time = Column(String, default="09:00")  # "HH:MM", business-local

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class LaborRule(Base):
    __tablename__ = "labor_rules"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), unique=True)
    weekly_overtime_threshold_hours = Column(Float, default=40.0)
    min_rest_hours_between_shifts = Column(Float, default=10.0)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Role(Base):
    """Business-scoped, manager-editable — not a hardcoded enum. 'cook', 'server', etc."""

    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), index=True)
    name = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Skill(Base):
    """Business-scoped. 'grill station', 'wine cert', 'POS system'."""

    __tablename__ = "skills"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), index=True)
    name = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Employee(Base):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), index=True)
    full_name = Column(String)
    # E.164, globally unique (not per-business) — v1 routes inbound SMS to a
    # business purely by matching From -> Employee.phone_number, since all
    # businesses share one platform Twilio number.
    phone_number = Column(String, unique=True, index=True)
    is_active = Column(Boolean, default=True)
    hire_date = Column(DateTime(timezone=True), nullable=True)
    reliability_score = Column(Float, nullable=True)  # cached, derived from AttendanceRecord
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class EmployeeRole(Base):
    """Which roles an employee can be scheduled into."""

    __tablename__ = "employee_roles"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), index=True)
    role_id = Column(Integer, ForeignKey("roles.id"), index=True)
    is_primary = Column(Boolean, default=False)

    __table_args__ = (UniqueConstraint("employee_id", "role_id"),)


class EmployeeSkillRating(Base):
    """Pros/cons signal #1: skill/station ratings."""

    __tablename__ = "employee_skill_ratings"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), index=True)
    skill_id = Column(Integer, ForeignKey("skills.id"), index=True)
    rating = Column(Integer)  # 1-5
    rated_by_user_id = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (UniqueConstraint("employee_id", "skill_id"),)


class ManagerNote(Base):
    """Pros/cons signal #2: manager free-text notes."""

    __tablename__ = "manager_notes"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), index=True)
    author_user_id = Column(String)
    note_text = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AttendanceRecord(Base):
    """Pros/cons signal #3 (raw events; reliability_score is derived from these)."""

    __tablename__ = "attendance_records"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), index=True)
    shift_assignment_id = Column(Integer, ForeignKey("shift_assignments.id"), nullable=True)
    status = Column(String)  # 'on_time' | 'late' | 'no_show' | 'called_out' | 'left_early'
    minutes_late = Column(Integer, nullable=True)
    notes = Column(Text, nullable=True)
    recorded_by_user_id = Column(String, nullable=True)
    recorded_at = Column(DateTime(timezone=True), server_default=func.now())


class ShiftTemplate(Base):
    """Recurring weekly coverage pattern, manager-configured. e.g. 'Friday Dinner'."""

    __tablename__ = "shift_templates"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), index=True)
    name = Column(String, nullable=True)
    day_of_week = Column(Integer)  # 0-6
    start_time = Column(Time)
    end_time = Column(Time)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ShiftTemplateRequirement(Base):
    """'Friday Dinner needs 2 cooks, 1 host, 3 servers' — one row per role need."""

    __tablename__ = "shift_template_requirements"

    id = Column(Integer, primary_key=True, index=True)
    shift_template_id = Column(Integer, ForeignKey("shift_templates.id"), index=True)
    role_id = Column(Integer, ForeignKey("roles.id"))
    count_required = Column(Integer)
    skill_id = Column(Integer, ForeignKey("skills.id"), nullable=True)  # hard cert requirement, optional
    min_skill_rating = Column(Integer, nullable=True)


class Schedule(Base):
    """One row per business per week."""

    __tablename__ = "schedules"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), index=True)
    week_start_date = Column(Date)
    status = Column(String, default="draft")  # draft|ai_generated|manager_reviewing|published|archived
    generated_at = Column(DateTime(timezone=True), nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    created_by_user_id = Column(String, nullable=True)
    unfilled_slot_count = Column(Integer, default=0)  # surfaced from last solver run
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("business_id", "week_start_date"),)


class ShiftSlot(Base):
    """One seat to fill — a template's '2 cooks' expands to 2 rows for a given date."""

    __tablename__ = "shift_slots"

    id = Column(Integer, primary_key=True, index=True)
    schedule_id = Column(Integer, ForeignKey("schedules.id"), index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), index=True)  # denorm for query convenience
    role_id = Column(Integer, ForeignKey("roles.id"))
    skill_id = Column(Integer, ForeignKey("skills.id"), nullable=True)
    min_skill_rating = Column(Integer, nullable=True)
    date = Column(Date)
    start_time = Column(Time)
    end_time = Column(Time)
    source_template_id = Column(Integer, ForeignKey("shift_templates.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ShiftAssignment(Base):
    __tablename__ = "shift_assignments"

    id = Column(Integer, primary_key=True, index=True)
    shift_slot_id = Column(Integer, ForeignKey("shift_slots.id"), unique=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=True)  # null = unfilled
    assigned_by = Column(String, default="solver")  # 'solver' | 'llm' | 'manager_manual'
    rationale = Column(Text, nullable=True)  # LLM's stated reason, shown in dashboard tooltip
    is_manually_edited = Column(Boolean, default=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AvailabilitySubmission(Base):
    __tablename__ = "availability_submissions"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), index=True)
    week_start_date = Column(Date)
    requested_at = Column(DateTime(timezone=True), nullable=True)
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    raw_sms_text = Column(Text, nullable=True)
    status = Column(String, default="pending")  # pending|submitted|no_response|parse_failed|manual_entry
    parse_confidence = Column(Float, nullable=True)

    __table_args__ = (UniqueConstraint("employee_id", "week_start_date"),)


class AvailabilitySlot(Base):
    """Structured parse output of an AvailabilitySubmission's raw SMS text."""

    __tablename__ = "availability_slots"

    id = Column(Integer, primary_key=True, index=True)
    availability_submission_id = Column(Integer, ForeignKey("availability_submissions.id"), index=True)
    date = Column(Date)
    start_time = Column(Time)
    end_time = Column(Time)
    is_available = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class SmsMessage(Base):
    """Full audit log of every SMS sent or received."""

    __tablename__ = "sms_messages"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=True)
    direction = Column(String)  # 'outbound' | 'inbound'
    phone_number = Column(String)
    twilio_sid = Column(String, nullable=True, index=True)
    message_type = Column(String)  # availability_request|availability_reply|schedule_published|manual
    body_text = Column(Text)
    status = Column(String, default="queued")  # queued|sent|delivered|failed|received
    related_schedule_id = Column(Integer, ForeignKey("schedules.id"), nullable=True)
    related_availability_submission_id = Column(
        Integer, ForeignKey("availability_submissions.id"), nullable=True
    )
    error_message = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
