import { createAdminClient } from "@/lib/supabase/admin"

/** Set to true to enable automatic FIFO scheduling of the 3-day slot window. */
const AUTO_SCHEDULE_ENABLED = false

export interface AdminPost {
  id: string
  platform: "tiktok" | "pinterest" | "local"
  status: string
  caption: string | null
  scheduled_for: string | null
  is_manual_schedule: boolean
  approved: boolean
  concept_id: string | null
  outfit_id: string | null
  conceptName: string | null
  slides: string[]
  linkCheck: { checked_at?: string; dead?: string[] } | null
}

export interface ScheduleData {
  needsApproval: AdminPost[]
  scheduled: AdminPost[]
  queue: AdminPost[]
}

const PINTEREST_SLOT_HOURS = [10, 12, 14, 16, 18]
const TIKTOK_SLOT_HOURS = [12]
const WINDOW_DAYS = 3
const EST_OFFSET = "-04:00" // EDT (June)

function meta(row: Record<string, unknown>): Record<string, unknown> {
  try {
    return JSON.parse((row.metadata_json as string) ?? "{}")
  } catch {
    return {}
  }
}

function resolveSlides(
  row: Record<string, unknown>,
  collageByOutfit: Record<string, string>
): string[] {
  const m = meta(row)
  const slideUrls = m.slide_urls as string[] | undefined
  if (Array.isArray(slideUrls) && slideUrls.length) return slideUrls.filter(Boolean)
  const outfitIds = (m.outfit_ids as string[] | undefined) ?? []
  const fromOutfits = outfitIds.map((id) => collageByOutfit[id]).filter(Boolean)
  if (fromOutfits.length) return fromOutfits
  const single = collageByOutfit[(row.outfit_id as string) ?? ""]
  return single ? [single] : []
}

function toAdminPost(
  row: Record<string, unknown>,
  conceptNames: Record<string, string>,
  collageByOutfit: Record<string, string>
): AdminPost {
  let linkCheck = null
  if (row.link_check) {
    try {
      linkCheck = JSON.parse(row.link_check as string)
    } catch {
      linkCheck = null
    }
  }
  return {
    id: row.id as string,
    platform: row.platform as AdminPost["platform"],
    status: row.status as string,
    caption: (row.caption as string) ?? null,
    scheduled_for: (row.scheduled_for as string) ?? null,
    is_manual_schedule: Boolean(row.is_manual_schedule),
    approved: Boolean(row.approved),
    concept_id: (row.concept_id as string) ?? null,
    outfit_id: (row.outfit_id as string) ?? null,
    conceptName: conceptNames[(row.concept_id as string) ?? ""] ?? null,
    slides: resolveSlides(row, collageByOutfit),
    linkCheck,
  }
}

async function loadLookups(sb: ReturnType<typeof createAdminClient>) {
  const [{ data: concepts }, { data: collages }] = await Promise.all([
    sb.from("concepts").select("id, seed, metadata_json"),
    sb.from("collages").select("outfit_id, collage_url"),
  ])
  const conceptNames: Record<string, string> = {}
  for (const c of concepts ?? []) {
    const m = (() => {
      try {
        return JSON.parse((c.metadata_json as string) ?? "{}")
      } catch {
        return {}
      }
    })()
    conceptNames[c.id] = (m.display_name as string) ?? (c.seed as string)
  }
  const collageByOutfit: Record<string, string> = {}
  for (const c of collages ?? []) {
    if (c.collage_url) collageByOutfit[c.outfit_id as string] = c.collage_url as string
  }
  return { conceptNames, collageByOutfit }
}

/** Fill the rolling window of scheduled slots from the FIFO queue. */
export async function reconcileSchedule(): Promise<void> {
  if (!AUTO_SCHEDULE_ENABLED) return
  const sb = createAdminClient()
  const { data: scheduled } = await sb
    .from("posts")
    .select("platform, scheduled_for")
    .eq("status", "scheduled")
  const filled = new Set(
    (scheduled ?? []).map((p) => `${p.platform}@${p.scheduled_for}`)
  )

  const now = new Date()
  const updates: { id: string; scheduled_for: string }[] = []

  const queues: Record<string, Record<string, unknown>[]> = {}
  for (const platform of ["pinterest", "tiktok"]) {
    const { data } = await sb
      .from("posts")
      .select("*")
      .eq("platform", platform)
      .eq("status", "draft")
      .eq("approved", true)
      .is("scheduled_for", null)
      .order("queue_order", { ascending: true })
    queues[platform] = (data ?? []) as Record<string, unknown>[]
  }

  for (let day = 0; day < WINDOW_DAYS; day++) {
    const d = new Date(now)
    d.setDate(d.getDate() + day)
    const ymd = d.toISOString().slice(0, 10)
    const plans: [string, number[]][] = [
      ["pinterest", PINTEREST_SLOT_HOURS],
      ["tiktok", TIKTOK_SLOT_HOURS],
    ]
    for (const [platform, hours] of plans) {
      for (const h of hours) {
        const slotISO = `${ymd}T${String(h).padStart(2, "0")}:00:00${EST_OFFSET}`
        if (new Date(slotISO) <= now) continue
        if (filled.has(`${platform}@${slotISO}`)) continue
        const next = queues[platform].shift()
        if (!next) continue
        updates.push({ id: next.id as string, scheduled_for: slotISO })
        filled.add(`${platform}@${slotISO}`)
      }
    }
  }

  for (const u of updates) {
    await sb
      .from("posts")
      .update({
        status: "scheduled",
        scheduled_for: u.scheduled_for,
        is_manual_schedule: false,
        updated_at: new Date().toISOString(),
      })
      .eq("id", u.id)
  }
}

