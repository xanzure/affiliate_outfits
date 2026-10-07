import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { createFakeSupabase, type Row } from "./fakeSupabase"

let fake = createFakeSupabase()
vi.mock("@/lib/supabase/admin", () => ({ createAdminClient: () => fake.client }))

import { getMetricsData, getOutfits, getScheduleData } from "@/lib/admin"

const NOW = new Date("2026-10-07T12:00:00Z")
const hoursAgo = (h: number) => new Date(NOW.getTime() - h * 3600_000).toISOString()

function post(overrides: Row): Row {
  return {
    id: "p",
    platform: "pinterest",
    status: "draft",
    approved: false,
    caption: "caption",
    queue_order: null,
    concept_id: "c1",
    outfit_id: "o1",
    published_at: null,
    metadata_json: "{}",
    link_check: null,
    ...overrides,
  }
}

function seed(posts: Row[], extra: Record<string, Row[]> = {}) {
  fake = createFakeSupabase({
    concepts: [{ id: "c1", seed: "raw seed", metadata_json: JSON.stringify({ display_name: "Night Out" }) }],
    collages: [
      { outfit_id: "o1", collage_url: "https://cdn/o1.png" },
      { outfit_id: "o2", collage_url: "https://cdn/o2.png" },
    ],
    posts,
    ...extra,
  })
}

beforeEach(() => {
  vi.useFakeTimers()
  vi.setSystemTime(NOW)
})
afterEach(() => {
  vi.useRealTimers()
})

describe("getScheduleData — sections", () => {
  it("buckets posts into needs-approval, per-platform queues, and failed", async () => {
    seed([
      post({ id: "draft", approved: false }),
      post({ id: "q-pin", approved: true, queue_order: "1" }),
      post({ id: "q-tt", platform: "tiktok", approved: true, queue_order: "1" }),
      post({ id: "bad", status: "failed", metadata_json: JSON.stringify({ api_error: "401 token" }) }),
      post({ id: "live", status: "published", published_at: hoursAgo(100) }),
    ])
    const data = await getScheduleData()

    expect(data.needsApproval.map((p) => p.id)).toEqual(["draft"])
    expect(data.queues.pinterest.map((p) => p.id)).toEqual(["q-pin"])
    expect(data.queues.tiktok.map((p) => p.id)).toEqual(["q-tt"])
    expect(data.failed.map((p) => p.id)).toEqual(["bad"])
    expect(data.failed[0].apiError).toBe("401 token")
  })

  it("orders each queue FIFO by the zero-padded queue_order key", async () => {
    // Reorder keys (small ints) sort ahead of approve keys (epoch millis) —
    // only correct because both are zero-padded to the same width.
    const key = (n: number) => String(n).padStart(15, "0")
    seed([
      post({ id: "approved-later", approved: true, queue_order: key(1_791_000_000_000) }),
      post({ id: "moved-to-top", approved: true, queue_order: key(0) }),
      post({ id: "second", approved: true, queue_order: key(1) }),
    ])
    const { queues } = await getScheduleData()
    expect(queues.pinterest.map((p) => p.id)).toEqual(["moved-to-top", "second", "approved-later"])
  })

  it("resolves concept display names and slide images", async () => {
    seed([
      post({ id: "single", outfit_id: "o1" }),
      post({
        id: "slideshow",
        platform: "tiktok",
        outfit_id: null,
        metadata_json: JSON.stringify({ outfit_ids: ["o1", "o2", "missing"] }),
      }),
      post({ id: "explicit", metadata_json: JSON.stringify({ slide_urls: ["https://x/1.png", ""] }) }),
    ])
    const byId = Object.fromEntries((await getScheduleData()).needsApproval.map((p) => [p.id, p]))

    expect(byId.single.conceptName).toBe("Night Out")
    expect(byId.single.slides).toEqual(["https://cdn/o1.png"])
    expect(byId.slideshow.slides).toEqual(["https://cdn/o1.png", "https://cdn/o2.png"])
    expect(byId.explicit.slides).toEqual(["https://x/1.png"])
  })

  it("survives malformed metadata and link_check JSON", async () => {
    seed([post({ id: "junk", metadata_json: "{not json", link_check: "nope" })])
    const [p] = (await getScheduleData()).needsApproval
    expect(p.apiError).toBeNull()
    expect(p.linkCheck).toBeNull()
    expect(p.slides).toEqual(["https://cdn/o1.png"])
  })
})

