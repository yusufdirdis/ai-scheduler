import Link from "next/link";

export default function Home() {
  return (
    <main className="flex flex-1 flex-col items-center justify-center gap-4 px-6 text-center">
      <h1 className="text-2xl font-medium">ai-scheduler</h1>
      <p className="max-w-md text-sm text-[var(--as-muted)]">
        AI-optimized, SMS-driven employee scheduling.
      </p>
      <Link
        href="/dashboard"
        className="rounded-md bg-[var(--as-accent)] px-4 py-2 text-sm font-medium text-black hover:opacity-90"
      >
        Open manager dashboard
      </Link>
    </main>
  );
}
