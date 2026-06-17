"use client"

import Link from "next/link"
import { Concept } from "@/lib/types"

interface Props {
  concept: Concept
  outfitCount: number
  index: number
}

const PLACEHOLDER_COLORS = [
  "bg-stone-200",
  "bg-neutral-200",
  "bg-zinc-200",
  "bg-stone-300",
]

export default function ConceptCard({ concept, outfitCount, index }: Props) {
  const displayName = concept.metadata.display_name as string | undefined
  const label = displayName ?? concept.seed
  const colorClass = PLACEHOLDER_COLORS[index % PLACEHOLDER_COLORS.length]

  return (
    <Link href={`/concept/${concept.id}`} className="group block">
      <div className="relative aspect-[3/4] w-full overflow-hidden rounded-sm bg-canvas ring-1 ring-line/60 transition-all duration-500 group-hover:ring-accent/40 group-hover:shadow-[0_18px_42px_-18px_rgba(60,45,30,0.45)]">
        {concept.metadata.cover_image_url ? (
          <img
            src={concept.metadata.cover_image_url as string}
            alt={label}
            className="h-full w-full object-cover transition-transform duration-700 ease-out group-hover:scale-[1.06]"
          />
        ) : (
          <div className={`flex h-full w-full items-center justify-center ${colorClass}`}>
            <span className="font-serif text-4xl text-stone-400">
              {label.charAt(0)}
            </span>
          </div>
        )}

        {/* hover gradient + reveal */}
        <div className="pointer-events-none absolute inset-0 bg-gradient-to-t from-black/45 via-black/0 to-black/0 opacity-0 transition-opacity duration-500 group-hover:opacity-100" />
        <span className="absolute left-3 top-3 font-mono text-[0.65rem] tracking-widest text-foreground/30 transition-colors duration-500 group-hover:text-white/80">
          {String(index + 1).padStart(2, "0")}
        </span>
        <div className="pointer-events-none absolute inset-x-0 bottom-0 translate-y-2 p-4 opacity-0 transition-all duration-500 group-hover:translate-y-0 group-hover:opacity-100">
          <p className="text-[0.6rem] tracking-[0.28em] uppercase text-white/75">
            {outfitCount} {outfitCount === 1 ? "look" : "looks"} →
          </p>
        </div>
      </div>

      <div className="pt-3">
        <h2 className="font-serif text-xl leading-snug text-foreground transition-colors duration-300 group-hover:text-accent">
          {label}
        </h2>
        <p className="mt-0.5 text-[0.65rem] tracking-[0.28em] uppercase text-muted/70">
          {outfitCount} {outfitCount === 1 ? "outfit" : "outfits"}
        </p>
      </div>
    </Link>
  )
}
