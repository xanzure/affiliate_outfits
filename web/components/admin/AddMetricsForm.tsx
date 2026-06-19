"use client"

import { useState } from "react"
import { addMetrics } from "@/app/admin/(dashboard)/metrics/actions"

const FIELDS = ["views", "likes", "comments", "shares", "saves", "clicks"]

export default function AddMetricsForm({
  postOptions,
}: {
  postOptions: { id: string; label: string }[]
}) {
  const [open, setOpen] = useState(false)

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="rounded-sm border border-line px-3 py-2 text-xs uppercase tracking-wider text-foreground hover:border-accent hover:text-accent"
      >
        + Add metrics
      </button>
    )
  }

  return (
    <form
      action={addMetrics}
      className="rounded-sm border border-line bg-surface p-4"
      onSubmit={() => setTimeout(() => setOpen(false), 100)}
    >
      <div className="mb-3">
        <label className="mb-1 block text-[0.65rem] uppercase tracking-wider text-muted">Post</label>
        <select
          name="post_id"
          required
          className="w-full rounded-sm border border-line bg-background px-2 py-1.5 text-sm"
        >
          <option value="">Select a post…</option>
          {postOptions.map((o) => (
            <option key={o.id} value={o.id}>
              {o.label}
            </option>
          ))}
        </select>
      </div>
      <div className="grid grid-cols-3 gap-2">
        {FIELDS.map((f) => (
          <label key={f} className="text-[0.65rem] uppercase tracking-wider text-muted">
            {f}
            <input
              type="number"
              name={f}
              min={0}
              defaultValue={0}
              className="mt-1 w-full rounded-sm border border-line bg-background px-2 py-1 text-sm text-foreground"
            />
          </label>
        ))}
      </div>
      <div className="mt-3 flex gap-2">
        <button className="rounded-sm bg-accent px-3 py-1.5 text-xs uppercase tracking-wider text-surface">
          Save
        </button>
        <button type="button" onClick={() => setOpen(false)} className="px-3 py-1.5 text-xs uppercase tracking-wider text-muted">
          Cancel
        </button>
      </div>
    </form>
  )
}
