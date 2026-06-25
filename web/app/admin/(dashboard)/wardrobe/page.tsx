import { getWardrobe } from "@/lib/wardrobe"
import WardrobeGrid from "@/components/admin/WardrobeGrid"

export const dynamic = "force-dynamic"

export default async function WardrobePage() {
  const items = await getWardrobe()
  return (
    <div>
      <header className="mb-6">
        <h1 className="font-serif text-3xl text-foreground sm:text-4xl">Wardrobe</h1>
        <p className="mt-1 text-sm text-muted">{items.length} cached pieces</p>
      </header>
      <WardrobeGrid items={items} />
    </div>
  )
}
