"use client";

import { useEffect, useState } from "react";
import { Button, Card, ErrorText, Input, Label, Select } from "@/components/ui/primitives";
import { ApiError } from "@/lib/apiFetch";
import { getBusiness, getLaborRules, updateBusiness, updateLaborRules } from "@/lib/scheduler-api";
import { DAYS_OF_WEEK, type Business, type LaborRules } from "@/lib/types";

export default function LaborRulesPage() {
  const [business, setBusiness] = useState<Business | null>(null);
  const [laborRules, setLaborRules] = useState<LaborRules | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    Promise.all([getBusiness(), getLaborRules()])
      .then(([b, r]) => {
        setBusiness(b);
        setLaborRules(r);
      })
      .catch((err) => setError(err.message ?? "Failed to load settings"));
  }, []);

  async function saveBusiness(patch: Partial<Business>) {
    setBusy(true);
    setError(null);
    setSaved(null);
    try {
      const updated = await updateBusiness(patch);
      setBusiness(updated);
      setSaved("Saved");
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Failed to save");
    } finally {
      setBusy(false);
    }
  }

  async function saveLaborRules(patch: Partial<LaborRules>) {
    setBusy(true);
    setError(null);
    setSaved(null);
    try {
      const updated = await updateLaborRules(patch);
      setLaborRules(updated);
      setSaved("Saved");
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Failed to save");
    } finally {
      setBusy(false);
    }
  }

  if (!business || !laborRules) {
    return <p className="text-sm text-[var(--as-muted)]">{error ?? "Loading…"}</p>;
  }

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-xl font-medium">Settings</h1>
      <ErrorText>{error}</ErrorText>
      {saved && <p className="text-xs text-emerald-400">{saved}</p>}

      <BusinessInfoForm business={business} busy={busy} onSave={saveBusiness} />
      <AvailabilityScheduleForm business={business} busy={busy} onSave={saveBusiness} />
      <LaborRulesForm laborRules={laborRules} busy={busy} onSave={saveLaborRules} />
    </div>
  );
}

function BusinessInfoForm({
  business,
  busy,
  onSave,
}: {
  business: Business;
  busy: boolean;
  onSave: (patch: Partial<Business>) => void;
}) {
  const [name, setName] = useState(business.name);
  const [timezone, setTimezone] = useState(business.timezone);
  const [locationName, setLocationName] = useState(business.location_name ?? "");
  const [address, setAddress] = useState(business.address ?? "");

  return (
    <Card>
      <h2 className="mb-3 text-sm font-medium">Business info</h2>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div>
          <Label>Business name</Label>
          <Input value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <div>
          <Label>Timezone (IANA)</Label>
          <Input value={timezone} onChange={(e) => setTimezone(e.target.value)} placeholder="America/New_York" />
        </div>
        <div>
          <Label>Location name</Label>
          <Input value={locationName} onChange={(e) => setLocationName(e.target.value)} />
        </div>
        <div>
          <Label>Address</Label>
          <Input value={address} onChange={(e) => setAddress(e.target.value)} />
        </div>
      </div>
      <div className="mt-3">
        <Button
          disabled={busy}
          onClick={() =>
            onSave({ name, timezone, location_name: locationName || null, address: address || null })
          }
        >
          Save business info
        </Button>
      </div>
    </Card>
  );
}

function AvailabilityScheduleForm({
  business,
  busy,
  onSave,
}: {
  business: Business;
  busy: boolean;
  onSave: (patch: Partial<Business>) => void;
}) {
  const [weekStartDay, setWeekStartDay] = useState(business.week_start_day);
  const [requestDay, setRequestDay] = useState(business.availability_request_day_of_week);
  const [requestTime, setRequestTime] = useState(business.availability_request_time);

  return (
    <Card>
      <h2 className="mb-3 text-sm font-medium">Availability requests</h2>
      <p className="mb-3 text-xs text-[var(--as-muted)]">
        Controls the recurring weekly SMS ask (wired up in a later phase) — set the cadence now.
      </p>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <div>
          <Label>Week starts on</Label>
          <Select value={weekStartDay} onChange={(e) => setWeekStartDay(Number(e.target.value))}>
            {DAYS_OF_WEEK.map((d, i) => (
              <option key={d} value={i}>
                {d}
              </option>
            ))}
          </Select>
        </div>
        <div>
          <Label>Request availability on</Label>
          <Select value={requestDay} onChange={(e) => setRequestDay(Number(e.target.value))}>
            {DAYS_OF_WEEK.map((d, i) => (
              <option key={d} value={i}>
                {d}
              </option>
            ))}
          </Select>
        </div>
        <div>
          <Label>At time (HH:MM, business-local)</Label>
          <Input value={requestTime} onChange={(e) => setRequestTime(e.target.value)} placeholder="09:00" />
        </div>
      </div>
      <div className="mt-3">
        <Button
          disabled={busy}
          onClick={() =>
            onSave({
              week_start_day: weekStartDay,
              availability_request_day_of_week: requestDay,
              availability_request_time: requestTime,
            })
          }
        >
          Save schedule
        </Button>
      </div>
    </Card>
  );
}

function LaborRulesForm({
  laborRules,
  busy,
  onSave,
}: {
  laborRules: LaborRules;
  busy: boolean;
  onSave: (patch: Partial<LaborRules>) => void;
}) {
  const [otThreshold, setOtThreshold] = useState(String(laborRules.weekly_overtime_threshold_hours));
  const [minRest, setMinRest] = useState(String(laborRules.min_rest_hours_between_shifts));

  return (
    <Card>
      <h2 className="mb-3 text-sm font-medium">Labor rules</h2>
      <p className="mb-3 text-xs text-[var(--as-muted)]">
        Hard constraints the AI schedule builder will never violate.
      </p>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div>
          <Label>Weekly overtime threshold (hours)</Label>
          <Input type="number" min={1} step="0.5" value={otThreshold} onChange={(e) => setOtThreshold(e.target.value)} />
        </div>
        <div>
          <Label>Minimum rest between shifts (hours)</Label>
          <Input type="number" min={0} step="0.5" value={minRest} onChange={(e) => setMinRest(e.target.value)} />
        </div>
      </div>
      <div className="mt-3">
        <Button
          disabled={busy}
          onClick={() =>
            onSave({
              weekly_overtime_threshold_hours: Number(otThreshold),
              min_rest_hours_between_shifts: Number(minRest),
            })
          }
        >
          Save labor rules
        </Button>
      </div>
    </Card>
  );
}
