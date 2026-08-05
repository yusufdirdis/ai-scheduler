import { createClient, type SupabaseClient } from "@supabase/supabase-js";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

// Until a real Supabase project is wired up (NEXT_PUBLIC_SUPABASE_URL/ANON_KEY
// set), `supabase` is null and apiFetch simply omits the auth header — the
// backend's AUTH_DISABLED dev bypass covers local development in that case.
export const supabase: SupabaseClient | null =
  supabaseUrl && supabaseAnonKey ? createClient(supabaseUrl, supabaseAnonKey) : null;

export const supabaseConfigured = supabase !== null;
