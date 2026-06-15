"use client"

import Link from "next/link"
import { Concept } from "@/lib/types"

interface Props {
  concept: Concept
  outfitCount: number
}

const PLACEHOLDER_COLORS = [
  "bg-stone-200",
  "bg-neutral-200",
  "bg-zinc-200",
  "bg-slate-200",
  "bg-stone-300",
]

export default function ConceptCard({ concept, outfitCount }: Props) {
  const displayName = concept.metadata.display_name as string | undefined
  const label = displayName ?? concept.seed
  const colorClass = PLACEHOLDER_COLORS[parseInt(concept.id.replace(/\D/g, ""), 10) % PLACEHOLDER_COLORS.length]

  return (
    <Link href={`/concept/${concept.id}`} className="group block">
      <div className="overflow-hidden">
        <div className={`relative aspect-[3/4] w-full ${colorClass} transition-transform duration-500 group-hover:scale-[1.02]`}>
          {concept.metadata.cover_image_url ? (
            <img
              src={concept.metadata.cover_image_url as string}
              alt={label}
              className="h-full w-full object-cover"
            />
          ) : (
            <div className="flex h-full w-full items-end p-4">
              <span className="font-mono text-xs tracking-widest text-stone-400 uppercase">
                No image
              </span>
            </div>
          )}
        </div>
        <div className="pt-3">
          <p className="text-xs tracking-widest text-stone-400 uppercase mb-1">
            {outfitCount} {outfitCount === 1 ? "outfit" : "outfits"}
          </p>
          <h2 className="text-sm tracking-wide text-stone-800 group-hover:text-stone-500 transition-colors duration-200">
            {label}
          </h2>
        </div>
      </div>
    </Link>
  )
}
