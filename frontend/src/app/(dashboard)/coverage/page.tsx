"use client";

import { FormEvent, useEffect, useState } from "react";
import { Button, Card, ErrorText, Input, Label, Select } from "@/components/ui/primitives";
import { ApiError } from "@/lib/apiFetch";
import {
  createRole,
  createShiftTemplate,
  createSkill,
  deleteRole,
  deleteShiftTemplate,
  deleteSkill,
  listRoles,
  listShiftTemplates,
  listSkills,
} from "@/lib/scheduler-api";
import { DAYS_OF_WEEK, type Role, type ShiftTemplate, type Skill } from "@/lib/types";

export default function CoveragePage() {
  const [roles, setRoles] = useState<Role[]>([]);
  const [skills, setSkills] = useState<Skill[]>([]);
  const [templates, setTemplates] = useState<ShiftTemplate[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function refresh() {
    Promise.all([listRoles(), listSkills(), listShiftTemplates()])
      .then(([r, s, t]) => {
        setRoles(r);
        setSkills(s);
        setTemplates(t);
      })
      .catch((err) => setError(err.message ?? "Failed to load"));
  }

  useEffect(refresh, []);

  async function withBusy(fn: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await fn();
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-xl font-medium">Coverage</h1>
      <ErrorText>{error}</ErrorText>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <TaxonomyCard
          title="Roles"
          items={roles}
          busy={busy}
          placeholder="e.g. Cook"
          onCreate={(name) => withBusy(() => createRole(name))}
          onDelete={(id) => withBusy(() => deleteRole(id))}
        />
        <TaxonomyCard
          title="Skills"
          items={skills}
          busy={busy}
          placeholder="e.g. Grill Station"
          onCreate={(name) => withBusy(() => createSkill(name))}
          onDelete={(id) => withBusy(() => deleteSkill(id))}
        />
      </div>

      <Card>
        <h2 className="mb-3 text-sm font-medium">Shift templates</h2>
        <div className="mb-4 flex flex-col divide-y divide-[var(--as-border)]">
          {templates.length === 0 && (
            <p className="py-2 text-sm text-[var(--as-muted)]">No shift templates yet — add one below.</p>
          )}
          {templates.map((t) => (
            <div key={t.id} className="flex items-center justify-between py-2">
              <div>
                <p className="text-sm font-medium">
                  {t.name || DAYS_OF_WEEK[t.day_of_week]} · {DAYS_OF_WEEK[t.day_of_week]} {t.start_time}–{t.end_time}
                </p>
                <p className="text-xs text-[var(--as-muted)]">
                  {t.requirements
                    .map((r) => `${r.count_required}× ${roles.find((role) => role.id === r.role_id)?.name ?? "?"}`)
                    .join(", ") || "No requirements set"}
                </p>
              </div>
              <button
                className="text-xs text-[var(--as-muted)] hover:text-red-400"
                disabled={busy}
                onClick={() => withBusy(() => deleteShiftTemplate(t.id))}
              >
                Remove
              </button>
            </div>
          ))}
        </div>
        <NewShiftTemplateForm
          roles={roles}
          busy={busy || roles.length === 0}
          onCreate={(payload) => withBusy(() => createShiftTemplate(payload))}
        />
        {roles.length === 0 && (
          <p className="mt-2 text-xs text-[var(--as-muted)]">Add at least one role before creating shift templates.</p>
        )}
      </Card>
    </div>
  );
}

function TaxonomyCard({
  title,
  items,
  busy,
  placeholder,
  onCreate,
  onDelete,
}: {
  title: string;
  items: { id: number; name: string }[];
  busy: boolean;
  placeholder: string;
  onCreate: (name: string) => void;
  onDelete: (id: number) => void;
}) {
  const [name, setName] = useState("");

  function submit(e: FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    onCreate(name.trim());
    setName("");
  }

  return (
    <Card>
      <h2 className="mb-3 text-sm font-medium">{title}</h2>
      <div className="mb-3 flex flex-wrap gap-2">
        {items.length === 0 && <p className="text-sm text-[var(--as-muted)]">None yet.</p>}
        {items.map((item) => (
          <span key={item.id} className="flex items-center gap-1.5 rounded bg-white/10 px-2 py-1 text-xs">
            {item.name}
            <button className="text-[var(--as-muted)] hover:text-red-400" disabled={busy} onClick={() => onDelete(item.id)}>
              ✕
            </button>
          </span>
        ))}
      </div>
      <form onSubmit={submit} className="flex gap-2">
        <Input value={name} onChange={(e) => setName(e.target.value)} placeholder={placeholder} />
        <Button type="submit" disabled={busy || !name.trim()}>
          Add
        </Button>
      </form>
    </Card>
  );
}

interface RequirementRow {
  role_id: number;
  count_required: number;
}

function NewShiftTemplateForm({
  roles,
  busy,
  onCreate,
}: {
  roles: Role[];
  busy: boolean;
  onCreate: (payload: {
    name?: string;
    day_of_week: number;
    start_time: string;
    end_time: string;
    requirements: RequirementRow[];
  }) => void;
}) {
  const [name, setName] = useState("");
  const [dayOfWeek, setDayOfWeek] = useState(4);
  const [startTime, setStartTime] = useState("17:00");
  const [endTime, setEndTime] = useState("22:00");
  const [requirements, setRequirements] = useState<RequirementRow[]>([]);
  const [formError, setFormError] = useState<string | null>(null);

  function addRequirementRow() {
    if (roles.length === 0) return;
    setRequirements((prev) => [...prev, { role_id: roles[0].id, count_required: 1 }]);
  }

  function updateRow(idx: number, patch: Partial<RequirementRow>) {
    setRequirements((prev) => prev.map((r, i) => (i === idx ? { ...r, ...patch } : r)));
  }

  function removeRow(idx: number) {
    setRequirements((prev) => prev.filter((_, i) => i !== idx));
  }

  function submit(e: FormEvent) {
    e.preventDefault();
    setFormError(null);
    if (endTime <= startTime) {
      setFormError("End time must be after start time");
      return;
    }
    onCreate({
      name: name || undefined,
      day_of_week: dayOfWeek,
      start_time: `${startTime}:00`,
      end_time: `${endTime}:00`,
      requirements,
    });
    setName("");
    setRequirements([]);
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-3 border-t border-[var(--as-border)] pt-4">
      <div className="flex flex-col gap-3 sm:flex-row">
        <div className="flex-1">
          <Label>Name (optional)</Label>
          <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Friday Dinner" />
        </div>
        <div className="flex-1">
          <Label>Day</Label>
          <Select value={dayOfWeek} onChange={(e) => setDayOfWeek(Number(e.target.value))}>
            {DAYS_OF_WEEK.map((d, i) => (
              <option key={d} value={i}>
                {d}
              </option>
            ))}
          </Select>
        </div>
        <div>
          <Label>Start</Label>
          <Input type="time" value={startTime} onChange={(e) => setStartTime(e.target.value)} />
        </div>
        <div>
          <Label>End</Label>
          <Input type="time" value={endTime} onChange={(e) => setEndTime(e.target.value)} />
        </div>
      </div>

      <div className="flex flex-col gap-2">
        <Label>Coverage requirements</Label>
        {requirements.map((req, idx) => (
          <div key={idx} className="flex items-center gap-2">
            <Select
              value={req.role_id}
              onChange={(e) => updateRow(idx, { role_id: Number(e.target.value) })}
              className="flex-1"
            >
              {roles.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.name}
                </option>
              ))}
            </Select>
            <Input
              type="number"
              min={1}
              value={req.count_required}
              onChange={(e) => updateRow(idx, { count_required: Number(e.target.value) })}
              className="w-20"
            />
            <button
              type="button"
              className="text-xs text-[var(--as-muted)] hover:text-red-400"
              onClick={() => removeRow(idx)}
            >
              ✕
            </button>
          </div>
        ))}
        <Button type="button" variant="secondary" onClick={addRequirementRow} disabled={roles.length === 0}>
          + Add requirement
        </Button>
      </div>

      <ErrorText>{formError}</ErrorText>
      <div>
        <Button type="submit" disabled={busy}>
          Create shift template
        </Button>
      </div>
    </form>
  );
}
