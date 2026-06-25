// Mirror of app/collage/export.py _resolve_zone so the Wardrobe tags/filter
// match the zones the collage engine uses. Head noun (last word) wins.

export const ZONES = [
  "outerwear",
  "top",
  "bottom",
  "dress",
  "shoe",
  "bag",
  "accessory",
] as const

export type Zone = (typeof ZONES)[number]

const CATEGORY_MAP: Record<string, Zone> = {
  coat: "outerwear", jacket: "outerwear", blazer: "outerwear", outerwear: "outerwear",
  trench: "outerwear", cardigan: "outerwear", vest: "outerwear", puffer: "outerwear", parka: "outerwear",
  top: "top", shirt: "top", blouse: "top", tee: "top", "t-shirt": "top", tshirt: "top",
  sweater: "top", knit: "top", turtleneck: "top", tank: "top", crop: "top", polo: "top", halter: "top",
  bottom: "bottom", pants: "bottom", trousers: "bottom", jeans: "bottom", skirt: "bottom",
  shorts: "bottom", leggings: "bottom", denim: "bottom", slacks: "bottom", chino: "bottom",
  dress: "dress", jumpsuit: "dress", romper: "dress", mini: "dress", maxi: "dress", bodysuit: "dress",
  shoe: "shoe", shoes: "shoe", boot: "shoe", boots: "shoe", sneaker: "shoe", sneakers: "shoe",
  loafer: "shoe", loafers: "shoe", sandal: "shoe", sandals: "shoe", heel: "shoe", heels: "shoe",
  mule: "shoe", flat: "shoe", oxford: "shoe",
  bag: "bag", purse: "bag", tote: "bag", clutch: "bag", backpack: "bag", crossbody: "bag",
  handbag: "bag", satchel: "bag",
  accessory: "accessory", accessories: "accessory", belt: "accessory", scarf: "accessory",
  hat: "accessory", cap: "accessory", jewelry: "accessory", necklace: "accessory", ring: "accessory",
  bracelet: "accessory", earring: "accessory", earrings: "accessory", sunglasses: "accessory",
  glasses: "accessory", watch: "accessory", sock: "accessory", socks: "accessory",
}

export function resolveZone(category: string | null | undefined): Zone {
  if (!category) return "accessory"
  const c = category.toLowerCase().trim()
  if (CATEGORY_MAP[c]) return CATEGORY_MAP[c]
  const words = c.match(/[a-z]+/g) ?? []
  for (const w of [...words].reverse()) if (CATEGORY_MAP[w]) return CATEGORY_MAP[w]
  for (const [k, z] of Object.entries(CATEGORY_MAP)) if (c.includes(k)) return z
  return "accessory"
}
