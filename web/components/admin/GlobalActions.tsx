"use client"

import Link from "next/link"
import { useState, useTransition } from "react"
import { enqueueJob } from "@/app/admin/(dashboard)/job-actions"
import { useTasks } from "./TasksProvider"

export default function GlobalActions({
  concepts,
}: {
  concepts: { id: string; name: string }[]
}) {
  const { trackJob } = useTasks()
  const [runOpen, setRunOpen] = useState(false)
  const [conceptId, setConceptId] = useState("")
  const [batch, setBatch] = useState(false)
  const [pending, start] = useTransition()

  const btn =
    "w-full rounded-sm px-3 py-2 text-left text-[0.7rem] tracking-[0.2em] uppercase text-muted transition-colors hover:text-accent"

  return (
    <div className="flex flex-col gap-1">
      <button className={btn} onClick={() => setRunOpen((v) => !v)}>
        ▶ Run pipeline
      </button>

      {runOpen && (
        <div className="rounded-sm border border-line bg-surface p-3">
          <select
            value={conceptId}
            onChange={(e) => setConceptId(e.target.value)}
            className="mb-2 w-full rounded-sm border border-line bg-background px-2 py-1 text-xs"
          >
            <option value="">Pick concept…</option>
            {concepts.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
          <label className="mb-2 flex items-center gap-2 text-xs text-muted">
            <input type="checkbox" checked={batch} onChange={(e) => setBatch(e.target.checked)} />
            Batch of 5
          </label>
          <button
            disabled={!conceptId || pending}
            onClick={() =>
              start(async () => {
                const id = await enqueueJob("run_concept", { concept_id: conceptId, batch })
                const name = concepts.find((c) => c.id === conceptId)?.name ?? "concept"
                trackJob(id, batch ? "Pipeline ×5" : "Pipeline", name)
                setRunOpen(false)
              })
            }
            className="w-full rounded-sm bg-accent px-3 py-1.5 text-[0.65rem] uppercase tracking-wider text-surface disabled:opacity-40"
          >
            Run
          </button>
        </div>
      )}

      <button
        className={btn}
        disabled={pending}
        onClick={() =>
          start(async () => {
            const id = await enqueueJob("link_check", { scope: "all" })
            trackJob(id, "Link check", "All links")
          })
        }
      >
        ⚲ Check links
      </button>

      <Link href="/admin/activity" className={btn}>
        ☰ Activity
      </Link>
    </div>
  )
}