describe("getScheduleData — per-platform 24h cooldown", () => {
  it("is ready immediately when a platform has never posted", async () => {
    seed([post({ id: "q", approved: true, queue_order: "1" })])
    const { cooldowns } = await getScheduleData()
    expect(cooldowns).toEqual({ tiktok: { readyAt: null }, pinterest: { readyAt: null } })
  })

  it("counts down 24h from the last publish on that platform only", async () => {
    seed([post({ id: "live", status: "published", published_at: hoursAgo(3) })])
    const { cooldowns } = await getScheduleData()
    expect(cooldowns.pinterest.readyAt).toBe(new Date(NOW.getTime() + 21 * 3600_000).toISOString())
    expect(cooldowns.tiktok.readyAt).toBeNull()
  })

  it("is ready again once the window has elapsed", async () => {
    seed([post({ id: "live", status: "published", published_at: hoursAgo(25) })])
    expect((await getScheduleData()).cooldowns.pinterest.readyAt).toBeNull()
  })

  it("counts failed attempts (last_publish_attempt_at) so a bad token can't drain the queue", async () => {
    seed([
      post({ id: "old", status: "published", published_at: hoursAgo(30) }),
      post({
        id: "failed",
        status: "failed",
        metadata_json: JSON.stringify({ last_publish_attempt_at: hoursAgo(1) }),
      }),
    ])
    const { cooldowns } = await getScheduleData()
    expect(cooldowns.pinterest.readyAt).toBe(new Date(NOW.getTime() + 23 * 3600_000).toISOString())
  })
})

describe("getOutfits — status flags", () => {
  it("derives posted / queued / onSite and links slideshow posts to every outfit", async () => {
    fake = createFakeSupabase({
      outfits: [
        {
          id: "o1",
          concept_id: "c1",
          created_at: "2026-10-01",
          spec_json: JSON.stringify({ layout: [{ product_id: "pr1" }] }),
          product_ids_json: JSON.stringify(["pr1", "gone"]),
        },
        { id: "o2", concept_id: "c1", created_at: "2026-10-02", spec_json: "{}", product_ids_json: "[]" },
      ],
      collages: [{ outfit_id: "o1", collage_url: "https://cdn/o1.png" }],
      concepts: [{ id: "c1", seed: "s", status: "active", metadata_json: "{}" }],
      products: [{ id: "pr1", name: "Boot", retailer: "R", url: "https://r/boot" }],
      posts: [
        post({ id: "pin", outfit_id: "o1", status: "published" }),
        // Real slideshows set outfit_id = outfit_ids[0] (see tiktok_service.py),
        // so o1 is referenced both ways and must still list the post once.
        post({
          id: "tt",
          platform: "tiktok",
          outfit_id: "o1",
          approved: true,
          metadata_json: JSON.stringify({ outfit_ids: ["o1", "o2"] }),
        }),
      ],
    })
    const byId = Object.fromEntries((await getOutfits()).map((o) => [o.id, o]))

    expect(byId.o1).toMatchObject({ posted: true, queued: true, onSite: true, conceptName: "s" })
    expect(byId.o1.posts.map((p) => p.id)).toEqual(["pin", "tt"])
    expect(byId.o1.products.map((p) => p.id)).toEqual(["pr1"]) // dangling id dropped
    expect(byId.o2).toMatchObject({ posted: false, queued: true, onSite: false })
    expect(byId.o2.posts.map((p) => p.id)).toEqual(["tt"])
  })
})

describe("getMetricsData", () => {
  it("uses only the latest metric per post for totals and averages", async () => {
    fake = createFakeSupabase({
      concepts: [
        { id: "c1", seed: "a", status: "active", ranking_score: 80, usage_count: 2, metadata_json: "{}" },
        { id: "c2", seed: "b", status: "active", ranking_score: 20, usage_count: 1, metadata_json: "{}" },
      ],
      posts: [
        { id: "p1", platform: "pinterest", concept_id: "c1", caption: "one" },
        { id: "p2", platform: "tiktok", concept_id: "c2", caption: "two" },
      ],
      metrics: [
        { post_id: "p1", platform: "pinterest", collected_at: "2026-10-01", views: 10, clicks: 1, saves: 1, score: 1 },
        { post_id: "p1", platform: "pinterest", collected_at: "2026-10-05", views: 100, clicks: 5, saves: 3, score: 4 },
        { post_id: "p2", platform: "tiktok", collected_at: "2026-10-03", views: 50, clicks: 2, saves: 0, score: 2.5 },
      ],
    })
    const data = await getMetricsData()

    expect(data.totals).toEqual({ views: 150, clicks: 7, saves: 3, avgScore: 3.3 })
    expect(data.posts.find((p) => p.post_id === "p1")?.conceptName).toBe("a")
    // weakest concepts first, so the dashboard surfaces what to retire
    expect(data.concepts.map((c) => c.id)).toEqual(["c2", "c1"])
  })

  it("returns zeroed totals with no metrics", async () => {
    fake = createFakeSupabase({ concepts: [], posts: [], metrics: [] })
    expect((await getMetricsData()).totals).toEqual({ views: 0, clicks: 0, saves: 0, avgScore: 0 })
  })
})
