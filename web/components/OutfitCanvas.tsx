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
    <div>
      <p className="text-xs tracking-widest text-stone-400 uppercase mb-4">
        {outfitNumber(index)}
      </p>

      <div className="relative w-full bg-[#edeae5]" style={{ paddingBottom: "120%" }}>
        {layout.map((item) => {
          const product = productMap[item.product_id]
          if (!product) return null

          return (
            <button
              key={item.product_id}
              onClick={() => setSelected(product)}
              className="absolute group focus:outline-none"
              style={{
                left: `${item.x}%`,
                top: `${item.y}%`,
                width: `${item.width}%`,
                transform: `rotate(${item.rotation}deg)`,
                zIndex: item.z_index,
              }}
            >
              <div className="relative transition-all duration-200 group-hover:scale-105">
                <div className="absolute inset-0 rounded-sm opacity-0 group-hover:opacity-100 transition-opacity duration-200 shadow-[0_0_20px_6px_rgba(255,255,255,0.7)]" />
                {product.image_url ? (
                  <img
                    src={product.image_url}
                    alt={product.name}
                    className="w-full h-auto object-contain drop-shadow-md"
                    draggable={false}
                  />
                ) : (
                  <div className="w-full aspect-square bg-stone-300 flex items-center justify-center">
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
