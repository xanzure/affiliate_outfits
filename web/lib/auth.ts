import { createSupabaseServerClient } from "@/lib/supabase/server"

export function adminEmails(): string[] {
  return (process.env.ADMIN_EMAILS ?? "")
    .split(",")
    .map((e) => e.trim().toLowerCase())
    .filter(Boolean)
}

/** Local-dev convenience only — gated to non-production + explicit env flag. */
export function devBypass(): boolean {
  return (
    process.env.NODE_ENV !== "production" &&
    process.env.ADMIN_DEV_BYPASS === "true"
  )
}

export function isAllowedEmail(email: string | null | undefined): boolean {
  if (!email) return false
  return adminEmails().includes(email.toLowerCase())
}

/** Returns the signed-in admin user, or null if not authenticated/allowed. */
export async function getAdminUser() {
  if (devBypass()) {
    return { email: adminEmails()[0] ?? "dev@local", id: "dev-bypass" }
  }
  const supabase = await createSupabaseServerClient()
  const {
    data: { user },
  } = await supabase.auth.getUser()
  if (!user || !isAllowedEmail(user.email)) return null
  return user
}