export interface AdminOutfitProduct {
  id: string
  name: string
  retailer: string
  category: string | null
  price_cents: number | null
  currency: string
  url: string
  affiliate_url: string | null
}

export interface AdminOutfit {
  id: string
  conceptName: string | null
  conceptActive: boolean
  collageUrl: string | null
  createdAt: string
  posted: boolean
  scheduled: boolean
  onSite: boolean
  products: AdminOutfitProduct[]
}

export async function getOutfits(): Promise<AdminOutfit[]> {
  const sb = createAdminClient()
  const [{ data: outfits }, { data: collages }, { data: posts }, { data: concepts }, { data: products }] =
    await Promise.all([
      sb.from("outfits").select("*").order("created_at", { ascending: false }),
      sb.from("collages").select("outfit_id, collage_url"),
      sb.from("posts").select("outfit_id, status, metadata_json"),
      sb.from("concepts").select("id, seed, status, metadata_json"),
      sb.from("products").select("*"),
    ])

  const collageByOutfit: Record<string, string> = {}
  for (const c of collages ?? []) if (c.collage_url) collageByOutfit[c.outfit_id as string] = c.collage_url as string

  const conceptInfo: Record<string, { name: string; active: boolean }> = {}
  for (const c of concepts ?? []) {
    let name = c.seed as string
    try {
      const m = JSON.parse((c.metadata_json as string) ?? "{}")
      if (m.display_name) name = m.display_name
    } catch {}
    conceptInfo[c.id as string] = { name, active: c.status === "active" }
  }

  const productMap: Record<string, AdminOutfitProduct> = {}
  for (const p of products ?? []) {
    productMap[p.id as string] = {
      id: p.id as string,
      name: p.name as string,
      retailer: p.retailer as string,
      category: (p.category as string) ?? null,
      price_cents: (p.price_cents as number) ?? null,
      currency: (p.currency as string) ?? "USD",
      url: p.url as string,
      affiliate_url: (p.affiliate_url as string) ?? null,
    }
  }

  // posts grouped by outfit for status flags
  const postsByOutfit: Record<string, string[]> = {}
  for (const post of posts ?? []) {
    const oid = post.outfit_id as string
    if (!oid) continue
    ;(postsByOutfit[oid] ??= []).push(post.status as string)
    // slideshow posts reference multiple outfit_ids in metadata
    try {
      const m = JSON.parse((post.metadata_json as string) ?? "{}")
      for (const extra of (m.outfit_ids as string[] | undefined) ?? []) {
        ;(postsByOutfit[extra] ??= []).push(post.status as string)
      }
    } catch {}
  }

  return (outfits ?? []).map((row) => {
    const id = row.id as string
    const conceptId = (row.concept_id as string) ?? ""
    const ci = conceptInfo[conceptId] ?? { name: row.concept_seed as string, active: false }
    const statuses = postsByOutfit[id] ?? []
    let layoutLen = 0
    try {
      layoutLen = (JSON.parse((row.spec_json as string) ?? "{}").layout ?? []).length
    } catch {}
    const productIds: string[] = (() => {
      try {
        return JSON.parse((row.product_ids_json as string) ?? "[]")
      } catch {
        return []
      }
    })()
    const collageUrl = collageByOutfit[id] ?? null
    return {
      id,
      conceptName: ci.name,
      conceptActive: ci.active,
      collageUrl,
      createdAt: row.created_at as string,
      posted: statuses.includes("published"),
      scheduled: statuses.includes("scheduled"),
      onSite: ci.active && !!collageUrl && layoutLen > 0,
      products: productIds.map((pid) => productMap[pid]).filter(Boolean),
    }
  })
}

export interface ConceptPerf {
  id: string
  name: string
  status: string
  ranking_score: number
  usage_count: number
}

export interface PostMetric {
  post_id: string
  platform: string
  conceptName: string | null
  views: number
  likes: number
  clicks: number
  saves: number
  score: number
}

