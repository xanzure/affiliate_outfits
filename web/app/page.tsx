import { getConcepts, getOutfitsForConcept } from "@/lib/data"
import ConceptCard from "@/components/ConceptCard"

export default async function HomePage() {
  const concepts = await getConcepts()
  const outfitCounts = await Promise.all(
    concepts.map((c) => getOutfitsForConcept(c.id).then((o) => o.length))
  )

  return (
    <main className="min-h-screen bg-[#f5f2ee] px-6 py-16 sm:px-12 lg:px-20">
      <header className="mb-16">
        <h1 className="text-xs tracking-[0.3em] text-stone-400 uppercase mb-2">
          Vance Archives
        </h1>
        <p className="text-xs tracking-widest text-stone-300 uppercase">
          {concepts.length} active concepts
        </p>
      </header>

      <div className="grid grid-cols-2 gap-x-6 gap-y-14 sm:grid-cols-3 lg:grid-cols-4">
        {concepts.map((concept, i) => (
          <ConceptCard
            key={concept.id}
            concept={concept}
            outfitCount={outfitCounts[i]}
          />
        ))}
      </div>
    </main>
  )
}
