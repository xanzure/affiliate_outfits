"use server"

import { revalidatePath } from "next/cache"
import { createAdminClient } from "@/lib/supabase/admin"

export async function deleteOutfit(outfitId: string): Promise<void> {
  const sb = createAdminClient()
  await sb.from("posts").delete().eq("outfit_id", outfitId)
  await sb.from("collages").delete().eq("outfit_id", outfitId)
  await sb.from("outfits").delete().eq("id", outfitId)
  revalidatePath("/admin/outfits")
}
