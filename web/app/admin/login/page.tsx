import { redirect } from "next/navigation"
import { createSupabaseServerClient } from "@/lib/supabase/server"

export default async function AdminLoginPage({
  searchParams,
}: {
  searchParams: Promise<{ error?: string }>
}) {
  const { error } = await searchParams

  async function login(formData: FormData) {
    "use server"
    const email = formData.get("email") as string
    const password = formData.get("password") as string
    const supabase = await createSupabaseServerClient()
    const { error: authError } = await supabase.auth.signInWithPassword({ email, password })
    if (authError) {
      redirect(`/admin/login?error=${encodeURIComponent(authError.message)}`)
    }
    redirect("/admin/schedule")
  }

  return (
    <main className="flex min-h-screen items-center justify-center px-6">
      <div className="w-full max-w-sm">
        <img src="/logo_cropped.png" alt="Vance Archives" className="mb-8 h-12 w-auto" />
        <p className="mb-2 text-[0.7rem] tracking-[0.3em] uppercase text-accent">Admin</p>
        <h1 className="mb-6 font-serif text-3xl text-foreground">Sign in</h1>
        <form action={login} className="space-y-4">
          <input
            type="email"
            name="email"
            required
            placeholder="Email"
            className="w-full rounded-sm border border-line bg-surface px-4 py-3 text-sm text-foreground outline-none focus:border-accent"
          />
          <input
            type="password"
            name="password"
            required
            placeholder="Password"
            className="w-full rounded-sm border border-line bg-surface px-4 py-3 text-sm text-foreground outline-none focus:border-accent"
          />
          {error && <p className="text-sm text-red-500">{decodeURIComponent(error)}</p>}
          <button
            type="submit"
            className="w-full border border-foreground py-3 text-[0.7rem] tracking-[0.28em] uppercase text-foreground transition-colors hover:border-accent hover:bg-accent hover:text-surface"
          >
            Sign in
          </button>
        </form>
      </div>
    </main>
  )
}
