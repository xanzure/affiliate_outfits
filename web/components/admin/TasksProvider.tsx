"use client"

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react"
import { getJobStatus } from "@/app/admin/(dashboard)/job-actions"

export type Task = {
  id: string
  label: string // human description, e.g. concept name or product URL
  kind: string // action label, e.g. "Pipeline", "Intake"
  status: string // queued | running | done | failed | unknown
  message?: string
  startedAt: number
}

const STORAGE_KEY = "va_tasks"
const POLL_MS = 5000
const TERMINAL = new Set(["done", "failed"])

type Ctx = {
  tasks: Task[]
  trackJob: (id: string, kind: string, label: string) => void
  dismissTask: (id: string) => void
}

const TasksCtx = createContext<Ctx | null>(null)

export function useTasks() {
  const ctx = useContext(TasksCtx)
  if (!ctx) throw new Error("useTasks must be used inside <TasksProvider>")
  return ctx
}

function load(): Task[] {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "[]") as Task[]
  } catch {
    return []
  }
}

export function TasksProvider({ children }: { children: React.ReactNode }) {
  const [tasks, setTasks] = useState<Task[]>([])
  const timer = useRef<ReturnType<typeof setInterval> | null>(null)

  // On mount: rehydrate persisted tasks, dropping any that already finished.
  // Queued/running tasks survive the refresh; done/failed are pruned here.
  useEffect(() => {
    setTasks(load().filter((t) => !TERMINAL.has(t.status)))
  }, [])

  // Persist on every change so a refresh keeps in-flight work visible.
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(tasks))
    } catch {
      /* quota / private mode — non-fatal */
    }
  }, [tasks])

  // Poll all non-terminal tasks on a single shared interval.
  useEffect(() => {
    const active = tasks.filter((t) => !TERMINAL.has(t.status))
    if (active.length === 0) return

    timer.current = setInterval(async () => {
      const updates = await Promise.all(
        active.map(async (t) => {
          const { status, result } = await getJobStatus(t.id)
          const message =
            (result?.error as string) ||
            (result?.name as string) ||
            undefined
          return { id: t.id, status, message }
        })
      )
      setTasks((prev) =>
        prev.map((t) => {
          const u = updates.find((x) => x.id === t.id)
          if (!u || u.status === "unknown") return t
          return { ...t, status: u.status, message: u.message ?? t.message }
        })
      )
    }, POLL_MS)

    return () => {
      if (timer.current) clearInterval(timer.current)
    }
  }, [tasks])

  const trackJob = useCallback((id: string, kind: string, label: string) => {
    setTasks((prev) =>
      prev.some((t) => t.id === id)
        ? prev
        : [{ id, kind, label, status: "queued", startedAt: Date.now() }, ...prev]
    )
  }, [])

  const dismissTask = useCallback((id: string) => {
    setTasks((prev) => prev.filter((t) => t.id !== id))
  }, [])

  return (
    <TasksCtx.Provider value={{ tasks, trackJob, dismissTask }}>
      {children}
    </TasksCtx.Provider>
  )
}
