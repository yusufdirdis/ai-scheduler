"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { Badge, Button, Card, ErrorText, Input, Label } from "@/components/ui/primitives";
import { ApiError } from "@/lib/apiFetch";
import { createEmployee, listEmployees } from "@/lib/scheduler-api";
import type { EmployeeSummary } from "@/lib/types";

export default function EmployeesPage() {
  const [employees, setEmployees] = useState<EmployeeSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  function refresh() {
    setLoading(true);
    listEmployees()
      .then(setEmployees)
      .catch((err) => setError(err.message ?? "Failed to load employees"))
      .finally(() => setLoading(false));
  }

  useEffect(refresh, []);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await createEmployee({ full_name: name, phone_number: phone });
      setName("");
      setPhone("");
      setShowForm(false);
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Failed to create employee");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-medium">Employees</h1>
        <Button onClick={() => setShowForm((v) => !v)}>{showForm ? "Cancel" : "Add employee"}</Button>
      </div>

      {showForm && (
        <Card>
          <form onSubmit={handleSubmit} className="flex flex-col gap-3 sm:flex-row sm:items-end">
            <div className="flex-1">
              <Label>Full name</Label>
              <Input value={name} onChange={(e) => setName(e.target.value)} required placeholder="Alex Rivera" />
            </div>
            <div className="flex-1">
              <Label>Phone number (E.164)</Label>
              <Input
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                required
                placeholder="+15551234567"
              />
            </div>
            <Button type="submit" disabled={submitting}>
              {submitting ? "Adding…" : "Add"}
            </Button>
          </form>
          <div className="mt-2">
            <ErrorText>{error}</ErrorText>
          </div>
        </Card>
      )}

      {loading ? (
        <p className="text-sm text-[var(--as-muted)]">Loading…</p>
      ) : employees.length === 0 ? (
        <Card>
          <p className="text-sm text-[var(--as-muted)]">No employees yet. Add your first one above.</p>
        </Card>
      ) : (
        <div className="flex flex-col divide-y divide-[var(--as-border)] overflow-hidden rounded-lg border border-[var(--as-border)]">
          {employees.map((emp) => (
            <Link
              key={emp.id}
              href={`/employees/${emp.id}`}
              className="flex items-center justify-between bg-[var(--as-surface)] px-4 py-3 transition-colors hover:bg-white/5"
            >
              <div>
                <p className="text-sm font-medium">{emp.full_name}</p>
                <p className="text-xs text-[var(--as-muted)]">{emp.phone_number}</p>
              </div>
              <div className="flex items-center gap-2">
                {emp.roles.map((r) => (
                  <Badge key={r}>{r}</Badge>
                ))}
                {!emp.is_active && <Badge tone="warning">Inactive</Badge>}
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
