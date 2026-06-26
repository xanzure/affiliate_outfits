"use client"

import { useTasks } from "./TasksProvider"

const DOT: Record<string, string> = {
  queued: "bg-muted",
  running: "bg-amber-500 animate-pulse",
  done: "bg-green-600",
  failed: "bg-red-500",
  unknown: "bg-muted",
}
const STATUS_LABEL: Record<string, string> = {
  queued: "Queued",
  running: "Running…",
  done: "Done",
  failed: "Failed",
  unknown: "…",
}

export default function TaskPanel() {
  const { tasks, dismissTask } = useTasks()
  if (tasks.length === 0) return null

  return (
    <div className="flex flex-col gap-2 rounded-sm border border-line bg-surface/70 p-3">
      <p className="text-[0.6rem] tracking-[0.2em] uppercase text-muted">Tasks</p>
      {tasks.map((t) => {
        const done = t.status === "done" || t.status === "failed"
        return (
          <div key={t.id} className="flex items-start gap-2">
            <span
              className={`mt-1 h-1.5 w-1.5 shrink-0 rounded-full ${DOT[t.status] ?? "bg-muted"}`}
            />
            <div className="min-w-0 flex-1">
              <p className="truncate text-[0.72rem] text-foreground" title={t.label}>
                {t.label}
              </p>
              <p className="text-[0.6rem] tracking-[0.08em] uppercase text-muted">
                {t.kind} · {STATUS_LABEL[t.status] ?? t.status}
              </p>
              {t.status === "failed" && t.message && (
                <p className="mt-0.5 break-words text-[0.6rem] text-red-500">{t.message}</p>
              )}
            </div>
            {done && (
              <button
                onClick={() => dismissTask(t.id)}
                aria-label="dismiss"
                className="px-1 text-sm leading-none text-muted transition-colors hover:text-foreground"
              >
                ×
              </button>
            )}
          </div>
        )
      })}
    </div>
  )
}
