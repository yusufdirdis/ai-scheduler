"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Card } from "@/components/ui/primitives";
import { getBusiness, listEmployees, listShiftTemplates } from "@/lib/scheduler-api";
import type { Business, EmployeeSummary, ShiftTemplate } from "@/lib/types";

export default function DashboardPage() {
  const [business, setBusiness] = useState<Business | null>(null);
  const [employees, setEmployees] = useState<EmployeeSummary[]>([]);
  const [templates, setTemplates] = useState<ShiftTemplate[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([getBusiness(), listEmployees(), listShiftTemplates()])
      .then(([b, e, t]) => {
        setBusiness(b);
        setEmployees(e);
        setTemplates(t);
      })
      .catch((err) => setError(err.message ?? "Failed to load"));
  }, []);

  const activeEmployees = employees.filter((e) => e.is_active);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-medium">{business?.name ?? "Loading…"}</h1>
        <p className="text-sm text-[var(--as-muted)]">
          {business?.location_name ?? "No location set"} · {business?.business_type}
        </p>
      </div>

      {error && <p className="text-sm text-red-400">{error}</p>}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Link href="/employees">
          <Card className="transition-colors hover:border-white/30">
            <p className="text-xs text-[var(--as-muted)]">Active employees</p>
            <p className="mt-1 text-2xl font-medium">{activeEmployees.length}</p>
          </Card>
        </Link>
        <Link href="/coverage">
          <Card className="transition-colors hover:border-white/30">
            <p className="text-xs text-[var(--as-muted)]">Shift templates</p>
            <p className="mt-1 text-2xl font-medium">{templates.length}</p>
          </Card>
        </Link>
        <Link href="/labor-rules">
          <Card className="transition-colors hover:border-white/30">
            <p className="text-xs text-[var(--as-muted)]">Settings</p>
            <p className="mt-1 text-sm text-[var(--as-muted)]">Labor rules &amp; business info</p>
          </Card>
        </Link>
      </div>

      <Card>
        <p className="text-sm text-[var(--as-muted)]">
          Availability collection, AI schedule building, and SMS delivery come online in later
          phases. For now: manage employees, roles, skills, and coverage requirements here.
        </p>
      </Card>
    </div>
  );
}