export interface MetricsData {
  totals: { views: number; clicks: number; saves: number; avgScore: number }
  concepts: ConceptPerf[]
  posts: PostMetric[]
  postOptions: { id: string; label: string }[]
}

export async function getMetricsData(): Promise<MetricsData> {
  const sb = createAdminClient()
  const [{ data: metrics }, { data: concepts }, { data: posts }] = await Promise.all([
    sb.from("metrics").select("*"),
    sb.from("concepts").select("id, seed, status, ranking_score, usage_count, metadata_json"),
    sb.from("posts").select("id, platform, concept_id, caption"),
  ])

  const conceptName: Record<string, string> = {}
  const conceptPerf: ConceptPerf[] = (concepts ?? []).map((c) => {
    let name = c.seed as string
    try {
      const m = JSON.parse((c.metadata_json as string) ?? "{}")
      if (m.display_name) name = m.display_name
    } catch {}
    conceptName[c.id as string] = name
    return {
      id: c.id as string,
      name,
      status: c.status as string,
      ranking_score: (c.ranking_score as number) ?? 50,
      usage_count: (c.usage_count as number) ?? 0,
    }
  })
  conceptPerf.sort((a, b) => a.ranking_score - b.ranking_score)

  const postConcept: Record<string, string | null> = {}
  const postOptions: { id: string; label: string }[] = []
  for (const p of posts ?? []) {
    postConcept[p.id as string] = (p.concept_id as string) ?? null
    const label = `${p.platform} · ${conceptName[(p.concept_id as string) ?? ""] ?? "—"} · ${(p.caption as string ?? "").slice(0, 28)}`
    postOptions.push({ id: p.id as string, label })
  }

  // latest metric per post
  const latest: Record<string, Record<string, unknown>> = {}
  for (const m of metrics ?? []) {
    const pid = m.post_id as string
    if (!latest[pid] || (m.collected_at as string) > (latest[pid].collected_at as string)) {
      latest[pid] = m
    }
  }

  const totals = { views: 0, clicks: 0, saves: 0, avgScore: 0 }
  const postMetrics: PostMetric[] = Object.values(latest).map((m) => {
    totals.views += (m.views as number) ?? 0
    totals.clicks += (m.clicks as number) ?? 0
    totals.saves += (m.saves as number) ?? 0
    const cid = postConcept[m.post_id as string] ?? ""
    return {
      post_id: m.post_id as string,
      platform: m.platform as string,
      conceptName: conceptName[cid] ?? null,
      views: (m.views as number) ?? 0,
      likes: (m.likes as number) ?? 0,
      clicks: (m.clicks as number) ?? 0,
      saves: (m.saves as number) ?? 0,
      score: (m.score as number) ?? 0,
    }
  })
  totals.avgScore = postMetrics.length
    ? Math.round((postMetrics.reduce((s, p) => s + p.score, 0) / postMetrics.length) * 10) / 10
    : 0

  return { totals, concepts: conceptPerf, posts: postMetrics, postOptions }
}

export async function getConceptOptions(): Promise<{ id: string; name: string }[]> {
  const sb = createAdminClient()
  const { data } = await sb
    .from("concepts")
    .select("id, seed, status, metadata_json")
    .eq("status", "active")
    .order("ranking_score", { ascending: false })
  return (data ?? []).map((c) => {
    let name = c.seed as string
    try {
      const m = JSON.parse((c.metadata_json as string) ?? "{}")
      if (m.display_name) name = m.display_name
    } catch {}
    return { id: c.id as string, name }
  })
}

export interface ActivityEntry {
  id: string
  action: string
  target_id: string | null
  created_at: string
}

export async function getActivity(limit = 100): Promise<ActivityEntry[]> {
  const sb = createAdminClient()
  const { data } = await sb
    .from("admin_actions")
    .select("*")
    .order("created_at", { ascending: false })
    .limit(limit)
  return (data ?? []).map((a) => ({
    id: a.id as string,
    action: a.action as string,
    target_id: (a.target_id as string) ?? null,
    created_at: a.created_at as string,
  }))
}

export async function getScheduleData(): Promise<ScheduleData> {
  const sb = createAdminClient()
  const { conceptNames, collageByOutfit } = await loadLookups(sb)
  const { data: rows } = await sb.from("posts").select("*")
  const posts = (rows ?? []).map((r) =>
    toAdminPost(r as Record<string, unknown>, conceptNames, collageByOutfit)
  )

  const needsApproval = posts.filter(
    (p) => p.status === "draft" && !p.approved
  )
  const scheduled = posts
    .filter((p) => p.status === "scheduled")
    .sort((a, b) => (a.scheduled_for ?? "").localeCompare(b.scheduled_for ?? ""))
  const queue = posts
    .filter((p) => p.status === "draft" && p.approved && !p.scheduled_for)
    .sort((a, b) => a.id.localeCompare(b.id))

  return { needsApproval, scheduled, queue }
}
