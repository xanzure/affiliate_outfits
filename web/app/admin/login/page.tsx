"use client"

import { useState } from "react"
import { createSupabaseBrowserClient } from "@/lib/supabase/client"

export default function AdminLoginPage() {
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function signIn(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      const supabase = createSupabaseBrowserClient()
      const { data, error } = await supabase.auth.signInWithPassword({ email, password })
      if (error) {
        setLoading(false)
        setError(error.message)
      } else if (data.session) {
        window.location.href = "/admin/schedule"
      } else {
        setLoading(false)
        setError("No session returned — check Supabase config.")
      }
    } catch (err) {
      setLoading(false)
      setError(String(err))
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center px-6">
      <div className="w-full max-w-sm">
        <img src="/logo_cropped.png" alt="Vance Archives" className="mb-8 h-12 w-auto" />
        <p className="mb-2 text-[0.7rem] tracking-[0.3em] uppercase text-accent">Admin</p>
        <h1 className="mb-6 font-serif text-3xl text-foreground">Sign in</h1>
        <form onSubmit={signIn} className="space-y-4">
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="Email"
            className="w-full rounded-sm border border-line bg-surface px-4 py-3 text-sm text-foreground outline-none focus:border-accent"
          />
          <input
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Password"
            className="w-full rounded-sm border border-line bg-surface px-4 py-3 text-sm text-foreground outline-none focus:border-accent"
          />
          {error && <p className="text-sm text-red-500">{error}</p>}
          <button
            type="submit"
            disabled={loading}
            className="w-full border border-foreground py-3 text-[0.7rem] tracking-[0.28em] uppercase text-foreground transition-colors hover:border-accent hover:bg-accent hover:text-surface disabled:opacity-50"
          >
            {loading ? "Signing in…" : "Sign in"}
          </button>
        </form>
      </div>
    </main>
  )
}
