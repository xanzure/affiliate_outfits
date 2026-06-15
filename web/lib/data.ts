import { Concept, Outfit } from "@/lib/types"
import { concepts as mockConcepts } from "@/lib/mock/concepts"
import { outfits as mockOutfits } from "@/lib/mock/outfits"

// Data access layer — replace function bodies with API calls when backend is ready.
// The UI never imports mock data directly; it always goes through here.

export async function getConcepts(): Promise<Concept[]> {
  return mockConcepts.filter((c) => c.status === "active")
}

export async function getConcept(id: string): Promise<Concept | null> {
  return mockConcepts.find((c) => c.id === id) ?? null
}

export async function getOutfitsForConcept(conceptId: string): Promise<Outfit[]> {
  return mockOutfits
    .filter((o) => o.concept_id === conceptId)
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
}
