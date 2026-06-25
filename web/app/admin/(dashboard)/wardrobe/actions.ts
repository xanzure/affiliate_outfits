"use server"

import { revalidatePath } from "next/cache"
import { createAdminClient } from "@/lib/supabase/admin"
import { enqueueJob } from "../job-actions"

/** Soft-delete: drop from the cache (no new outfit uses it) but keep the row +
 *  image so existing outfits that reference it don't break. */
export async function archiveProduct(productId: string): Promise<void> {
  const sb = createAdminClient()
  await sb
    .from("products")
    .update({ archived_at: new Date().toISOString() })
    .eq("id", productId)
  revalidatePath("/admin/wardrobe")
}

/** Upload a manual image to a temp storage path; returns its public URL so the
 *  intake/reprocess job can use it instead of scraping. */
export async function uploadIntakeImage(formData: FormData): Promise<string> {
  const file = formData.get("file") as File | null
  if (!file) throw new Error("no file")
  const sb = createAdminClient()
  const path = `intake/${crypto.randomUUID()}.png`
  const bytes = new Uint8Array(await file.arrayBuffer())
  const { error } = await sb.storage
    .from("product-images")
    .upload(path, bytes, { contentType: file.type || "image/png", upsert: true })
  if (error) throw new Error(error.message)
  return sb.storage.from("product-images").getPublicUrl(path).data.publicUrl
}

/** Enqueue an intake job for a direct product URL (Apify scrapes that URL only)
 *  or a manually-uploaded image. Returns the job id to poll. */
export async function intakeProduct(input: {
  url: string
  category?: string
  imageUrl?: string
}): Promise<string> {
  const id = await enqueueJob("intake_product", {
    url: input.url,
    category: input.category || null,
    image_url: input.imageUrl || null,
  })
  revalidatePath("/admin/wardrobe")
  return id
}

/** Re-run the cutout for one product, optionally with a freshly-uploaded image. */
export async function reprocessProduct(input: {
  productId: string
  imageUrl?: string
}): Promise<string> {
  return enqueueJob("reprocess_product", {
    product_id: input.productId,
    image_url: input.imageUrl || null,
  })
}
