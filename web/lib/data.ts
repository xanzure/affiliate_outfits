import { Concept, Outfit, Product, ProductLayout } from "@/lib/types"
import { supabase } from "@/lib/supabase"

export async function getConcepts(): Promise<Concept[]> {
  // Only show concepts that have at least one outfit
  const { data: outfitConcepts, error: oErr } = await supabase
    .from("outfits")
    .select("concept_id")

  if (oErr) throw new Error(`getConcepts outfits: ${oErr.message}`)
  const conceptsWithOutfits = [...new Set((outfitConcepts ?? []).map((o) => o.concept_id))]
  if (conceptsWithOutfits.length === 0) return []

  const { data, error } = await supabase
    .from("concepts")
    .select("*")
    .eq("status", "active")
    .in("id", conceptsWithOutfits)
    .order("ranking_score", { ascending: false })

  if (error) throw new Error(`getConcepts: ${error.message}`)
  return (data ?? []).map(rowToConcept)
}

export async function getConcept(id: string): Promise<Concept | null> {
  const { data, error } = await supabase
    .from("concepts")
    .select("*")
    .eq("id", id)
    .single()

  if (error) return null
  return rowToConcept(data)
}

export async function getOutfitsForConcept(conceptId: string): Promise<Outfit[]> {
  const { data: outfitRows, error } = await supabase
    .from("outfits")
    .select("*")
    .eq("concept_id", conceptId)
    .order("created_at", { ascending: false })

  if (error) throw new Error(`getOutfitsForConcept: ${error.message}`)
  if (!outfitRows || outfitRows.length === 0) return []

  const allProductIds: string[] = outfitRows.flatMap((o) =>
    JSON.parse(o.product_ids_json ?? "[]")
  )
  const uniqueIds = [...new Set(allProductIds)]

  let productMap: Record<string, Product> = {}
  if (uniqueIds.length > 0) {
    const { data: productRows, error: pErr } = await supabase
      .from("products")
      .select("*")
      .in("id", uniqueIds)

    if (pErr) throw new Error(`getOutfitsForConcept products: ${pErr.message}`)
    productMap = Object.fromEntries((productRows ?? []).map((p) => [p.id, rowToProduct(p)]))
  }

  return outfitRows.map((row) => rowToOutfit(row, productMap))
}

// --- row mappers ---

function rowToConcept(row: Record<string, unknown>): Concept {
  return {
    id: row.id as string,
    seed: row.seed as string,
    status: row.status as Concept["status"],
    ranking_score: row.ranking_score as number,
    last_posted_date_est: (row.last_posted_date_est as string) ?? null,
    created_at: row.created_at as string,
    metadata: JSON.parse((row.metadata_json as string) ?? "{}"),
  }
}

function rowToProduct(row: Record<string, unknown>): Product {
  return {
    id: row.id as string,
    retailer: row.retailer as string,
    name: row.name as string,
    category: (row.category as string) ?? null,
    url: row.url as string,
    affiliate_url: (row.affiliate_url as string) ?? null,
    image_url: (row.image_url as string) ?? null,
    local_image_path: (row.local_image_path as string) ?? null,
    price_cents: (row.price_cents as number) ?? null,
    currency: (row.currency as string) ?? "USD",
  }
}

function rowToOutfit(row: Record<string, unknown>, productMap: Record<string, Product>): Outfit {
  const productIds: string[] = JSON.parse((row.product_ids_json as string) ?? "[]")
  const spec = JSON.parse((row.spec_json as string) ?? "{}")
  return {
    id: row.id as string,
    concept_id: (row.concept_id as string) ?? null,
    concept_seed: row.concept_seed as string,
    product_ids: productIds,
    products: productIds.map((id) => productMap[id]).filter(Boolean),
    collage_url: (row.collage_url as string) ?? null,
    spec: {
      layout: (spec.layout ?? []) as ProductLayout[],
      ...spec,
    },
    created_at: row.created_at as string,
    metadata: JSON.parse((row.metadata_json as string) ?? "{}"),
  }
}
