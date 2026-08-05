"use client";

import { FormEvent, useState } from "react";
import { Button, Card, ErrorText, Input, Label } from "@/components/ui/primitives";
import { supabase, supabaseConfigured } from "@/lib/supabase";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!supabase) return;
    setBusy(true);
    setError(null);
    const { error: authError } = await supabase.auth.signInWithOtp({ email });
    setBusy(false);
    if (authError) {
      setError(authError.message);
    } else {
      setSent(true);
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-sm flex-1 flex-col justify-center px-6">
      <Card>
        <h1 className="mb-1 text-lg font-medium">Sign in</h1>
        <p className="mb-4 text-sm text-[var(--as-muted)]">Manager access to your ai-scheduler dashboard.</p>

        {!supabaseConfigured ? (
          <p className="text-sm text-amber-400">
            Supabase isn&apos;t configured yet (NEXT_PUBLIC_SUPABASE_URL / NEXT_PUBLIC_SUPABASE_ANON_KEY are
            unset). The dashboard is reachable directly while the backend runs with AUTH_DISABLED=true for
            local development.
          </p>
        ) : sent ? (
          <p className="text-sm text-emerald-400">Check {email} for a sign-in link.</p>
        ) : (
          <form onSubmit={handleSubmit} className="flex flex-col gap-3">
            <div>
              <Label>Email</Label>
              <Input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@business.com"
              />
            </div>
            <ErrorText>{error}</ErrorText>
            <Button type="submit" disabled={busy}>
              {busy ? "Sending…" : "Send sign-in link"}
            </Button>
          </form>
        )}
      </Card>
    </div>
  );
}
