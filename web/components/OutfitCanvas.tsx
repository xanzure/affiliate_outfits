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

export default function OutfitCanvas({ outfit, index }: Props) {
  const [selected, setSelected] = useState<Product | null>(null)

  const productMap = Object.fromEntries(outfit.products.map((p) => [p.id, p]))

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
    <div className="group/card">
      <div className="mb-4">
        <p className="font-mono text-[0.7rem] tracking-[0.28em] uppercase text-accent">
          {outfitNumber(index)}
        </p>
      </div>

      <div
        className="relative w-full overflow-hidden rounded-sm bg-gradient-to-b from-[#efeae2] to-[#e3dccf] ring-1 ring-line/70 shadow-[0_12px_34px_-18px_rgba(60,45,30,0.4)] transition-shadow duration-500 group-hover/card:shadow-[0_22px_48px_-18px_rgba(60,45,30,0.5)]"
        style={{ paddingBottom: "120%" }}
      >
        {layout.map((item) => {
          const product = productMap[item.product_id]
          if (!product) return null

          return (
            <button
              key={item.product_id}
              onClick={() => setSelected(product)}
              className="group absolute cursor-pointer focus:outline-none"
              style={{
                left: `${item.x}%`,
                top: `${item.y}%`,
                width: `${item.width}%`,
                transform: `rotate(${item.rotation}deg)`,
                zIndex: item.z_index,
              }}
            >
              <div className="relative transition-transform duration-300 ease-out group-hover:-translate-y-1 group-hover:scale-110">
                {product.image_url ? (
                  <img
                    src={product.image_url}
                    alt={product.name}
                    draggable={false}
                    className="h-auto w-full object-contain [filter:drop-shadow(0_4px_8px_rgba(40,30,20,0.18))] transition-[filter] duration-300 group-hover:[filter:drop-shadow(0_12px_22px_rgba(40,30,20,0.42))_drop-shadow(0_0_18px_rgba(154,111,74,0.5))]"
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

      {selected && (
        <ProductPanel product={selected} onClose={() => setSelected(null)} />
      )}
    </div>
  )
}
