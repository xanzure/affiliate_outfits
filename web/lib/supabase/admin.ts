import { createClient } from "@supabase/supabase-js"

/**
 * Service-role Supabase client for server-only admin writes.
 * NEVER import this into a client component — it holds the service role key.
 */
export function createAdminClient() {
  return createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SERVICE_ROLE_KEY!,
    { auth: { persistSession: false, autoRefreshToken: false } }
  )
}
