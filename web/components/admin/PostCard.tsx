"use client"

import { useState, useTransition } from "react"
import type { AdminPost } from "@/lib/admin"
import {
  approvePost,
  cancelSchedule,
  deletePost,
  editCaption,
  schedulePostAt,
} from "@/app/admin/(dashboard)/schedule/actions"

type Section = "needsApproval" | "scheduled" | "queue"

function fmtTime(iso: string | null): string {
  if (!iso) return ""
  return new Date(iso).toLocaleString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  })
}

function PlatformBadge({ platform }: { platform: string }) {
  const label = platform === "tiktok" ? "TikTok" : platform === "pinterest" ? "Pinterest" : platform
  return (
    <span className="rounded-sm bg-foreground/5 px-2 py-0.5 text-[0.6rem] font-medium tracking-[0.15em] uppercase text-foreground/70">
      {label}
    </span>
  )
}

export default function PostCard({ post, section }: { post: AdminPost; section: Section }) {
  const [slide, setSlide] = useState(0)
  const [menuOpen, setMenuOpen] = useState(false)
  const [editing, setEditing] = useState(false)
  const [caption, setCaption] = useState(post.caption ?? "")
  const [picking, setPicking] = useState(false)
  const [when, setWhen] = useState("")
  const [pending, start] = useTransition()

  const slides = post.slides.length ? post.slides : [""]
  const deadLinks = post.linkCheck?.dead?.length ?? 0

  const run = (fn: () => Promise<void>) => () => {
    setMenuOpen(false)
    start(() => void fn())
  }

  return (
    <div className="overflow-hidden rounded-sm border border-line/70 bg-surface">
      {/* header */}
      <div className="flex items-center justify-between gap-2 px-3 pt-3">
        <div className="flex items-center gap-2">
          <PlatformBadge platform={post.platform} />
          {section === "scheduled" && post.scheduled_for && (
            <span className="text-[0.7rem] font-medium text-accent">
              {fmtTime(post.scheduled_for)}
            </span>
          )}
          {section === "scheduled" && post.is_manual_schedule && (
            <span className="text-[0.6rem] uppercase tracking-wider text-muted/60">pinned</span>
          )}
        </div>
        <div className="relative">
          <button
            onClick={() => setMenuOpen((v) => !v)}
            disabled={pending}
            className="px-2 py-1 text-lg leading-none text-muted hover:text-foreground disabled:opacity-40"
            aria-label="actions"
          >
            ⋯
          </button>
          {menuOpen && (
            <div className="absolute right-0 z-20 mt-1 w-44 overflow-hidden rounded-sm border border-line bg-background text-sm shadow-lg">
              {section === "needsApproval" && (
                <button onClick={run(() => approvePost(post.id))} className="block w-full px-3 py-2 text-left hover:bg-accent/10 hover:text-accent">
                  Approve
                </button>
              )}
              <button
                onClick={() => { setMenuOpen(false); setEditing(true) }}
                className="block w-full px-3 py-2 text-left hover:bg-accent/10 hover:text-accent"
              >
                Edit caption
              </button>
              {section !== "needsApproval" && (
                <button
                  onClick={() => { setMenuOpen(false); setPicking(true) }}
                  className="block w-full px-3 py-2 text-left hover:bg-accent/10 hover:text-accent"
                >
                  Schedule now…
                </button>
              )}
              {section === "scheduled" && (
                <button onClick={run(() => cancelSchedule(post.id))} className="block w-full px-3 py-2 text-left hover:bg-accent/10 hover:text-accent">
                  Cancel schedule
                </button>
              )}
              <button onClick={run(() => deletePost(post.id))} className="block w-full px-3 py-2 text-left text-red-600 hover:bg-red-50">
                Delete
              </button>
            </div>
          )}
        </div>
      </div>

      {/* media carousel */}
      <div className="relative mt-3 aspect-[4/5] w-full bg-canvas">
        {slides[slide] ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={slides[slide]} alt="" className="h-full w-full object-contain" />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-xs text-muted">no image</div>
        )}
        {slides.length > 1 && (
          <>
            <button
              onClick={() => setSlide((s) => (s - 1 + slides.length) % slides.length)}
              className="absolute left-2 top-1/2 -translate-y-1/2 rounded-full bg-background/80 px-2 py-1 text-sm shadow"
            >
              ‹
            </button>
            <button
              onClick={() => setSlide((s) => (s + 1) % slides.length)}
              className="absolute right-2 top-1/2 -translate-y-1/2 rounded-full bg-background/80 px-2 py-1 text-sm shadow"
            >
              ›
            </button>
            <span className="absolute bottom-2 left-1/2 -translate-x-1/2 rounded-full bg-background/80 px-2 py-0.5 text-[0.6rem] text-muted">
              {slide + 1}/{slides.length}
            </span>
          </>
        )}
      </div>

      {/* caption */}
      <div className="px-3 py-3">
        {editing ? (
          <div>
            <textarea
              value={caption}
              onChange={(e) => setCaption(e.target.value)}
              rows={3}
              className="w-full rounded-sm border border-line bg-background p-2 text-sm outline-none focus:border-accent"
            />
            <div className="mt-2 flex gap-2">
              <button
                onClick={run(async () => { await editCaption(post.id, caption); setEditing(false) })}
                className="rounded-sm bg-accent px-3 py-1 text-xs uppercase tracking-wider text-surface"
              >
                Save
              </button>
              <button onClick={() => { setEditing(false); setCaption(post.caption ?? "") }} className="px-3 py-1 text-xs uppercase tracking-wider text-muted">
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <p className="text-sm leading-relaxed text-foreground/90">{post.caption}</p>
        )}

        <div className="mt-2 flex items-center justify-between text-[0.65rem] uppercase tracking-wider text-muted/70">
          <span>{post.conceptName}</span>
          {deadLinks > 0 && <span className="text-amber-600">⚠ {deadLinks} dead link{deadLinks > 1 ? "s" : ""}</span>}
        </div>

        {picking && (
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <input
              type="datetime-local"
              value={when}
              onChange={(e) => setWhen(e.target.value)}
              className="rounded-sm border border-line bg-background px-2 py-1 text-sm"
            />
            <button
              disabled={!when}
              onClick={run(async () => { await schedulePostAt(post.id, when); setPicking(false) })}
              className="rounded-sm bg-accent px-3 py-1 text-xs uppercase tracking-wider text-surface disabled:opacity-40"
            >
              Pin
            </button>
            <button onClick={() => setPicking(false)} className="px-2 py-1 text-xs uppercase tracking-wider text-muted">
              Cancel
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
