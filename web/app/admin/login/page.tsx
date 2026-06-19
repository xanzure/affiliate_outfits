"use client"

import { useState } from "react"
import { createSupabaseBrowserClient } from "@/lib/supabase/client"

export default function AdminLoginPage() {
  const [email, setEmail] = useState("")
  const [sent, setSent] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function sendLink(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError(null)
    const supabase = createSupabaseBrowserClient()
    const { error } = await supabase.auth.signInWithOtp({
      email,
      options: { emailRedirectTo: `${window.location.origin}/auth/callback` },
    })
    setLoading(false)
    if (error) setError(error.message)
    else setSent(true)
  }

  return (
    <main className="flex min-h-screen items-center justify-center px-6">
      <div className="w-full max-w-sm">
        <img src="/logo_cropped.png" alt="Vance Archives" className="mb-8 h-12 w-auto" />
        <p className="mb-2 text-[0.7rem] tracking-[0.3em] uppercase text-accent">
          Admin
        </p>
        <h1 className="mb-6 font-serif text-3xl text-foreground">Sign in</h1>

        {sent ? (
          <p className="text-sm text-muted">
            Check <span className="text-foreground">{email}</span> for a magic link.
          </p>
        ) : (
          <form onSubmit={sendLink} className="space-y-4">
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              className="w-full rounded-sm border border-line bg-surface px-4 py-3 text-sm text-foreground outline-none focus:border-accent"
            />
            {error && <p className="text-sm text-red-600">{error}</p>}
            <button
              type="submit"
              disabled={loading}
              className="w-full border border-foreground py-3 text-[0.7rem] tracking-[0.28em] uppercase text-foreground transition-colors hover:border-accent hover:bg-accent hover:text-surface disabled:opacity-50"
            >
              {loading ? "Sending…" : "Send magic link"}
            </button>
          </form>
        )}
      </div>
    </main>
  )
}
