"use client"

import { useState, useTransition, useEffect, useRef } from "react"
import { useRouter } from "next/navigation"
import type { AdminOutfit, AdminOutfitPost } from "@/lib/admin"
import { enqueueJob, getJobStatus } from "@/app/admin/(dashboard)/job-actions"
import { deleteOutfit } from "@/app/admin/(dashboard)/outfits/actions"
import {
  approvePost,
  deletePost,
  postNow,
  retryPost,
} from "@/app/admin/(dashboard)/schedule/actions"
import { useTasks } from "./TasksProvider"

function Badge({ on, label }: { on: boolean; label: string }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[0.6rem] tracking-wider uppercase ${
        on ? "bg-accent/15 text-accent" : "bg-foreground/5 text-muted/50"
      }`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${on ? "bg-accent" : "bg-muted/30"}`} />
      {label}
    </span>
  )
}

function price(cents: number | null, currency: string): string {
  if (cents == null) return "—"
  return new Intl.NumberFormat("en-US", { style: "currency", currency }).format(cents / 100)
}

const STATUS_LABEL: Record<string, string> = {
  draft: "queued",
  published: "published",
  failed: "failed",
}
const STATUS_COLOR: Record<string, string> = {
  queued: "text-accent",
  needs_approval: "text-muted",
  published: "text-green-600",
  failed: "text-red-500",
}

/** One linked post (TikTok/Pinterest) with the same approve / post-now / retry /
 *  remove actions as the Schedule tab — so an outfit's posts can be managed
 *  without leaving here. Mirrors the Approve → Queue → post model. */
function PostRow({ post, onDone }: { post: AdminOutfitPost; onDone: () => void }) {
  const { trackJob } = useTasks()
  const [pending, start] = useTransition()
  const [confirmRemove, setConfirmRemove] = useState(false)

  const isNeedsApproval = post.status === "draft" && !post.approved
  const isQueued = post.status === "draft" && post.approved
  const label = isNeedsApproval ? "needs approval" : STATUS_LABEL[post.status] ?? post.status
  const color = isNeedsApproval
    ? STATUS_COLOR.needs_approval
    : isQueued
      ? STATUS_COLOR.queued
      : STATUS_COLOR[post.status] ?? "text-muted"

  const run = (fn: () => Promise<void>) => () => start(async () => { await fn(); onDone() })
  const runJob = (jobLabel: string, fn: () => Promise<string>) => () =>
    start(async () => {
      const jobId = await fn()
      trackJob(jobId, jobLabel, post.caption ?? post.platform)
      onDone()
    })

  return (
    <div className="rounded-sm border border-line/60 bg-background p-2.5">
      <div className="flex items-center justify-between gap-2">
        <span className="text-[0.65rem] uppercase tracking-wider text-foreground/70">
          {post.platform === "tiktok" ? "TikTok" : post.platform === "pinterest" ? "Pinterest" : post.platform}
        </span>
        <span className={`text-[0.65rem] uppercase tracking-wider ${color}`}>{label}</span>
      </div>

      {post.status === "failed" && post.apiError && (
        <p className="mt-1.5 break-words rounded-sm bg-red-50 px-2 py-1 text-[0.65rem] text-red-600">
          {post.apiError}
        </p>
      )}

      <div className="mt-2 flex flex-wrap items-center gap-2">
        {isNeedsApproval && (
          <button
            disabled={pending}
            onClick={run(() => approvePost(post.id))}
            className="text-[0.65rem] uppercase tracking-wider text-accent hover:underline disabled:opacity-40"
          >
            Approve
          </button>
        )}
        {isQueued && (
          <button
            disabled={pending}
            onClick={runJob("Post now", () => postNow(post.id))}
            className="text-[0.65rem] uppercase tracking-wider text-accent hover:underline disabled:opacity-40"
          >
            Post now
          </button>
        )}
        {post.status === "failed" && (
          <button
            disabled={pending}
            onClick={runJob("Retry post", () => retryPost(post.id))}
            className="text-[0.65rem] uppercase tracking-wider text-accent hover:underline disabled:opacity-40"
          >
            Retry
          </button>
        )}
        {post.status !== "published" && (
          confirmRemove ? (
            <>
              <span className="text-[0.65rem] text-muted">Remove this post?</span>
              <button
                disabled={pending}
                onClick={run(() => deletePost(post.id))}
                className="text-[0.65rem] uppercase tracking-wider text-red-500 hover:text-red-600 disabled:opacity-40"
              >
                Confirm
              </button>
              <button onClick={() => setConfirmRemove(false)} className="text-[0.65rem] uppercase tracking-wider text-muted">
                Cancel
              </button>
            </>
          ) : (
            <button
              onClick={() => setConfirmRemove(true)}
              className="text-[0.65rem] uppercase tracking-wider text-muted hover:text-red-500"
            >
              Remove
            </button>
          )
        )}
      </div>
    </div>
  )
}

