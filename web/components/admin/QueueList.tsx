"use client"

import { useEffect, useState, useTransition } from "react"
import type { AdminPost, Cooldown } from "@/lib/admin"
import { reorderQueue } from "@/app/admin/(dashboard)/schedule/actions"
import PostCard from "./PostCard"

/** Relative "next auto-post in Xh Ym" string, ticking every 30s. */
function useCountdown(readyAt: string | null): string {
  const [, force] = useState(0)
  useEffect(() => {
    if (!readyAt) return
    const t = setInterval(() => force((n) => n + 1), 30_000)
    return () => clearInterval(t)
  }, [readyAt])

  if (!readyAt) return "ready — posts on next check"
  const ms = Date.parse(readyAt) - Date.now()
  if (ms <= 0) return "ready — posts on next check"
  const mins = Math.round(ms / 60_000)
  const h = Math.floor(mins / 60)
  const m = mins % 60
  return `next auto-post in ${h > 0 ? `${h}h ` : ""}${m}m`
}

export default function QueueList({
  platform,
  posts,
  cooldown,
}: {
  platform: "tiktok" | "pinterest"
  posts: AdminPost[]
  cooldown: Cooldown
}) {
  const [order, setOrder] = useState(posts)
  const [, start] = useTransition()
  const countdown = useCountdown(cooldown.readyAt)

  // Re-sync local order when the server data changes (after a refresh / revalidate).
  const idsKey = posts.map((p) => p.id).join(",")
  useEffect(() => {
    setOrder(posts)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [idsKey])

  const move = (id: string, dir: "up" | "down" | "top") => {
    const idx = order.findIndex((p) => p.id === id)
    if (idx < 0) return
    const next = [...order]
    const [item] = next.splice(idx, 1)
    if (dir === "up") next.splice(Math.max(0, idx - 1), 0, item)
    else if (dir === "down") next.splice(Math.min(next.length, idx + 1), 0, item)
    else next.unshift(item)
    setOrder(next) // optimistic
    start(() => void reorderQueue(next.map((p) => p.id)))
  }

  const label = platform === "tiktok" ? "TikTok" : "Pinterest"

  return (
    <div>
      <div className="mb-3 flex items-baseline gap-3">
        <h3 className="text-[0.65rem] font-medium tracking-[0.2em] uppercase text-foreground/60">{label}</h3>
        <span className="text-[0.65rem] tracking-wider text-muted/60">{order.length}</span>
        <span className="text-[0.65rem] text-accent/80">{countdown}</span>
      </div>
      {order.length === 0 ? (
        <p className="text-sm text-muted/50">Empty.</p>
      ) : (
        <div className="space-y-4">
          {order.map((p, i) => (
            <PostCard
              key={p.id}
              post={p}
              section="queue"
              position={i + 1}
              isFirst={i === 0}
              isLast={i === order.length - 1}
              onMove={(dir) => move(p.id, dir)}
            />
          ))}
        </div>
      )}
    </div>
  )
}
