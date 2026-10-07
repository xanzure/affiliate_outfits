import { beforeEach, describe, expect, it, vi } from "vitest"
import { createFakeSupabase } from "./fakeSupabase"

let fake = createFakeSupabase()
vi.mock("@/lib/supabase/admin", () => ({ createAdminClient: () => fake.client }))
vi.mock("next/cache", () => ({ revalidatePath: vi.fn() }))
// vi.mock is hoisted above plain consts, so the eagerly-read mock must be too.
const { enqueueJob } = vi.hoisted(() => ({ enqueueJob: vi.fn(async () => "job_123") }))
vi.mock("@/app/admin/(dashboard)/job-actions", () => ({ enqueueJob }))

import {
  approvePost,
  deletePost,
  postNow,
  reorderQueue,
} from "@/app/admin/(dashboard)/schedule/actions"

const writes = (table: string, op: string) => fake.calls.filter((c) => c.table === table && c.op === op)

beforeEach(() => {
  fake = createFakeSupabase()
  enqueueJob.mockClear()
})

describe("approvePost", () => {
  it("approves and appends to the queue tail with an epoch-millis key", async () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date("2026-10-07T12:00:00Z"))
    await approvePost("p1")
    vi.useRealTimers()

    const [update] = writes("posts", "update")
    expect(update.filters).toEqual([["id", "p1"]])
    expect(update.payload).toMatchObject({
      approved: true,
      queue_order: String(Date.parse("2026-10-07T12:00:00Z")).padStart(15, "0"),
    })
    expect(writes("admin_actions", "insert")[0].payload).toMatchObject({ action: "approve", target_id: "p1" })
  })
})

describe("reorderQueue", () => {
  it("rewrites queue_order as fixed-width sequential keys", async () => {
    await reorderQueue(["c", "a", "b"])
    const updates = writes("posts", "update").map((c) => [
      c.filters[0][1],
      (c.payload as { queue_order: string }).queue_order,
    ])
    expect(updates).toEqual([
      ["c", "000000000000000"],
      ["a", "000000000000001"],
      ["b", "000000000000002"],
    ])
  })
})

describe("postNow", () => {
  it("hands the publish to the worker and returns the job id", async () => {
    expect(await postNow("p9")).toBe("job_123")
    expect(enqueueJob).toHaveBeenCalledWith("retry_post", { post_id: "p9" })
  })
})

describe("deletePost", () => {
  it("deletes unpublished posts", async () => {
    fake = createFakeSupabase({ posts: [{ status: "draft" }] })
    await deletePost("p1")
    expect(writes("posts", "delete")[0].filters).toEqual([["id", "p1"]])
  })

  it("refuses to delete a published post", async () => {
    fake = createFakeSupabase({ posts: [{ status: "published" }] })
    await expect(deletePost("p1")).rejects.toThrow("Cannot delete a published post")
    expect(writes("posts", "delete")).toHaveLength(0)
  })
})
