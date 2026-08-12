import { apiJson } from "@/lib/apiFetch";
import type {
  AvailabilityDaySlot,
  AvailabilityDetail,
  AvailabilityStatusRow,
  Business,
  EmployeeDetail,
  EmployeeSummary,
  LaborRules,
  Role,
  ScheduleDetail,
  ScheduleSummary,
  ShiftTemplate,
  Skill,
} from "@/lib/types";

// ---- Business + labor rules --------------------------------------------------

export const getBusiness = () => apiJson<Business>("/api/businesses/me");

export const updateBusiness = (payload: Partial<Business>) =>
  apiJson<Business>("/api/businesses/me", { method: "PATCH", body: JSON.stringify(payload) });

export const getLaborRules = () => apiJson<LaborRules>("/api/businesses/me/labor-rules");

export const updateLaborRules = (payload: Partial<LaborRules>) =>
  apiJson<LaborRules>("/api/businesses/me/labor-rules", {
    method: "PATCH",
    body: JSON.stringify(payload),
  });

// ---- Coverage: roles, skills, shift templates ----------------------------------

export const listRoles = () => apiJson<Role[]>("/api/coverage/roles");
export const createRole = (name: string) =>
  apiJson<Role>("/api/coverage/roles", { method: "POST", body: JSON.stringify({ name }) });
export const deleteRole = (id: number) =>
  apiJson<{ deleted: boolean }>(`/api/coverage/roles/${id}`, { method: "DELETE" });

export const listSkills = () => apiJson<Skill[]>("/api/coverage/skills");
export const createSkill = (name: string) =>
  apiJson<Skill>("/api/coverage/skills", { method: "POST", body: JSON.stringify({ name }) });
export const deleteSkill = (id: number) =>
  apiJson<{ deleted: boolean }>(`/api/coverage/skills/${id}`, { method: "DELETE" });

export const listShiftTemplates = () => apiJson<ShiftTemplate[]>("/api/coverage/shift-templates");

export interface ShiftTemplateInput {
  name?: string | null;
  day_of_week: number;
  start_time: string;
  end_time: string;
  requirements: { role_id: number; count_required: number; skill_id?: number | null; min_skill_rating?: number | null }[];
}

export const createShiftTemplate = (payload: ShiftTemplateInput) =>
  apiJson<ShiftTemplate>("/api/coverage/shift-templates", {
    method: "POST",
    body: JSON.stringify(payload),
  });

export const updateShiftTemplate = (id: number, payload: Partial<ShiftTemplateInput> & { is_active?: boolean }) =>
  apiJson<ShiftTemplate>(`/api/coverage/shift-templates/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });

export const deleteShiftTemplate = (id: number) =>
  apiJson<{ deleted: boolean }>(`/api/coverage/shift-templates/${id}`, { method: "DELETE" });

// ---- Employees ------------------------------------------------------------------

export const listEmployees = () => apiJson<EmployeeSummary[]>("/api/employees");

export const getEmployee = (id: number) => apiJson<EmployeeDetail>(`/api/employees/${id}`);

export const createEmployee = (payload: { full_name: string; phone_number: string }) =>
  apiJson<EmployeeDetail>("/api/employees", { method: "POST", body: JSON.stringify(payload) });

export const updateEmployee = (
  id: number,
  payload: Partial<{ full_name: string; phone_number: string; is_active: boolean }>
) => apiJson<EmployeeDetail>(`/api/employees/${id}`, { method: "PATCH", body: JSON.stringify(payload) });

export const deactivateEmployee = (id: number) =>
  apiJson<{ deactivated: boolean }>(`/api/employees/${id}`, { method: "DELETE" });

export const assignEmployeeRole = (employeeId: number, roleId: number, isPrimary: boolean) =>
  apiJson<EmployeeDetail>(`/api/employees/${employeeId}/roles`, {
    method: "POST",
    body: JSON.stringify({ role_id: roleId, is_primary: isPrimary }),
  });

export const unassignEmployeeRole = (employeeId: number, roleId: number) =>
  apiJson<EmployeeDetail>(`/api/employees/${employeeId}/roles/${roleId}`, { method: "DELETE" });

export const rateEmployeeSkill = (employeeId: number, skillId: number, rating: number, notes?: string) =>
  apiJson<EmployeeDetail>(`/api/employees/${employeeId}/skills/${skillId}`, {
    method: "PUT",
    body: JSON.stringify({ rating, notes }),
  });

export const removeEmployeeSkillRating = (employeeId: number, skillId: number) =>
  apiJson<EmployeeDetail>(`/api/employees/${employeeId}/skills/${skillId}`, { method: "DELETE" });

export const addEmployeeNote = (employeeId: number, noteText: string) =>
  apiJson<EmployeeDetail>(`/api/employees/${employeeId}/notes`, {
    method: "POST",
    body: JSON.stringify({ note_text: noteText }),
  });

export const removeEmployeeNote = (employeeId: number, noteId: number) =>
  apiJson<EmployeeDetail>(`/api/employees/${employeeId}/notes/${noteId}`, { method: "DELETE" });

export const addAttendanceRecord = (
  employeeId: number,
  payload: { status: string; minutes_late?: number; notes?: string }
) =>
  apiJson<EmployeeDetail>(`/api/employees/${employeeId}/attendance`, {
    method: "POST",
    body: JSON.stringify(payload),
  });

// ---- Availability (manual entry) ------------------------------------------------

export const getAvailabilityStatus = (weekStartDate: string) =>
  apiJson<AvailabilityStatusRow[]>(`/api/availability/status?week_start_date=${weekStartDate}`);

export const getEmployeeAvailability = (employeeId: number, weekStartDate: string) =>
  apiJson<AvailabilityDetail>(`/api/availability/${employeeId}?week_start_date=${weekStartDate}`);

export const setEmployeeAvailability = (
  employeeId: number,
  weekStartDate: string,
  slots: AvailabilityDaySlot[]
) =>
  apiJson<AvailabilityDetail>(`/api/availability/${employeeId}?week_start_date=${weekStartDate}`, {
    method: "PUT",
    body: JSON.stringify({ slots }),
  });

export const requestAvailabilityNow = () =>
  apiJson<{ status: string }>("/api/availability/request-now", { method: "POST" });

// ---- Schedules (AI + manual) ------------------------------------------------------

export const listSchedules = () => apiJson<ScheduleSummary[]>("/api/schedules");

export const createSchedule = (weekStartDate: string) =>
  apiJson<ScheduleDetail>("/api/schedules", {
    method: "POST",
    body: JSON.stringify({ week_start_date: weekStartDate }),
  });

export const getSchedule = (id: number) => apiJson<ScheduleDetail>(`/api/schedules/${id}`);

export const buildSchedule = (id: number) =>
  apiJson<ScheduleDetail>(`/api/schedules/${id}/build`, { method: "POST" });

export const updateScheduleAssignment = (scheduleId: number, slotId: number, employeeId: number | null) =>
  apiJson<ScheduleDetail>(`/api/schedules/${scheduleId}/assignments/${slotId}`, {
    method: "PATCH",
    body: JSON.stringify({ employee_id: employeeId }),
  });