export default function OutfitCard({ outfit }: { outfit: AdminOutfit }) {
  const router = useRouter()
  const [open, setOpen] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)
  const [pending, start] = useTransition()
  const [confirmDelete, setConfirmDelete] = useState(false)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const enqueueAndPoll = (
    type: "regenerate_image" | "regenerate_collage" | "generate_posts_for_outfit"
  ) => () => {
    setMsg(null)
    start(async () => {
      const jobId = await enqueueJob(type, { outfit_id: outfit.id })
      setMsg("Queued…")
      pollRef.current = setInterval(async () => {
        const { status } = await getJobStatus(jobId)
        if (status === "done") {
          clearInterval(pollRef.current!)
          setMsg(null)
          router.refresh()
        } else if (status === "failed") {
          clearInterval(pollRef.current!)
          setMsg("Job failed — check Activity log.")
        } else {
          setMsg(status === "running" ? "Running…" : "Queued…")
        }
      }, 2500)
    })
  }

  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current) }, [])


  return (
    <>
      <button onClick={() => setOpen(true)} className="group block text-left">
        <div className="relative aspect-[4/5] w-full overflow-hidden rounded-sm bg-canvas ring-1 ring-line/60 transition-all group-hover:ring-accent/40">
          {outfit.collageUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={outfit.collageUrl} alt="" className="h-full w-full object-contain" />
          ) : (
            <div className="flex h-full w-full items-center justify-center text-xs text-muted">no image</div>
          )}
        </div>
        <div className="pt-2">
          <p className="truncate text-sm text-foreground">{outfit.conceptName}</p>
          <div className="mt-1 flex flex-wrap gap-1">
            <Badge on={outfit.posted} label="Posted" />
            <Badge on={outfit.queued} label="Queued" />
            <Badge on={outfit.onSite} label="On site" />
          </div>
        </div>
      </button>

      {open && (
        <div className="fixed inset-0 z-50 flex items-end justify-center sm:items-center" onClick={() => setOpen(false)}>
          <div className="absolute inset-0 bg-stone-900/40 backdrop-blur-[2px]" />
          <div
            className="relative z-10 max-h-[88vh] w-full max-w-lg overflow-y-auto rounded-t-lg bg-surface p-6 shadow-2xl sm:rounded-lg"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between">
              <div>
                <p className="text-[0.65rem] tracking-[0.25em] uppercase text-accent">{outfit.conceptName}</p>
                <h3 className="font-serif text-2xl text-foreground">Outfit</h3>
              </div>
              <button onClick={() => setOpen(false)} className="text-[0.7rem] uppercase tracking-wider text-muted hover:text-accent">
                Close
              </button>
            </div>

            {outfit.collageUrl && (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={outfit.collageUrl} alt="" className="mx-auto my-4 max-h-72 object-contain" />
            )}

            <div className="mb-2 flex flex-wrap gap-1">
              <Badge on={outfit.posted} label="Posted" />
              <Badge on={outfit.queued} label="Queued" />
              <Badge on={outfit.onSite} label="On site" />
            </div>

            <ul className="divide-y divide-line/60 border-y border-line/60">
              {outfit.products.map((p) => (
                <li key={p.id} className="flex items-center justify-between gap-3 py-2 text-sm">
                  <span className="min-w-0">
                    <span className="block truncate text-foreground">{p.name}</span>
                    <span className="text-[0.7rem] uppercase tracking-wider text-muted/70">
                      {p.retailer} · {p.category ?? "—"}
                    </span>
                  </span>
                  <span className="shrink-0 text-muted">{price(p.price_cents, p.currency)}</span>
                </li>
              ))}
            </ul>

            <div className="mt-5">
              <p className="mb-2 text-[0.65rem] tracking-[0.2em] uppercase text-muted">Posts</p>
              {outfit.posts.length === 0 ? (
                <div>
                  <p className="mb-2 text-xs text-muted/60">No posts linked to this outfit yet.</p>
                  <button
                    onClick={enqueueAndPoll("generate_posts_for_outfit")}
                    disabled={pending}
                    className="rounded-sm border border-line px-3 py-2 text-xs uppercase tracking-wider text-foreground hover:border-accent hover:text-accent disabled:opacity-40"
                  >
                    Generate posts
                  </button>
                </div>
              ) : (
                <div className="space-y-2">
                  {outfit.posts.map((p) => (
                    <PostRow key={p.id} post={p} onDone={() => router.refresh()} />
                  ))}
                </div>
              )}
            </div>

            <div className="mt-5 flex flex-wrap gap-2">
              <button
                onClick={enqueueAndPoll("regenerate_image")}
                disabled={pending}
                className="rounded-sm border border-line px-3 py-2 text-xs uppercase tracking-wider text-foreground hover:border-accent hover:text-accent disabled:opacity-40"
              >
                Regenerate images
              </button>
              <button
                onClick={enqueueAndPoll("regenerate_collage")}
                disabled={pending}
                className="rounded-sm border border-line px-3 py-2 text-xs uppercase tracking-wider text-foreground hover:border-accent hover:text-accent disabled:opacity-40"
              >
                Regenerate collage
              </button>
            </div>
            {msg && <p className="mt-3 text-xs text-accent">{msg}</p>}

            <div className="mt-4 border-t border-line/60 pt-4">
              {!confirmDelete ? (
                <button
                  onClick={() => setConfirmDelete(true)}
                  className="text-xs uppercase tracking-wider text-red-400 hover:text-red-500"
                >
                  Delete outfit
                </button>
              ) : (
                <div className="flex items-center gap-3">
                  <span className="text-xs text-muted">Delete outfit + all its posts?</span>
                  <button
                    disabled={pending}
                    onClick={() => start(async () => {
                      await deleteOutfit(outfit.id)
                      setOpen(false)
                    })}
                    className="text-xs uppercase tracking-wider text-red-500 hover:text-red-600 disabled:opacity-40"
                  >
                    Confirm
                  </button>
                  <button
                    onClick={() => setConfirmDelete(false)}
                    className="text-xs uppercase tracking-wider text-muted hover:text-foreground"
                  >
                    Cancel
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  )
}
