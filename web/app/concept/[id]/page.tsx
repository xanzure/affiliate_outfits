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
    <main className="paper-vignette">
      <div className="mx-auto max-w-[1400px] px-6 pt-12 pb-28 sm:px-12 lg:px-20">
        <nav className="mb-12">
          <Link
            href="/"
            className="group inline-flex items-center gap-2 text-[0.7rem] tracking-[0.28em] uppercase text-muted transition-colors hover:text-accent"
          >
            <span className="transition-transform duration-300 group-hover:-translate-x-1">←</span>
            The Archive
          </Link>
        </nav>

        <header className="mb-16 animate-fade-up border-b border-line/70 pb-12">
          <p className="mb-4 text-[0.7rem] tracking-[0.38em] uppercase text-accent">
            Concept
          </p>
          <h1 className="font-serif text-5xl leading-[0.95] tracking-tight text-foreground sm:text-6xl">
            {label}
          </h1>
          {displayName && (
            <p className="mt-3 text-sm italic text-muted">{concept.seed}</p>
          )}
          <p className="mt-6 flex items-center gap-3 text-[0.7rem] tracking-[0.28em] uppercase text-muted/70">
            <span className="h-px w-10 bg-line" />
            {outfits.length} {outfits.length === 1 ? "outfit" : "outfits"}
          </p>
        </header>

        {outfits.length === 0 ? (
          <p className="text-[0.7rem] tracking-[0.28em] uppercase text-muted/70">
            No outfits yet
          </p>
        ) : (
          <div className="grid grid-cols-1 gap-x-10 gap-y-16 sm:grid-cols-2 lg:grid-cols-3">
            {outfits.map((outfit, i) => (
              <OutfitCanvas key={outfit.id} outfit={outfit} index={i} />
            ))}
          </div>
        )}
      </div>
    </main>
  )
}
