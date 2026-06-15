export type ConceptStatus = "active" | "needs_review" | "retired"
export type Platform = "tiktok" | "pinterest" | "local"
export type PostStatus = "draft" | "scheduled" | "published" | "failed"

export interface Concept {
  id: string
  seed: string
  status: ConceptStatus
  ranking_score: number
  last_posted_date_est: string | null
  created_at: string
  metadata: {
    cover_image_url?: string | null
    display_name?: string
    [key: string]: unknown
  }
}

export interface Product {
  id: string
  retailer: string
  name: string
  category: string | null
  url: string
  affiliate_url: string | null
  image_url: string | null
  local_image_path: string | null
  price_cents: number | null
  currency: string
}

export interface ProductLayout {
  product_id: string
  x: number       // percent from left edge of canvas
  y: number       // percent from top edge of canvas
  width: number   // percent of canvas width
  rotation: number
  z_index: number
}

export interface Collage {
  id: string
  outfit_id: string
  image_path: string
  collage_url: string | null
  layout: Record<string, unknown>
  created_at: string
  metadata: Record<string, unknown>
}

export interface Outfit {
  id: string
  concept_id: string | null
  concept_seed: string
  product_ids: string[]
  products: Product[]
  collage_url: string | null
  spec: {
    layout: ProductLayout[]
    [key: string]: unknown
  }
  created_at: string
  metadata: Record<string, unknown>
}
