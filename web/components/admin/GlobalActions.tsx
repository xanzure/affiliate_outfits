"use client"

import Link from "next/link"
import { useState, useTransition, useEffect, useRef } from "react"
import { enqueueJob, getJobStatus } from "@/app/admin/(dashboard)/job-actions"

type JobState = { id: string; label: string; status: string }

const STATUS_COLOR: Record<string, string> = {
  queued: "text-muted",
  running: "text-amber-500",
  done: "text-green-600",
  failed: "text-red-500",
}
const STATUS_LABEL: Record<string, string> = {
  queued: "queued",
  running: "running…",
  done: "done ✓",
  failed: "failed ✗",
  unknown: "?",
}

function useJobPoller(job: JobState | null, onDone: (status: string) => void) {
  const ref = useRef<ReturnType<typeof setInterval> | null>(null)
  useEffect(() => {
    if (!job || job.status === "done" || job.status === "failed") return
    ref.current = setInterval(async () => {
      const { status } = await getJobStatus(job.id)
      onDone(status)
      if (status === "done" || status === "failed") {
        if (ref.current) clearInterval(ref.current)
      }
    }, 2500)
    return () => { if (ref.current) clearInterval(ref.current) }
  }, [job?.id])
}

export default function GlobalActions({
  concepts,
}: {
  concepts: { id: string; name: string }[]
}) {
  const [runOpen, setRunOpen] = useState(false)
  const [conceptId, setConceptId] = useState("")
  const [batch, setBatch] = useState(false)
  const [pending, start] = useTransition()

  const [pipelineJob, setPipelineJob] = useState<JobState | null>(null)
  const [linkJob, setLinkJob] = useState<JobState | null>(null)

  useJobPoller(pipelineJob, (status) =>
    setPipelineJob((j) => j ? { ...j, status } : j)
  )
  useJobPoller(linkJob, (status) =>
    setLinkJob((j) => j ? { ...j, status } : j)
  )

  const btn =
    "w-full rounded-sm px-3 py-2 text-left text-[0.7rem] tracking-[0.2em] uppercase text-muted transition-colors hover:text-accent"

  return (
    <div className="flex flex-col gap-1">
      <button className={btn} onClick={() => setRunOpen((v) => !v)}>
        ▶ Run pipeline
      </button>

      {pipelineJob && (
        <p className={`px-3 text-[0.65rem] ${STATUS_COLOR[pipelineJob.status] ?? "text-muted"}`}>
          {pipelineJob.label}: {STATUS_LABEL[pipelineJob.status] ?? pipelineJob.status}
        </p>
      )}

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
                const label = concepts.find((c) => c.id === conceptId)?.name ?? "concept"
                setPipelineJob({ id, label, status: "queued" })
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
            setLinkJob({ id, label: "link check", status: "queued" })
          })
        }
      >
        ⚲ Check links
      </button>

      {linkJob && (
        <p className={`px-3 text-[0.65rem] ${STATUS_COLOR[linkJob.status] ?? "text-muted"}`}>
          Links: {STATUS_LABEL[linkJob.status] ?? linkJob.status}
        </p>
      )}

      <Link href="/admin/activity" className={btn}>
        ☰ Activity
      </Link>
    </div>
  )
}
