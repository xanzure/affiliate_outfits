import { getOutfits } from "@/lib/admin"
import OutfitCard from "@/components/admin/OutfitCard"

export const dynamic = "force-dynamic"

export default async function OutfitsPage() {
  const outfits = await getOutfits()

  return (
    <div>
      <header className="mb-8">
        <h1 className="font-serif text-3xl text-foreground sm:text-4xl">Outfits</h1>
        <p className="mt-1 text-sm text-muted">{outfits.length} total</p>
      </header>

      {outfits.length === 0 ? (
        <p className="text-sm text-muted/60">No outfits yet.</p>
      ) : (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
          {outfits.map((o) => (
            <OutfitCard key={o.id} outfit={o} />
          ))}
        </div>
      )}
    </div>
  )
}
