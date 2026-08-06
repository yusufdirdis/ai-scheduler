/** Mirrors backend/services/weeks.py — 0=Monday..6=Sunday throughout. */

function toWeekday(d: Date): number {
  const jsDay = d.getDay(); // 0=Sunday..6=Saturday
  return (jsDay + 6) % 7; // 0=Monday..6=Sunday
}

export function formatDate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export function parseDate(s: string): Date {
  const [y, m, d] = s.split("-").map(Number);
  return new Date(y, m - 1, d);
}

export function weekStartOnOrBefore(reference: Date, weekStartDay: number): Date {
  const delta = (toWeekday(reference) - weekStartDay + 7) % 7;
  const result = new Date(reference);
  result.setDate(result.getDate() - delta);
  return result;
}

export function addDays(d: Date, days: number): Date {
  const result = new Date(d);
  result.setDate(result.getDate() + days);
  return result;
}

export function weekDates(weekStart: Date): Date[] {
  return Array.from({ length: 7 }, (_, i) => addDays(weekStart, i));
}

export function formatWeekRange(weekStart: Date): string {
  const end = addDays(weekStart, 6);
  const opts: Intl.DateTimeFormatOptions = { month: "short", day: "numeric" };
  return `${weekStart.toLocaleDateString(undefined, opts)} – ${end.toLocaleDateString(undefined, opts)}`;
}
