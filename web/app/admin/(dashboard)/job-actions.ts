"use server"

import { revalidatePath } from "next/cache"
import { createAdminClient } from "@/lib/supabase/admin"

export async function enqueueJob(
  type:
    | "regenerate_image"
    | "regenerate_collage"
    | "run_concept"
    | "link_check"
    | "intake_product"
    | "reprocess_product"
    | "retry_post",
  payload: Record<string, unknown> = {}
): Promise<string> {
  const sb = createAdminClient()
  const id = `job_${crypto.randomUUID().replace(/-/g, "").slice(0, 24)}`
  const now = new Date().toISOString()
  await sb.from("jobs").insert({
    id,
    type,
    payload_json: JSON.stringify(payload),
    status: "queued",
    result_json: "{}",
    created_at: now,
    updated_at: now,
  })
  await sb.from("admin_actions").insert({
    id: `act_${crypto.randomUUID().replace(/-/g, "").slice(0, 24)}`,
    action: `enqueue_${type}`,
    target_id: (payload.outfit_id as string) ?? (payload.concept_id as string) ?? null,
    detail_json: JSON.stringify(payload),
    created_at: now,
  })
  revalidatePath("/admin")
  return id
}

export async function getJobStatus(
  id: string
): Promise<{ status: string; result: Record<string, unknown> }> {
  const sb = createAdminClient()
  const { data } = await sb
    .from("jobs")
    .select("status, result_json")
    .eq("id", id)
    .single()
  if (!data) return { status: "unknown", result: {} }
  let result: Record<string, unknown> = {}
  try { result = JSON.parse(data.result_json ?? "{}") } catch {}
  return { status: data.status, result }
}
