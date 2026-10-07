import { beforeEach, describe, expect, it, vi } from "vitest"

const getUser = vi.fn()
vi.mock("@/lib/supabase/server", () => ({
  createSupabaseServerClient: async () => ({ auth: { getUser } }),
}))

import { adminEmails, devBypass, getAdminUser, isAllowedEmail } from "@/lib/auth"

beforeEach(() => {
  getUser.mockReset()
  vi.stubEnv("ADMIN_EMAILS", " Owner@Example.com, second@example.com ,")
  vi.stubEnv("ADMIN_DEV_BYPASS", "")
  vi.stubEnv("NODE_ENV", "test")
})

describe("admin allowlist", () => {
  it("parses ADMIN_EMAILS: trims, lowercases, drops blanks", () => {
    expect(adminEmails()).toEqual(["owner@example.com", "second@example.com"])
  })

  it("matches emails case-insensitively", () => {
    expect(isAllowedEmail("OWNER@example.com")).toBe(true)
    expect(isAllowedEmail("intruder@example.com")).toBe(false)
  })

  it("rejects missing emails", () => {
    expect(isAllowedEmail(null)).toBe(false)
    expect(isAllowedEmail(undefined)).toBe(false)
    expect(isAllowedEmail("")).toBe(false)
  })

  it("allows nobody when ADMIN_EMAILS is unset", () => {
    vi.stubEnv("ADMIN_EMAILS", "")
    expect(adminEmails()).toEqual([])
    expect(isAllowedEmail("owner@example.com")).toBe(false)
  })
})

describe("devBypass", () => {
  it("is off unless explicitly enabled", () => {
    expect(devBypass()).toBe(false)
  })

  it("turns on with ADMIN_DEV_BYPASS=true outside production", () => {
    vi.stubEnv("ADMIN_DEV_BYPASS", "true")
    expect(devBypass()).toBe(true)
  })

  it("can never turn on in production", () => {
    vi.stubEnv("ADMIN_DEV_BYPASS", "true")
    vi.stubEnv("NODE_ENV", "production")
    expect(devBypass()).toBe(false)
  })
})

describe("getAdminUser", () => {
  it("returns the session user when allowlisted", async () => {
    getUser.mockResolvedValue({ data: { user: { id: "u1", email: "owner@example.com" } } })
    expect(await getAdminUser()).toMatchObject({ id: "u1" })
  })

  it("returns null for a signed-in user who is not allowlisted", async () => {
    getUser.mockResolvedValue({ data: { user: { id: "u2", email: "intruder@example.com" } } })
    expect(await getAdminUser()).toBeNull()
  })

  it("returns null when signed out", async () => {
    getUser.mockResolvedValue({ data: { user: null } })
    expect(await getAdminUser()).toBeNull()
  })

  it("skips the session lookup under dev bypass", async () => {
    vi.stubEnv("ADMIN_DEV_BYPASS", "true")
    expect(await getAdminUser()).toEqual({ email: "owner@example.com", id: "dev-bypass" })
    expect(getUser).not.toHaveBeenCalled()
  })
})
