import { beforeEach, describe, expect, it, vi } from "vitest"
import { NextRequest } from "next/server"

const getUser = vi.fn()
vi.mock("@supabase/ssr", () => ({
  createServerClient: () => ({ auth: { getUser } }),
}))

import { config, proxy } from "@/proxy"

const request = (path: string) => new NextRequest(new URL(path, "https://www.vancearchives.com"))

/** NextResponse.next() marks pass-through responses with this header. */
const passedThrough = (res: Response) => res.headers.get("x-middleware-next") === "1"
const redirectTarget = (res: Response) => {
  const location = res.headers.get("location")
  return location ? new URL(location).pathname : null
}

beforeEach(() => {
  getUser.mockReset()
  vi.stubEnv("ADMIN_EMAILS", "owner@example.com")
  vi.stubEnv("ADMIN_DEV_BYPASS", "")
  vi.stubEnv("NODE_ENV", "production")
})

describe("admin proxy (auth gate)", () => {
  it("only runs on /admin routes", () => {
    expect(config.matcher).toEqual(["/admin/:path*"])
  })

  it("always lets the login page through", async () => {
    const res = await proxy(request("/admin/login"))
    expect(passedThrough(res)).toBe(true)
    expect(getUser).not.toHaveBeenCalled()
  })

  it("redirects signed-out visitors to login", async () => {
    getUser.mockResolvedValue({ data: { user: null } })
    const res = await proxy(request("/admin/schedule"))
    expect(res.status).toBe(307)
    expect(redirectTarget(res)).toBe("/admin/login")
  })

  it("redirects signed-in users who are not on the allowlist", async () => {
    getUser.mockResolvedValue({ data: { user: { email: "intruder@example.com" } } })
    const res = await proxy(request("/admin/outfits"))
    expect(redirectTarget(res)).toBe("/admin/login")
  })

  it("lets allowlisted admins through (case-insensitive)", async () => {
    getUser.mockResolvedValue({ data: { user: { email: "Owner@Example.com" } } })
    const res = await proxy(request("/admin/schedule"))
    expect(passedThrough(res)).toBe(true)
  })

  it("ignores ADMIN_DEV_BYPASS in production", async () => {
    vi.stubEnv("ADMIN_DEV_BYPASS", "true")
    getUser.mockResolvedValue({ data: { user: null } })
    const res = await proxy(request("/admin/schedule"))
    expect(redirectTarget(res)).toBe("/admin/login")
  })

  it("honours ADMIN_DEV_BYPASS outside production without a session lookup", async () => {
    vi.stubEnv("ADMIN_DEV_BYPASS", "true")
    vi.stubEnv("NODE_ENV", "development")
    const res = await proxy(request("/admin/schedule"))
    expect(passedThrough(res)).toBe(true)
    expect(getUser).not.toHaveBeenCalled()
  })
})
