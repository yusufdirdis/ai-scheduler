import Link from "next/link";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Overview" },
  { href: "/employees", label: "Employees" },
  { href: "/coverage", label: "Coverage" },
  { href: "/availability", label: "Availability" },
  { href: "/labor-rules", label: "Settings" },
];

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="mx-auto flex w-full max-w-5xl flex-1 flex-col px-6 py-6">
      <header className="mb-8 flex items-center justify-between">
        <Link href="/dashboard" className="text-sm font-medium tracking-tight">
          ai-scheduler
        </Link>
        <nav className="flex gap-1">
          {NAV_ITEMS.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="rounded-md px-3 py-1.5 text-sm text-[var(--as-muted)] transition-colors hover:bg-white/5 hover:text-[var(--as-accent)]"
            >
              {item.label}
            </Link>
          ))}
        </nav>
      </header>
      <main className="flex-1">{children}</main>
    </div>
  );
}
