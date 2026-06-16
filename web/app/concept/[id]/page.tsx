export const revalidate = 60

import { notFound } from "next/navigation"
import Link from "next/link"
import { getConcept, getOutfitsForConcept } from "@/lib/data"
import OutfitCanvas from "@/components/OutfitCanvas"

interface Props {
  params: Promise<{ id: string }>
}

export default async function ConceptPage({ params }: Props) {
  const { id } = await params
  const [concept, outfits] = await Promise.all([
    getConcept(id),
    getOutfitsForConcept(id),
  ])

  if (!concept) notFound()

  const displayName = concept.metadata.display_name as string | undefined
  const label = displayName ?? concept.seed

  return (
    <main className="min-h-screen bg-[#f5f2ee] px-6 py-16 sm:px-12 lg:px-20">
      <nav className="mb-12">
        <Link
          href="/"
          className="text-xs tracking-widest text-stone-400 uppercase hover:text-stone-600 transition-colors"
        >
          ← Vance Archives
        </Link>
      </nav>

      <header className="mb-16">
        <p className="text-xs tracking-widest text-stone-400 uppercase mb-2">Concept</p>
        <h1 className="text-lg tracking-wide text-stone-800">{label}</h1>
        {displayName && (
          <p className="text-xs text-stone-400 mt-1">{concept.seed}</p>
        )}
        <p className="text-xs tracking-widest text-stone-300 uppercase mt-4">
          {outfits.length} {outfits.length === 1 ? "outfit" : "outfits"}
        </p>
      </header>

      {outfits.length === 0 ? (
        <p className="text-xs tracking-widest text-stone-300 uppercase">No outfits yet</p>
      ) : (
        <div className="grid grid-cols-1 gap-16 sm:grid-cols-2 lg:grid-cols-3">
          {outfits.map((outfit, i) => (
            <OutfitCanvas key={outfit.id} outfit={outfit} index={i} />
          ))}
        </div>
      )}
    </main>
  )
}
