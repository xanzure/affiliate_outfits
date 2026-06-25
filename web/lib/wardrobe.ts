import { createAdminClient } from "@/lib/supabase/admin"
import { resolveZone, type Zone } from "@/lib/categories"

export type WardrobeItem = {
  id: string
  name: string
  retailer: string
  category: string | null
  zone: Zone
  imageUrl: string | null
  priceCents: number | null
  currency: string
  url: string
  source: string // apify / google_shopping / manual
  color: string | null
  inUse: boolean
  createdAt: string
}

/** Every image-ready, non-archived product — i.e. the cache an outfit can use. */
export async function getWardrobe(): Promise<WardrobeItem[]> {
  const sb = createAdminClient()
  const [{ data: products }, { data: outfits }] = await Promise.all([
    sb
      .from("products")
      .select("*")
      .is("archived_at", null)
      .like("image_url", "%supabase.co/storage%")
      .order("created_at", { ascending: false }),
    sb.from("outfits").select("product_ids_json"),
  ])

  const inUse = new Set<string>()
  for (const o of outfits ?? []) {
    try {
      for (const pid of JSON.parse((o.product_ids_json as string) ?? "[]")) inUse.add(pid)
    } catch {}
  }

  return (products ?? []).map((p) => {
    let source = "unknown"
    let color: string | null = null
    try {
      const m = JSON.parse((p.metadata_json as string) ?? "{}")
      source = (m.product_source as string) ?? "unknown"
      color = (m.color as string) ?? null
    } catch {}
    return {
      id: p.id as string,
      name: p.name as string,
      retailer: p.retailer as string,
      category: (p.category as string) ?? null,
      zone: resolveZone(p.category as string),
      imageUrl: (p.image_url as string) ?? null,
      priceCents: (p.price_cents as number) ?? null,
      currency: (p.currency as string) ?? "USD",
      url: p.url as string,
      source,
      color,
      inUse: inUse.has(p.id as string),
      createdAt: p.created_at as string,
    }
  })
}
