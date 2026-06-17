import { getConcepts, getOutfitCountsByConcept } from "@/lib/data"
import ConceptCard from "@/components/ConceptCard"

export const revalidate = 60

export default async function HomePage() {
  const [concepts, outfitCountMap] = await Promise.all([
    getConcepts(),
    getOutfitCountsByConcept(),
  ])
  const outfitCounts = concepts.map((c) => outfitCountMap[c.id] ?? 0)

  return (
    <main className="paper-vignette">
      <section className="mx-auto max-w-[1400px] px-6 pt-20 pb-14 sm:px-12 lg:px-20">
        <div className="max-w-3xl animate-fade-up">
          <p className="mb-5 text-[0.7rem] tracking-[0.38em] uppercase text-accent">
            The Archive
          </p>
          <h1 className="font-serif text-5xl leading-[0.95] tracking-tight text-foreground sm:text-6xl lg:text-7xl">
            Outfits, curated by
            <br />
            <span className="italic text-accent">obsession.</span>
          </h1>
          <p className="mt-6 max-w-xl text-sm leading-relaxed text-muted">
            A living archive of styled looks — built around artists, eras, and the
            aesthetics worth dressing for. Every piece shoppable.
          </p>
          <div className="mt-8 flex items-center gap-3 text-[0.7rem] tracking-[0.28em] uppercase text-muted/70">
            <span className="h-px w-10 bg-line" />
            {concepts.length} active concepts
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-[1400px] px-6 pb-28 sm:px-12 lg:px-20">
        <div className="grid grid-cols-2 gap-x-5 gap-y-12 sm:grid-cols-3 lg:grid-cols-4">
          {concepts.map((concept, i) => (
            <ConceptCard
              key={concept.id}
              concept={concept}
              outfitCount={outfitCounts[i]}
              index={i}
            />
          ))}
        </div>
      </section>
    </main>
  )
}
