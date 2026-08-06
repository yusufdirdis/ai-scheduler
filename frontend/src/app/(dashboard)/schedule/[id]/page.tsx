"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { Badge, Button, Card, ErrorText, Select } from "@/components/ui/primitives";
import { ApiError } from "@/lib/apiFetch";
import { buildSchedule, getSchedule, listEmployees, updateScheduleAssignment } from "@/lib/scheduler-api";
import type { EmployeeSummary, ScheduleDetail, ScheduleSlot, ScheduleStatus } from "@/lib/types";

const STATUS_LABELS: Record<ScheduleStatus, string> = {
  draft: "Draft",
  ai_generated: "AI drafted",
  manager_reviewing: "Reviewing",
  published: "Published",
  archived: "Archived",
};

const STATUS_TONE: Record<ScheduleStatus, "default" | "success" | "warning"> = {
  draft: "default",
  ai_generated: "warning",
  manager_reviewing: "warning",
  published: "success",
  archived: "default",
};

const UNASSIGNED = "unassigned";

export default function ScheduleDetailPage() {
  const params = useParams<{ id: string }>();
  const scheduleId = Number(params.id);

  const [schedule, setSchedule] = useState<ScheduleDetail | null>(null);
  const [employees, setEmployees] = useState<EmployeeSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [building, setBuilding] = useState(false);
  const [savingSlotId, setSavingSlotId] = useState<number | null>(null);

  function refresh() {
    getSchedule(scheduleId)
      .then(setSchedule)
      .catch((err) => setError(err instanceof ApiError ? String(err.detail) : "Failed to load schedule"));
  }

  useEffect(() => {
    refresh();
    listEmployees().then(setEmployees).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scheduleId]);

  async function handleBuild() {
    setBuilding(true);
    setError(null);
    try {
      const updated = await buildSchedule(scheduleId);
      setSchedule(updated);
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Failed to build schedule");
    } finally {
      setBuilding(false);
    }
  }

  async function handleReassign(slotId: number, employeeIdRaw: string) {
    const employeeId = employeeIdRaw === UNASSIGNED ? null : Number(employeeIdRaw);
    setSavingSlotId(slotId);
    setError(null);
    try {
      const updated = await updateScheduleAssignment(scheduleId, slotId, employeeId);
      setSchedule(updated);
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Failed to reassign");
    } finally {
      setSavingSlotId(null);
    }
  }

  if (error && !schedule) return <p className="text-sm text-red-400">{error}</p>;
  if (!schedule) return <p className="text-sm text-[var(--as-muted)]">Loading…</p>;

  const activeEmployees = employees.filter((e) => e.is_active);
  const isLocked = schedule.status === "published";

  const slotsByDate = new Map<string, ScheduleSlot[]>();
  for (const slot of schedule.slots) {
    const list = slotsByDate.get(slot.date) ?? [];
    list.push(slot);
    slotsByDate.set(slot.date, list);
  }
  const dates = Array.from(slotsByDate.keys()).sort();

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-medium">Week of {schedule.week_start_date}</h1>
          <p className="text-sm text-[var(--as-muted)]">
            {schedule.unfilled_slot_count > 0 ? `${schedule.unfilled_slot_count} slot(s) unfilled` : "Fully staffed"}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Badge tone={STATUS_TONE[schedule.status]}>{STATUS_LABELS[schedule.status]}</Badge>
          {!isLocked && (
            <Button disabled={building} onClick={handleBuild}>
              {building ? "Building…" : schedule.status === "draft" ? "Build schedule" : "Rebuild"}
            </Button>
          )}
        </div>
      </div>

      <ErrorText>{error}</ErrorText>

      {schedule.slots.length === 0 ? (
        <Card>
          <p className="text-sm text-[var(--as-muted)]">
            No slots on this schedule — add shift templates with coverage requirements on the Coverage page.
          </p>
        </Card>
      ) : (
        dates.map((date) => (
          <Card key={date}>
            <h2 className="mb-3 text-sm font-medium">
              {new Date(date + "T00:00:00").toLocaleDateString(undefined, { weekday: "long", month: "short", day: "numeric" })}
            </h2>
            <div className="flex flex-col divide-y divide-[var(--as-border)]">
              {slotsByDate.get(date)!.map((slot) => (
                <div key={slot.id} className="flex items-center justify-between gap-4 py-3">
                  <div className="flex-1">
                    <p className="text-sm">
                      {slot.role_name} · {slot.start_time}–{slot.end_time}
                      {slot.skill_name && (
                        <span className="ml-2 text-xs text-[var(--as-muted)]">
                          requires {slot.skill_name}
                          {slot.min_skill_rating ? ` ${slot.min_skill_rating}+` : ""}
                        </span>
                      )}
                    </p>
                    {slot.assignment?.rationale && (
                      <p className="mt-0.5 text-xs text-[var(--as-muted)]" title={slot.assignment.rationale}>
                        {slot.assignment.rationale}
                      </p>
                    )}
                    {slot.assignment?.is_manually_edited && (
                      <span className="mt-0.5 inline-block">
                        <Badge>Manually edited</Badge>
                      </span>
                    )}
                  </div>
                  <div className="w-56 shrink-0">
                    <Select
                      value={slot.assignment?.employee_id ?? UNASSIGNED}
                      disabled={isLocked || savingSlotId === slot.id}
                      onChange={(e) => handleReassign(slot.id, e.target.value)}
                    >
                      <option value={UNASSIGNED}>— Unassigned —</option>
                      {activeEmployees.map((emp) => (
                        <option key={emp.id} value={emp.id}>
                          {emp.full_name}
                        </option>
                      ))}
                    </Select>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        ))
      )}
    </div>
  );
}
