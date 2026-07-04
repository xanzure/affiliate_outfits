"use client"

import { useState, useTransition } from "react"
import type { AdminPost } from "@/lib/admin"
import {
  approvePost,
  deletePost,
  editCaption,
  postNow,
  retryPost,
} from "@/app/admin/(dashboard)/schedule/actions"
import { useTasks } from "./TasksProvider"

type Section = "needsApproval" | "queue" | "failed"

function PlatformBadge({ platform }: { platform: string }) {
  const label = platform === "tiktok" ? "TikTok" : platform === "pinterest" ? "Pinterest" : platform
  return (
    <span className="rounded-sm bg-foreground/5 px-2 py-0.5 text-[0.6rem] font-medium tracking-[0.15em] uppercase text-foreground/70">
      {label}
    </span>
  )
}

export default function PostCard({
  post,
  section,
  position,
  isFirst,
  isLast,
  onMove,
}: {
  post: AdminPost
  section: Section
  position?: number
  isFirst?: boolean
  isLast?: boolean
  onMove?: (dir: "up" | "down" | "top") => void
}) {
  const { trackJob } = useTasks()
  const [slide, setSlide] = useState(0)
  const [menuOpen, setMenuOpen] = useState(false)
  const [editing, setEditing] = useState(false)
  const [caption, setCaption] = useState(post.caption ?? "")
  const [pending, start] = useTransition()

  const slides = post.slides.length ? post.slides : [""]
  const deadLinks = post.linkCheck?.dead?.length ?? 0

  const run = (fn: () => Promise<void>) => () => {
    setMenuOpen(false)
    start(() => void fn())
  }

  // Actions that enqueue a worker job (Post now / Retry) — track in the Tasks panel.
  const runJob = (label: string, fn: () => Promise<string>) => () => {
    setMenuOpen(false)
    start(async () => {
      const jobId = await fn()
      trackJob(jobId, label, post.caption ?? post.platform)
    })
  }

  return (
    <div className="overflow-hidden rounded-sm border border-line/70 bg-surface">
      {/* header */}
      <div className="flex items-center justify-between gap-2 px-3 pt-3">
        <div className="flex items-center gap-2">
          <PlatformBadge platform={post.platform} />
          {section === "queue" && position != null && (
            <span className="text-[0.7rem] font-medium text-accent">#{position}</span>
          )}
          {section === "queue" && onMove && (
            <span className="flex items-center gap-0.5">
              <button
                disabled={isFirst || pending}
                onClick={() => onMove("up")}
                className="px-1 text-sm leading-none text-muted hover:text-foreground disabled:opacity-25"
                aria-label="move up"
              >
                ↑
              </button>
              <button
                disabled={isLast || pending}
                onClick={() => onMove("down")}
                className="px-1 text-sm leading-none text-muted hover:text-foreground disabled:opacity-25"
                aria-label="move down"
              >
                ↓
              </button>
              <button
                disabled={isFirst || pending}
                onClick={() => onMove("top")}
                className="px-1 text-sm leading-none text-muted hover:text-foreground disabled:opacity-25"
                aria-label="move to top"
                title="move to top"
              >
                ⤒
              </button>
            </span>
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
              {section === "queue" && (
                <button onClick={runJob("Post now", () => postNow(post.id))} className="block w-full px-3 py-2 text-left hover:bg-accent/10 hover:text-accent">
                  Post now
                </button>
              )}
              {section === "failed" && (
                <button onClick={runJob("Retry post", () => retryPost(post.id))} className="block w-full px-3 py-2 text-left hover:bg-accent/10 hover:text-accent">
                  Retry
                </button>
              )}
              <button
                onClick={() => { setMenuOpen(false); setEditing(true) }}
                className="block w-full px-3 py-2 text-left hover:bg-accent/10 hover:text-accent"
              >
                Edit caption
              </button>
              <button onClick={run(() => deletePost(post.id))} className="block w-full px-3 py-2 text-left text-red-600 hover:bg-red-50">
                {section === "needsApproval" ? "Delete" : "Remove"}
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

        {section === "failed" && post.apiError && (
          <p className="mt-2 break-words rounded-sm bg-red-50 px-2 py-1.5 text-[0.7rem] text-red-600">
            {post.apiError}
          </p>
        )}
      </div>
    </div>
  )
}
