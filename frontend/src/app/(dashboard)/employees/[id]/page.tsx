"use client";

import { useParams, useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { Badge, Button, Card, ErrorText, Input, Label, Select } from "@/components/ui/primitives";
import { ApiError } from "@/lib/apiFetch";
import {
  addAttendanceRecord,
  addEmployeeNote,
  assignEmployeeRole,
  deactivateEmployee,
  getEmployee,
  listRoles,
  listSkills,
  rateEmployeeSkill,
  removeEmployeeNote,
  removeEmployeeSkillRating,
  unassignEmployeeRole,
  updateEmployee,
} from "@/lib/scheduler-api";
import { ATTENDANCE_STATUSES, type EmployeeDetail, type Role, type Skill } from "@/lib/types";

const ATTENDANCE_LABELS: Record<string, string> = {
  on_time: "On time",
  late: "Late",
  no_show: "No-show",
  called_out: "Called out",
  left_early: "Left early",
};

export default function EmployeeDetailPage() {
  const params = useParams<{ id: string }>();
  const employeeId = Number(params.id);
  const router = useRouter();

  const [employee, setEmployee] = useState<EmployeeDetail | null>(null);
  const [roles, setRoles] = useState<Role[]>([]);
  const [skills, setSkills] = useState<Skill[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function refresh() {
    getEmployee(employeeId)
      .then(setEmployee)
      .catch((err) => setError(err instanceof ApiError ? String(err.detail) : "Failed to load employee"));
  }

  useEffect(() => {
    refresh();
    listRoles().then(setRoles).catch(() => {});
    listSkills().then(setSkills).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [employeeId]);

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

  if (error && !employee) {
    return <p className="text-sm text-red-400">{error}</p>;
  }
  if (!employee) {
    return <p className="text-sm text-[var(--as-muted)]">Loading…</p>;
  }

  const assignedRoleIds = new Set(employee.roles.map((r) => r.role_id));
  const assignableRoles = roles.filter((r) => !assignedRoleIds.has(r.id));
  const ratedSkillIds = new Set(employee.skill_ratings.map((s) => s.skill_id));
  const ratableSkills = skills.filter((s) => !ratedSkillIds.has(s.id));

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-medium">{employee.full_name}</h1>
          <p className="text-sm text-[var(--as-muted)]">{employee.phone_number}</p>
        </div>
        <div className="flex items-center gap-2">
          {!employee.is_active && <Badge tone="warning">Inactive</Badge>}
          {employee.is_active && (
            <Button
              variant="danger"
              disabled={busy}
              onClick={() =>
                withBusy(async () => {
                  await deactivateEmployee(employeeId);
                  router.push("/employees");
                })
              }
            >
              Deactivate
            </Button>
          )}
        </div>
      </div>

      <ErrorText>{error}</ErrorText>

      <EditBasicInfo
        employee={employee}
        busy={busy}
        onSave={(full_name, phone_number) =>
          withBusy(() => updateEmployee(employeeId, { full_name, phone_number }))
        }
      />

      <Card>
        <h2 className="mb-3 text-sm font-medium">Roles</h2>
        <div className="mb-3 flex flex-wrap gap-2">
          {employee.roles.length === 0 && <p className="text-sm text-[var(--as-muted)]">No roles assigned.</p>}
          {employee.roles.map((r) => (
            <span
              key={r.role_id}
              className="flex items-center gap-2 rounded bg-white/10 px-2 py-1 text-xs"
            >
              {r.role_name}
              {r.is_primary && <Badge tone="success">Primary</Badge>}
              <button
                className="text-[var(--as-muted)] hover:text-red-400"
                disabled={busy}
                onClick={() => withBusy(() => unassignEmployeeRole(employeeId, r.role_id))}
              >
                ✕
              </button>
            </span>
          ))}
        </div>
        {assignableRoles.length > 0 && (
          <AssignRoleForm
            roles={assignableRoles}
            busy={busy}
            onAssign={(roleId, isPrimary) => withBusy(() => assignEmployeeRole(employeeId, roleId, isPrimary))}
          />
        )}
      </Card>

      <Card>
        <h2 className="mb-3 text-sm font-medium">Skill ratings</h2>
        <div className="mb-3 flex flex-col gap-2">
          {employee.skill_ratings.length === 0 && (
            <p className="text-sm text-[var(--as-muted)]">No skills rated yet.</p>
          )}
          {employee.skill_ratings.map((s) => (
            <div key={s.skill_id} className="flex items-center justify-between text-sm">
              <span>
                {s.skill_name} — {"★".repeat(s.rating)}
                {"☆".repeat(5 - s.rating)}
                {s.notes && <span className="ml-2 text-xs text-[var(--as-muted)]">{s.notes}</span>}
              </span>
              <button
                className="text-[var(--as-muted)] hover:text-red-400"
                disabled={busy}
                onClick={() => withBusy(() => removeEmployeeSkillRating(employeeId, s.skill_id))}
              >
                Remove
              </button>
            </div>
          ))}
        </div>
        {ratableSkills.length > 0 && (
          <RateSkillForm
            skills={ratableSkills}
            busy={busy}
            onRate={(skillId, rating, notes) => withBusy(() => rateEmployeeSkill(employeeId, skillId, rating, notes))}
          />
        )}
      </Card>

      <Card>
        <h2 className="mb-3 text-sm font-medium">Manager notes</h2>
        <div className="mb-3 flex flex-col gap-2">
          {employee.notes.length === 0 && <p className="text-sm text-[var(--as-muted)]">No notes yet.</p>}
          {employee.notes.map((n) => (
            <div key={n.id} className="flex items-start justify-between gap-2 text-sm">
              <span>{n.note_text}</span>
              <button
                className="shrink-0 text-[var(--as-muted)] hover:text-red-400"
                disabled={busy}
                onClick={() => withBusy(() => removeEmployeeNote(employeeId, n.id))}
              >
                Remove
              </button>
            </div>
          ))}
        </div>
        <AddNoteForm busy={busy} onAdd={(text) => withBusy(() => addEmployeeNote(employeeId, text))} />
      </Card>

      <Card>
        <h2 className="mb-3 text-sm font-medium">Attendance history</h2>
        <div className="mb-3 flex flex-col gap-2">
          {employee.attendance.length === 0 && (
            <p className="text-sm text-[var(--as-muted)]">No attendance records yet.</p>
          )}
          {employee.attendance.map((a) => (
            <div key={a.id} className="flex items-center justify-between text-sm">
              <span>
                {ATTENDANCE_LABELS[a.status]}
                {a.minutes_late != null && ` (${a.minutes_late} min)`}
                {a.notes && <span className="ml-2 text-xs text-[var(--as-muted)]">{a.notes}</span>}
              </span>
              <span className="text-xs text-[var(--as-muted)]">
                {a.recorded_at ? new Date(a.recorded_at).toLocaleDateString() : ""}
              </span>
            </div>
          ))}
        </div>
        <AddAttendanceForm
          busy={busy}
          onAdd={(status, minutesLate, notes) =>
            withBusy(() => addAttendanceRecord(employeeId, { status, minutes_late: minutesLate, notes }))
          }
        />
      </Card>
    </div>
  );
}

function EditBasicInfo({
  employee,
  busy,
  onSave,
}: {
  employee: EmployeeDetail;
  busy: boolean;
  onSave: (fullName: string, phone: string) => void;
}) {
  const [name, setName] = useState(employee.full_name);
  const [phone, setPhone] = useState(employee.phone_number);
  const dirty = name !== employee.full_name || phone !== employee.phone_number;

  return (
    <Card>
      <h2 className="mb-3 text-sm font-medium">Basic info</h2>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
        <div className="flex-1">
          <Label>Full name</Label>
          <Input value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <div className="flex-1">
          <Label>Phone number</Label>
          <Input value={phone} onChange={(e) => setPhone(e.target.value)} />
        </div>
        <Button disabled={!dirty || busy} onClick={() => onSave(name, phone)}>
          Save
        </Button>
      </div>
    </Card>
  );
}

function AssignRoleForm({
  roles,
  busy,
  onAssign,
}: {
  roles: Role[];
  busy: boolean;
  onAssign: (roleId: number, isPrimary: boolean) => void;
}) {
  const [roleId, setRoleId] = useState(roles[0]?.id ?? 0);
  const [isPrimary, setIsPrimary] = useState(false);

  useEffect(() => {
    if (!roles.find((r) => r.id === roleId)) setRoleId(roles[0]?.id ?? 0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [roles]);

  return (
    <div className="flex items-end gap-2">
      <div className="flex-1">
        <Label>Assign a role</Label>
        <Select value={roleId} onChange={(e) => setRoleId(Number(e.target.value))}>
          {roles.map((r) => (
            <option key={r.id} value={r.id}>
              {r.name}
            </option>
          ))}
        </Select>
      </div>
      <label className="mb-1.5 flex items-center gap-1 text-xs text-[var(--as-muted)]">
        <input type="checkbox" checked={isPrimary} onChange={(e) => setIsPrimary(e.target.checked)} />
        Primary
      </label>
      <Button disabled={busy} onClick={() => onAssign(roleId, isPrimary)}>
        Assign
      </Button>
    </div>
  );
}

function RateSkillForm({
  skills,
  busy,
  onRate,
}: {
  skills: Skill[];
  busy: boolean;
  onRate: (skillId: number, rating: number, notes?: string) => void;
}) {
  const [skillId, setSkillId] = useState(skills[0]?.id ?? 0);
  const [rating, setRating] = useState(3);
  const [notes, setNotes] = useState("");

  useEffect(() => {
    if (!skills.find((s) => s.id === skillId)) setSkillId(skills[0]?.id ?? 0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [skills]);

  return (
    <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
      <div className="flex-1">
        <Label>Skill</Label>
        <Select value={skillId} onChange={(e) => setSkillId(Number(e.target.value))}>
          {skills.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </Select>
      </div>
      <div>
        <Label>Rating (1-5)</Label>
        <Select value={rating} onChange={(e) => setRating(Number(e.target.value))}>
          {[1, 2, 3, 4, 5].map((n) => (
            <option key={n} value={n}>
              {n}
            </option>
          ))}
        </Select>
      </div>
      <div className="flex-1">
        <Label>Notes (optional)</Label>
        <Input value={notes} onChange={(e) => setNotes(e.target.value)} />
      </div>
      <Button disabled={busy} onClick={() => onRate(skillId, rating, notes || undefined)}>
        Rate
      </Button>
    </div>
  );
}

function AddNoteForm({ busy, onAdd }: { busy: boolean; onAdd: (text: string) => void }) {
  const [text, setText] = useState("");
  function submit(e: FormEvent) {
    e.preventDefault();
    if (!text.trim()) return;
    onAdd(text.trim());
    setText("");
  }
  return (
    <form onSubmit={submit} className="flex items-end gap-2">
      <div className="flex-1">
        <Label>Add a note</Label>
        <Input value={text} onChange={(e) => setText(e.target.value)} placeholder="Great with difficult customers" />
      </div>
      <Button type="submit" disabled={busy || !text.trim()}>
        Add
      </Button>
    </form>
  );
}

function AddAttendanceForm({
  busy,
  onAdd,
}: {
  busy: boolean;
  onAdd: (status: string, minutesLate?: number, notes?: string) => void;
}) {
  const [status, setStatus] = useState<string>("on_time");
  const [minutesLate, setMinutesLate] = useState("");
  const [notes, setNotes] = useState("");

  function submit(e: FormEvent) {
    e.preventDefault();
    onAdd(status, minutesLate ? Number(minutesLate) : undefined, notes || undefined);
    setMinutesLate("");
    setNotes("");
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-2 sm:flex-row sm:items-end">
      <div className="flex-1">
        <Label>Status</Label>
        <Select value={status} onChange={(e) => setStatus(e.target.value)}>
          {ATTENDANCE_STATUSES.map((s) => (
            <option key={s} value={s}>
              {ATTENDANCE_LABELS[s]}
            </option>
          ))}
        </Select>
      </div>
      {status === "late" && (
        <div className="w-28">
          <Label>Minutes late</Label>
          <Input type="number" min={0} value={minutesLate} onChange={(e) => setMinutesLate(e.target.value)} />
        </div>
      )}
      <div className="flex-1">
        <Label>Notes (optional)</Label>
        <Input value={notes} onChange={(e) => setNotes(e.target.value)} />
      </div>
      <Button type="submit" disabled={busy}>
        Record
      </Button>
    </form>
  );
}
