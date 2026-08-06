export interface Business {
  id: number;
  name: string;
  business_type: string;
  timezone: string;
  location_name: string | null;
  address: string | null;
  week_start_day: number;
  availability_request_day_of_week: number;
  availability_request_time: string;
}

export interface LaborRules {
  weekly_overtime_threshold_hours: number;
  min_rest_hours_between_shifts: number;
}

export interface Role {
  id: number;
  name: string;
}

export interface Skill {
  id: number;
  name: string;
}

export interface ShiftTemplateRequirement {
  id: number;
  role_id: number;
  count_required: number;
  skill_id: number | null;
  min_skill_rating: number | null;
}

export interface ShiftTemplate {
  id: number;
  name: string | null;
  day_of_week: number;
  start_time: string;
  end_time: string;
  is_active: boolean;
  requirements: ShiftTemplateRequirement[];
}

export interface EmployeeSummary {
  id: number;
  full_name: string;
  phone_number: string;
  is_active: boolean;
  reliability_score: number | null;
  roles: string[];
}

export interface EmployeeRoleAssignment {
  role_id: number;
  role_name: string;
  is_primary: boolean;
}

export interface EmployeeSkillRating {
  skill_id: number;
  skill_name: string;
  rating: number;
  notes: string | null;
}

export interface ManagerNote {
  id: number;
  note_text: string;
  author_user_id: string;
  created_at: string | null;
}

export interface AttendanceRecord {
  id: number;
  status: "on_time" | "late" | "no_show" | "called_out" | "left_early";
  minutes_late: number | null;
  notes: string | null;
  recorded_at: string | null;
}

export interface EmployeeDetail {
  id: number;
  full_name: string;
  phone_number: string;
  is_active: boolean;
  reliability_score: number | null;
  roles: EmployeeRoleAssignment[];
  skill_ratings: EmployeeSkillRating[];
  notes: ManagerNote[];
  attendance: AttendanceRecord[];
}

export const DAYS_OF_WEEK = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

export const ATTENDANCE_STATUSES: AttendanceRecord["status"][] = [
  "on_time",
  "late",
  "no_show",
  "called_out",
  "left_early",
];

export type AvailabilityStatus = "pending" | "manual_entry" | "submitted" | "no_response" | "parse_failed";

export interface AvailabilityStatusRow {
  employee_id: number;
  full_name: string;
  status: AvailabilityStatus;
  submitted_at: string | null;
  slot_count: number;
}

export interface AvailabilityDaySlot {
  date: string;
  start_time: string;
  end_time: string;
}

export interface AvailabilityDetail {
  status: AvailabilityStatus;
  submitted_at: string | null;
  slots: AvailabilityDaySlot[];
}

export type ScheduleStatus = "draft" | "ai_generated" | "manager_reviewing" | "published" | "archived";

export interface ScheduleSummary {
  id: number;
  week_start_date: string;
  status: ScheduleStatus;
  unfilled_slot_count: number;
  generated_at: string | null;
  published_at: string | null;
}

export interface ShiftAssignmentInfo {
  employee_id: number | null;
  employee_name: string | null;
  assigned_by: "solver" | "llm" | "manager_manual";
  rationale: string | null;
  is_manually_edited: boolean;
}

export interface ScheduleSlot {
  id: number;
  role_id: number;
  role_name: string;
  skill_id: number | null;
  skill_name: string | null;
  min_skill_rating: number | null;
  date: string;
  start_time: string;
  end_time: string;
  assignment: ShiftAssignmentInfo | null;
}

export interface ScheduleDetail extends ScheduleSummary {
  slots: ScheduleSlot[];
}
