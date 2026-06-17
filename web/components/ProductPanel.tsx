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
      <div className="absolute inset-0 bg-stone-900/30 backdrop-blur-[3px]" />
      <div
        className="relative z-10 w-full max-w-sm rounded-sm bg-surface p-8 shadow-2xl ring-1 ring-line/60 sm:mx-4"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-[0.7rem] tracking-[0.28em] uppercase text-muted transition-colors hover:text-accent"
        >
          Close
        </button>

        {product.image_url && (
          <div className="mb-6 aspect-square w-28 overflow-hidden rounded-sm bg-canvas ring-1 ring-line/50">
            <img
              src={product.image_url}
              alt={product.name}
              className="h-full w-full object-contain p-2"
            />
          </div>
        )}

        <p className="mb-2 text-[0.7rem] tracking-[0.28em] uppercase text-accent">
          {product.retailer}
          {product.category ? ` · ${product.category}` : ""}
        </p>
        <h3 className="mb-2 font-serif text-2xl leading-snug text-foreground">
          {product.name}
        </h3>
        <p className="mb-6 text-sm text-muted">
          {formatPrice(product.price_cents, product.currency)}
        </p>

        <a
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          className="block w-full border border-foreground py-3 text-center text-[0.7rem] tracking-[0.28em] uppercase text-foreground transition-colors duration-200 hover:border-accent hover:bg-accent hover:text-surface"
        >
          Shop the piece
        </a>
      </div>
    </div>
  )
}
