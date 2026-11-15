"use client"

import { useState } from "react"
import { Outfit, Product, ProductLayout } from "@/lib/types"
import ProductPanel from "./ProductPanel"

interface Props {
  outfit: Outfit
  index: number
}

function outfitNumber(index: number): string {
  return `#${String(index + 1).padStart(3, "0")}`
}

const isUrl = (v: unknown): v is string => typeof v === "string" && /^https?:\/\//.test(v)

export default function OutfitCanvas({ outfit, index }: Props) {
  const [selected, setSelected] = useState<Product | null>(null)
  const productMap = Object.fromEntries(outfit.products.map((p) => [p.id, p]))
  const layout = outfit.spec.layout ?? []

  // Preferred: show the rendered collage itself (pixel-identical to the cover)
  // with a clickable box over each product. Needs the image URL and full boxes.
  const collageUrl = outfit.spec.collage_url
  const canOverlay =
    isUrl(collageUrl) && layout.length > 0 && layout.every((item) => typeof item.height === "number")

  return (
    <div className="group/card">
      <div className="mb-4">
        <p className="font-mono text-[0.7rem] tracking-[0.28em] uppercase text-accent">
          {outfitNumber(index)}
        </p>
      </div>

      {canOverlay ? (
        <CollageWithHotspots
          collageUrl={collageUrl as string}
          layout={layout}
          productMap={productMap}
          onSelect={setSelected}
        />
      ) : (
        <RebuiltCanvas outfit={outfit} productMap={productMap} onSelect={setSelected} />
      )}

      {selected && (
        <ProductPanel product={selected} onClose={() => setSelected(null)} />
      )}
    </div>
  )
}

const FRAME =
  "relative w-full overflow-hidden rounded-sm ring-1 ring-line/70 shadow-[0_12px_34px_-18px_rgba(60,45,30,0.4)] transition-shadow duration-500 group-hover/card:shadow-[0_22px_48px_-18px_rgba(60,45,30,0.5)]"

function CollageWithHotspots({
  collageUrl,
  layout,
  productMap,
  onSelect,
}: {
  collageUrl: string
  layout: ProductLayout[]
  productMap: Record<string, Product>
  onSelect: (p: Product) => void
}) {
  return (
    <div className={FRAME}>
      <img src={collageUrl} alt="" draggable={false} className="block h-auto w-full" />
      {layout.map((item) => {
        const product = productMap[item.product_id]
        if (!product) return null
        return (
          <button
            key={item.product_id}
            onClick={() => onSelect(product)}
            aria-label={product.name}
            title={product.name}
            className="group absolute cursor-pointer focus:outline-none"
            style={{
              left: `${item.x}%`,
              top: `${item.y}%`,
              width: `${item.width}%`,
              height: `${item.height}%`,
              transform: `rotate(${item.rotation}deg)`,
              zIndex: item.z_index,
            }}
          >
            {/* The cutout sits exactly over the piece baked into the collage and
                lifts on hover/focus — invisible at rest, so the collage is untouched. */}
            {product.image_url && (
              <img
                src={product.image_url}
                alt=""
                draggable={false}
                className="h-full w-full object-contain opacity-0 transition-all duration-300 ease-out group-hover:-translate-y-1 group-hover:scale-[1.07] group-hover:opacity-100 group-hover:[filter:drop-shadow(0_12px_22px_rgba(40,30,20,0.42))_drop-shadow(0_0_18px_rgba(154,111,74,0.5))] group-focus-visible:opacity-100"
              />
            )}
          </button>
        )
      })}
    </div>
  )
}

function RebuiltCanvas({
  outfit,
  productMap,
  onSelect,
}: {
  outfit: Outfit
  productMap: Record<string, Product>
  onSelect: (p: Product) => void
}) {
  // Fallback for outfits without a rendered collage: rebuild from cutouts.
  const layout: ProductLayout[] = outfit.spec.layout?.length
    ? outfit.spec.layout
    : outfit.products.map((p, i) => ({
        product_id: p.id,
        x: 5 + (i % 2) * 48,
        y: 5 + Math.floor(i / 2) * 45,
        width: 40,
        rotation: (i % 3) - 1,
        z_index: i + 1,
      }))

  return (
    <div
      className={`${FRAME} bg-gradient-to-b from-[#efeae2] to-[#e3dccf]`}
      style={{ paddingBottom: "125%" }}
    >
      {layout.map((item) => {
        const product = productMap[item.product_id]
        if (!product) return null
        return (
          <button
            key={item.product_id}
            onClick={() => onSelect(product)}
            className="group absolute cursor-pointer focus:outline-none"
            style={{
              left: `${item.x}%`,
              top: `${item.y}%`,
              width: `${item.width}%`,
              ...(item.height ? { height: `${item.height}%` } : {}),
              transform: `rotate(${item.rotation}deg)`,
              zIndex: item.z_index,
            }}
          >
            <div className="relative h-full transition-transform duration-300 ease-out group-hover:-translate-y-1 group-hover:scale-110">
              {product.image_url ? (
                <img
                  src={product.image_url}
                  alt={product.name}
                  draggable={false}
                  className={`w-full object-contain [filter:drop-shadow(0_4px_8px_rgba(40,30,20,0.18))] transition-[filter] duration-300 group-hover:[filter:drop-shadow(0_12px_22px_rgba(40,30,20,0.42))_drop-shadow(0_0_18px_rgba(154,111,74,0.5))] ${item.height ? "h-full" : "h-auto"}`}
                />
              ) : (
                <div className="flex aspect-square w-full items-center justify-center bg-stone-300">
                  <span className="text-xs text-stone-400">{product.name}</span>
                </div>
              )}
            </div>
          </button>
        )
      })}
    </div>
  )
}
