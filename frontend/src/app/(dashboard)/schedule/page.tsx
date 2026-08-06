"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Badge, Button, Card, ErrorText } from "@/components/ui/primitives";
import { ApiError } from "@/lib/apiFetch";
import { createSchedule, getBusiness, listSchedules } from "@/lib/scheduler-api";
import type { ScheduleStatus, ScheduleSummary } from "@/lib/types";
import { formatDate, weekStartOnOrBefore } from "@/lib/weeks";

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

export default function SchedulesPage() {
  const [schedules, setSchedules] = useState<ScheduleSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  function refresh() {
    setLoading(true);
    listSchedules()
      .then(setSchedules)
      .catch((err) => setError(err.message ?? "Failed to load schedules"))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    // refresh() toggles the loading flag before an async fetch — an intentional,
    // safe re-render, not the unbounded cascading-render pattern this rule targets.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    refresh();
  }, []);

  async function createForCurrentWeek() {
    setCreating(true);
    setError(null);
    try {
      const business = await getBusiness();
      const weekStart = weekStartOnOrBefore(new Date(), business.week_start_day);
      const schedule = await createSchedule(formatDate(weekStart));
      window.location.href = `/schedule/${schedule.id}`;
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Failed to create schedule");
      setCreating(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-medium">Schedules</h1>
        <Button disabled={creating} onClick={createForCurrentWeek}>
          {creating ? "Creating…" : "New schedule (this week)"}
        </Button>
      </div>

      <ErrorText>{error}</ErrorText>

      {loading ? (
        <p className="text-sm text-[var(--as-muted)]">Loading…</p>
      ) : schedules.length === 0 ? (
        <Card>
          <p className="text-sm text-[var(--as-muted)]">
            No schedules yet. Create one for the current week to expand your shift templates into fillable slots.
          </p>
        </Card>
      ) : (
        <div className="flex flex-col divide-y divide-[var(--as-border)] overflow-hidden rounded-lg border border-[var(--as-border)]">
          {schedules.map((s) => (
            <Link
              key={s.id}
              href={`/schedule/${s.id}`}
              className="flex items-center justify-between bg-[var(--as-surface)] px-4 py-3 transition-colors hover:bg-white/5"
            >
              <div>
                <p className="text-sm font-medium">Week of {s.week_start_date}</p>
                <p className="text-xs text-[var(--as-muted)]">
                  {s.unfilled_slot_count > 0 ? `${s.unfilled_slot_count} slot(s) unfilled` : "Fully staffed"}
                </p>
              </div>
              <Badge tone={STATUS_TONE[s.status]}>{STATUS_LABELS[s.status]}</Badge>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
