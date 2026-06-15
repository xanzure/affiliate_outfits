"use client"

import { Product } from "@/lib/types"

interface Props {
  product: Product
  onClose: () => void
}

function formatPrice(cents: number | null, currency: string): string {
  if (cents === null) return "Price unavailable"
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
  }).format(cents / 100)
}

export default function ProductPanel({ product, onClose }: Props) {
  const href = product.affiliate_url ?? product.url

  return (
    <div
      className="fixed inset-0 z-50 flex items-end sm:items-center justify-center"
      onClick={onClose}
    >
      <div className="absolute inset-0 bg-stone-900/20 backdrop-blur-[2px]" />
      <div
        className="relative z-10 w-full max-w-sm bg-[#f5f2ee] p-8 shadow-xl sm:mx-4"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-stone-400 hover:text-stone-700 transition-colors text-xs tracking-widest uppercase"
        >
          Close
        </button>

        {product.image_url && (
          <div className="mb-6 aspect-square w-24 overflow-hidden bg-stone-100">
            <img
              src={product.image_url}
              alt={product.name}
              className="h-full w-full object-contain"
            />
          </div>
        )}

        <p className="text-xs tracking-widest text-stone-400 uppercase mb-1">
          {product.retailer}
          {product.category ? ` · ${product.category}` : ""}
        </p>
        <h3 className="text-base tracking-wide text-stone-800 mb-2">{product.name}</h3>
        <p className="text-sm text-stone-500 mb-6">
          {formatPrice(product.price_cents, product.currency)}
        </p>

        <a
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          className="block w-full text-center text-xs tracking-widest uppercase py-3 border border-stone-800 text-stone-800 hover:bg-stone-800 hover:text-[#f5f2ee] transition-colors duration-200"
        >
          Shop
        </a>
      </div>
    </div>
  )
}
