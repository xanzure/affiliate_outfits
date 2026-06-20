"use server"

import { revalidatePath } from "next/cache"
import { createAdminClient } from "@/lib/supabase/admin"

export async function deleteOutfit(outfitId: string): Promise<void> {
  const sb = createAdminClient()
  // Delete collage file from storage (best-effort — ignore if not found)
  await sb.storage.from("collages").remove([`collages/${outfitId}.png`])
  await sb.from("posts").delete().eq("outfit_id", outfitId)
  await sb.from("collages").delete().eq("outfit_id", outfitId)
  await sb.from("outfits").delete().eq("id", outfitId)
  revalidatePath("/admin/outfits")
}
