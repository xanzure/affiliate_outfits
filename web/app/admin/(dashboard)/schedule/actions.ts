"use server"

import { revalidatePath } from "next/cache"
import { createAdminClient } from "@/lib/supabase/admin"

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

export async function approvePost(id: string) {
  const sb = createAdminClient()
  await sb
    .from("posts")
    .update({ approved: true, updated_at: now() })
    .eq("id", id)
  await logAction("approve", id)
  revalidatePath("/admin/schedule")
}

export async function schedulePostAt(id: string, scheduledFor: string) {
  const sb = createAdminClient()
  await sb
    .from("posts")
    .update({
      status: "scheduled",
      scheduled_for: new Date(scheduledFor).toISOString(),
      is_manual_schedule: true,
      approved: true,
      updated_at: now(),
    })
    .eq("id", id)
  await logAction("schedule", id, { scheduledFor })
  revalidatePath("/admin/schedule")
}

export async function cancelSchedule(id: string) {
  const sb = createAdminClient()
  await sb
    .from("posts")
    .update({
      status: "draft",
      scheduled_for: null,
      is_manual_schedule: false,
      queue_order: now(),
      updated_at: now(),
    })
    .eq("id", id)
  await logAction("cancel_schedule", id)
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
}
