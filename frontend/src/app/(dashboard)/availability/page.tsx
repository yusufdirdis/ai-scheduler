"use client";

import { useEffect, useState } from "react";
import { Badge, Button, Card, ErrorText, Input } from "@/components/ui/primitives";
import { ApiError } from "@/lib/apiFetch";
import { getBusiness, getEmployeeAvailability, getAvailabilityStatus, setEmployeeAvailability } from "@/lib/scheduler-api";
import type { AvailabilityDaySlot, AvailabilityStatusRow, Business } from "@/lib/types";
import { addDays, formatDate, formatWeekRange, weekDates, weekStartOnOrBefore } from "@/lib/weeks";

const STATUS_LABELS: Record<string, string> = {
  pending: "Pending",
  manual_entry: "Entered manually",
  submitted: "Submitted",
  no_response: "No response",
  parse_failed: "Couldn't parse",
};

const STATUS_TONE: Record<string, "default" | "success" | "warning"> = {
  pending: "warning",
  manual_entry: "success",
  submitted: "success",
  no_response: "warning",
  parse_failed: "warning",
};

export default function AvailabilityPage() {
  const [business, setBusiness] = useState<Business | null>(null);
  const [weekStart, setWeekStart] = useState<Date | null>(null);
  const [rows, setRows] = useState<AvailabilityStatusRow[]>([]);
  const [editingEmployeeId, setEditingEmployeeId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getBusiness()
      .then((b) => {
        setBusiness(b);
        setWeekStart(weekStartOnOrBefore(new Date(), b.week_start_day));
      })
      .catch((err) => setError(err.message ?? "Failed to load business"));
  }, []);

  function refresh(ws: Date) {
    setLoading(true);
    getAvailabilityStatus(formatDate(ws))
      .then(setRows)
      .catch((err) => setError(err instanceof ApiError ? String(err.detail) : "Failed to load availability"))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    // refresh() toggles the loading flag before an async fetch — an intentional,
    // safe re-render, not the unbounded cascading-render pattern this rule targets.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (weekStart) refresh(weekStart);
  }, [weekStart]);

  if (!business || !weekStart) {
    return <p className="text-sm text-[var(--as-muted)]">{error ?? "Loading…"}</p>;
  }

  const weekStartDateStr = formatDate(weekStart);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-medium">Availability</h1>
        <div className="flex items-center gap-3">
          <Button variant="secondary" onClick={() => setWeekStart(addDays(weekStart, -7))}>
            ← Prev week
          </Button>
          <span className="text-sm text-[var(--as-muted)]">{formatWeekRange(weekStart)}</span>
          <Button variant="secondary" onClick={() => setWeekStart(addDays(weekStart, 7))}>
            Next week →
          </Button>
        </div>
      </div>

      <ErrorText>{error}</ErrorText>

      {loading ? (
        <p className="text-sm text-[var(--as-muted)]">Loading…</p>
      ) : rows.length === 0 ? (
        <Card>
          <p className="text-sm text-[var(--as-muted)]">No active employees yet — add some on the Employees page.</p>
        </Card>
      ) : (
        <div className="flex flex-col divide-y divide-[var(--as-border)] overflow-hidden rounded-lg border border-[var(--as-border)]">
          {rows.map((row) => (
            <div key={row.employee_id} className="bg-[var(--as-surface)]">
              <div className="flex items-center justify-between px-4 py-3">
                <div>
                  <p className="text-sm font-medium">{row.full_name}</p>
                  <p className="text-xs text-[var(--as-muted)]">
                    {row.slot_count > 0 ? `${row.slot_count} window${row.slot_count === 1 ? "" : "s"} offered` : "No availability entered"}
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <Badge tone={STATUS_TONE[row.status]}>{STATUS_LABELS[row.status] ?? row.status}</Badge>
                  <Button
                    variant="secondary"
                    onClick={() => setEditingEmployeeId(editingEmployeeId === row.employee_id ? null : row.employee_id)}
                  >
                    {editingEmployeeId === row.employee_id ? "Close" : "Enter / edit"}
                  </Button>
                </div>
              </div>
              {editingEmployeeId === row.employee_id && (
                <div className="border-t border-[var(--as-border)] px-4 py-4">
                  <AvailabilityEditor
                    employeeId={row.employee_id}
                    weekStart={weekStart}
                    weekStartDateStr={weekStartDateStr}
                    onSaved={() => {
                      refresh(weekStart);
                      setEditingEmployeeId(null);
                    }}
                  />
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

interface DayRow {
  date: Date;
  available: boolean;
  startTime: string;
  endTime: string;
}

function AvailabilityEditor({
  employeeId,
  weekStart,
  weekStartDateStr,
  onSaved,
}: {
  employeeId: number;
  weekStart: Date;
  weekStartDateStr: string;
  onSaved: () => void;
}) {
  const [days, setDays] = useState<DayRow[]>(() =>
    weekDates(weekStart).map((date) => ({ date, available: false, startTime: "09:00", endTime: "17:00" }))
  );
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Resets the loading flag when employeeId/week changes — intentional, not the
    // unbounded cascading-render pattern this rule targets.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true);
    getEmployeeAvailability(employeeId, weekStartDateStr)
      .then((detail) => {
        const byDate = new Map(detail.slots.map((s) => [s.date, s]));
        setDays(
          weekDates(weekStart).map((date) => {
            const key = formatDate(date);
            const slot = byDate.get(key);
            return slot
              ? { date, available: true, startTime: slot.start_time, endTime: slot.end_time }
              : { date, available: false, startTime: "09:00", endTime: "17:00" };
          })
        );
      })
      .catch((err) => setError(err instanceof ApiError ? String(err.detail) : "Failed to load"))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [employeeId, weekStartDateStr]);

  function updateDay(idx: number, patch: Partial<DayRow>) {
    setDays((prev) => prev.map((d, i) => (i === idx ? { ...d, ...patch } : d)));
  }

  async function save() {
    setSaving(true);
    setError(null);
    try {
      const slots: AvailabilityDaySlot[] = days
        .filter((d) => d.available)
        .map((d) => ({ date: formatDate(d.date), start_time: `${d.startTime}:00`, end_time: `${d.endTime}:00` }));
      await setEmployeeAvailability(employeeId, weekStartDateStr, slots);
      onSaved();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Failed to save");
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <p className="text-sm text-[var(--as-muted)]">Loading…</p>;

  return (
    <div className="flex flex-col gap-2">
      {days.map((day, idx) => (
        <div key={formatDate(day.date)} className="flex items-center gap-3">
          <label className="flex w-40 shrink-0 items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={day.available}
              onChange={(e) => updateDay(idx, { available: e.target.checked })}
            />
            {day.date.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" })}
          </label>
          {day.available && (
            <>
              <Input
                type="time"
                value={day.startTime}
                onChange={(e) => updateDay(idx, { startTime: e.target.value })}
                className="w-32"
              />
              <span className="text-xs text-[var(--as-muted)]">to</span>
              <Input
                type="time"
                value={day.endTime}
                onChange={(e) => updateDay(idx, { endTime: e.target.value })}
                className="w-32"
              />
            </>
          )}
        </div>
      ))}
      <ErrorText>{error}</ErrorText>
      <div className="mt-2">
        <Button disabled={saving} onClick={save}>
          {saving ? "Saving…" : "Save availability"}
        </Button>
      </div>
    </div>
  );
}
