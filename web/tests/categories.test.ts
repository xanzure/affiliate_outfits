import { describe, expect, it } from "vitest"
import { resolveZone } from "@/lib/categories"

describe("resolveZone", () => {
  it("maps exact category names", () => {
    expect(resolveZone("jacket")).toBe("outerwear")
    expect(resolveZone("jeans")).toBe("bottom")
    expect(resolveZone("sneakers")).toBe("shoe")
    expect(resolveZone("tote")).toBe("bag")
  })

  it("is case- and whitespace-insensitive", () => {
    expect(resolveZone("  Blazer ")).toBe("outerwear")
    expect(resolveZone("DRESS")).toBe("dress")
  })

  it("lets the head noun (last word) win", () => {
    // "mini" alone means dress, but in "mini bag" the head noun is bag —
    // the bug the right-to-left scan exists to prevent.
    expect(resolveZone("mini bag")).toBe("bag")
    expect(resolveZone("leather crossbody bag")).toBe("bag")
    expect(resolveZone("knit dress")).toBe("dress")
    expect(resolveZone("denim jacket")).toBe("outerwear")
  })

  it("falls back to a substring match when no whole word matches", () => {
    expect(resolveZone("overcoat")).toBe("outerwear")
  })

  it("defaults to accessory for empty or unknown categories", () => {
    expect(resolveZone(null)).toBe("accessory")
    expect(resolveZone(undefined)).toBe("accessory")
    expect(resolveZone("")).toBe("accessory")
    expect(resolveZone("zzz")).toBe("accessory")
  })
})
