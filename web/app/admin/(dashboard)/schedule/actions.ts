"use server"

import { revalidatePath } from "next/cache"
import { createAdminClient } from "@/lib/supabase/admin"
import { enqueueJob } from "../job-actions"

async function logAction(
  action: string,
  targetId: string,
  detail: Record<string, unknown> = {}
) {
  const sb = createAdminClient()
  await sb.from("admin_actions").insert({
    id: `act_${crypto.randomUUID().replace(/-/g, "").slice(0, 24)}`,
    action,
    target_id: targetId,
    detail_json: JSON.stringify(detail),
    created_at: new Date().toISOString(),
  })
}

const now = () => new Date().toISOString()

/** Fixed-width numeric queue_order key (see app/db/posts.py::_queue_order_key).
 *  Approvals use epoch millis so they append to the tail; reorders use small
 *  sequential ints — both zero-padded to 15 so string sort == numeric order. */
const orderKey = (value: number) => String(value).padStart(15, "0")

/** Move a Needs-Approval draft into the queue (appended to the tail). */
export async function approvePost(id: string) {
  const sb = createAdminClient()
  await sb
    .from("posts")
    .update({ approved: true, queue_order: orderKey(Date.now()), updated_at: now() })
    .eq("id", id)
  await logAction("approve", id)
  revalidatePath("/admin/schedule")
  revalidatePath("/admin/outfits")
}

/** Persist an explicit queue ordering (top → bottom) for one platform. */
export async function reorderQueue(orderedIds: string[]) {
  const sb = createAdminClient()
  const stamp = now()
  await Promise.all(
    orderedIds.map((id, index) =>
      sb
        .from("posts")
        .update({ queue_order: orderKey(index), updated_at: stamp })
        .eq("id", id)
    )
  )
  revalidatePath("/admin/schedule")
}

export async function editCaption(id: string, caption: string) {
  const sb = createAdminClient()
  await sb
    .from("posts")
    .update({ caption, updated_at: now() })
    .eq("id", id)
  await logAction("edit_caption", id)
  revalidatePath("/admin/schedule")
  revalidatePath("/admin/outfits")
}

/** Re-attempt a live platform post for a failed post. Runs on the worker
 *  (Python) since that's where the TikTok/Pinterest clients live — returns the
 *  job id so the caller can track it in the Tasks panel. */
export async function retryPost(id: string): Promise<string> {
  const jobId = await enqueueJob("retry_post", { post_id: id })
  await logAction("retry_post", id)
  return jobId
}

/** Publish a queued post immediately, bypassing the cooldown. Same worker job
 *  as retry — the successful attempt also resets that platform's 24h window. */
export async function postNow(id: string): Promise<string> {
  const jobId = await enqueueJob("retry_post", { post_id: id })
  await logAction("post_now", id)
  return jobId
}

export async function deletePost(id: string) {
  const sb = createAdminClient()
  const { data } = await sb.from("posts").select("status").eq("id", id).single()
  if (data?.status === "published") {
    throw new Error("Cannot delete a published post")
  }
  await sb.from("posts").delete().eq("id", id)
  await logAction("delete", id)
  revalidatePath("/admin/schedule")
  revalidatePath("/admin/outfits")
}
