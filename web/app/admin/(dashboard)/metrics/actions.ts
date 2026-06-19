"use server"

import { revalidatePath } from "next/cache"
import { createAdminClient } from "@/lib/supabase/admin"

export async function addMetrics(formData: FormData) {
  const sb = createAdminClient()
  const postId = String(formData.get("post_id") ?? "")
  if (!postId) return

  const num = (k: string) => Number(formData.get(k) ?? 0) || 0
  const views = num("views")
  const likes = num("likes")
  const comments = num("comments")
  const shares = num("shares")
  const saves = num("saves")
  const clicks = num("clicks")
  // simple engagement score
  const score =
    Math.round(((likes + comments * 2 + shares * 3 + saves * 2 + clicks * 4) /
      Math.max(views, 1)) * 1000) / 10

  const { data: post } = await sb.from("posts").select("platform").eq("id", postId).single()

  await sb.from("metrics").insert({
    id: `metric_${crypto.randomUUID().replace(/-/g, "").slice(0, 22)}`,
    post_id: postId,
    platform: post?.platform ?? "local",
    collected_at: new Date().toISOString(),
    views,
    likes,
    comments,
    shares,
    saves,
    clicks,
    score,
    metadata_json: "{}",
  })
  revalidatePath("/admin/metrics")
}
