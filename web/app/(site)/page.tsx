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
      <section className="mx-auto max-w-[1400px] px-5 pt-12 pb-12 sm:px-12 sm:pt-20 sm:pb-14 lg:px-20">
        <div className="max-w-3xl animate-fade-up">
          <p className="mb-4 text-[0.65rem] tracking-[0.35em] uppercase text-accent sm:mb-5 sm:text-[0.7rem]">
            The Archive
          </p>
          <h1 className="font-serif text-[2.75rem] leading-[0.95] tracking-tight text-foreground sm:text-6xl lg:text-7xl">
            Outfits, curated by
            <br />
            <span className="italic text-accent">obsession.</span>
          </h1>
          <p className="mt-5 max-w-xl text-sm leading-relaxed text-muted sm:mt-6">
            A living archive of styled looks — built around artists, eras, and the
            aesthetics worth dressing for. Every piece shoppable.
          </p>
          <div className="mt-7 flex items-center gap-3 text-[0.65rem] tracking-[0.28em] uppercase text-muted/70 sm:mt-8 sm:text-[0.7rem]">
            <span className="h-px w-10 bg-line" />
            {concepts.length} active concepts
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-[1400px] px-5 pb-20 sm:px-12 sm:pb-28 lg:px-20">
        <div className="grid grid-cols-2 gap-x-4 gap-y-10 sm:grid-cols-3 sm:gap-x-5 sm:gap-y-12 lg:grid-cols-4">
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
