"use client"

import { useMemo, useState } from "react"
import { useRouter } from "next/navigation"
import { ZONES, resolveZone, type Zone } from "@/lib/categories"
import type { WardrobeItem } from "@/lib/wardrobe"
import {
  archiveProduct,
  intakeProduct,
  reclassifyProduct,
  reprocessProduct,
  uploadIntakeImage,
} from "../../app/admin/(dashboard)/wardrobe/actions"
import { useTasks } from "./TasksProvider"

export default function WardrobeGrid({ items }: { items: WardrobeItem[] }) {
  const router = useRouter()
  const { trackJob } = useTasks()
  const [query, setQuery] = useState("")
  const [zone, setZone] = useState<Zone | "all">("all")
  const [showAdd, setShowAdd] = useState(false)
  const [editing, setEditing] = useState<WardrobeItem | null>(null)
  const [busyId, setBusyId] = useState<string | null>(null)

  const counts = useMemo(() => {
    const c: Record<string, number> = {}
    for (const it of items) c[it.zone] = (c[it.zone] ?? 0) + 1
    return c
  }, [items])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    return items.filter(
      (it) =>
        (zone === "all" || it.zone === zone) &&
        (!q || it.name.toLowerCase().includes(q) || it.retailer.toLowerCase().includes(q))
    )
  }, [items, query, zone])

  async function onArchive(it: WardrobeItem) {
    if (!confirm(`Remove "${it.name}" from the cache? Existing outfits keep working.`)) return
    setBusyId(it.id)
    await archiveProduct(it.id)
    setBusyId(null)
    router.refresh()
  }

  // Image replace runs a cutout job — enqueue it and let the Tasks panel track
  // it; no need to hold the card busy until the worker finishes.
  async function onReplaceImage(it: WardrobeItem, file: File) {
    setBusyId(it.id)
    try {
      const fd = new FormData()
      fd.set("file", file)
      const imageUrl = await uploadIntakeImage(fd)
      const jobId = await reprocessProduct({ productId: it.id, imageUrl })
      trackJob(jobId, "Re-cutout", it.name)
    } catch (e) {
      alert(String(e))
    } finally {
      setBusyId(null)
    }
  }

  // Intake is async: upload (if any), enqueue the scrape/cutout job, hand it to
  // the Tasks panel, and return immediately so the modal can close.
  async function onIntake(url: string, category: string, file: File | null) {
    let imageUrl: string | undefined
    if (file) {
      const fd = new FormData()
      fd.set("file", file)
      imageUrl = await uploadIntakeImage(fd)
    }
    const jobId = await intakeProduct({
      url,
      category: category || undefined,
      imageUrl,
    })
    trackJob(jobId, "Intake", url.replace(/^https?:\/\/(www\.)?/, ""))
  }

  return (
    <div>
      {/* toolbar */}
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search name or retailer…"
          className="min-w-[200px] flex-1 rounded-sm border border-line bg-surface px-3 py-2 text-sm text-foreground outline-none focus:border-accent"
        />
        <button
          onClick={() => setShowAdd(true)}
          className="rounded-sm border border-foreground px-4 py-2 text-[0.7rem] tracking-[0.2em] uppercase text-foreground transition-colors hover:border-accent hover:bg-accent hover:text-surface"
        >
          + Add item
        </button>
      </div>

      {/* zone filter */}
      <div className="mb-6 flex flex-wrap gap-1.5">
        <Chip active={zone === "all"} onClick={() => setZone("all")}>
          All {items.length}
        </Chip>
        {ZONES.map((z) => (
          <Chip key={z} active={zone === z} onClick={() => setZone(z)}>
            {z} {counts[z] ?? 0}
          </Chip>
        ))}
      </div>

      {filtered.length === 0 ? (
        <p className="text-sm text-muted/60">No matching pieces.</p>
      ) : (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
          {filtered.map((it) => (
            <Card
              key={it.id}
              item={it}
              busy={busyId === it.id}
              onEdit={() => setEditing(it)}
              onArchive={() => onArchive(it)}
              onReplaceImage={(f) => onReplaceImage(it, f)}
            />
          ))}
        </div>
      )}

      {showAdd && <AddModal onClose={() => setShowAdd(false)} onIntake={onIntake} />}
      {editing && (
        <EditModal
          item={editing}
          onClose={() => setEditing(null)}
          onDone={() => {
            setEditing(null)
            router.refresh()
          }}
        />
      )}
    </div>
  )
}

function Chip({
  active,
  onClick,
  children,
}: {
  active: boolean
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      onClick={onClick}
      className={`rounded-sm px-3 py-1.5 text-[0.65rem] tracking-[0.15em] uppercase transition-colors ${
        active ? "bg-accent/10 text-accent" : "text-muted hover:text-foreground"
      }`}
    >
      {children}
    </button>
  )
}

function Card({
  item,
  busy,
  onEdit,
  onArchive,
  onReplaceImage,
}: {
  item: WardrobeItem
  busy: boolean
  onEdit: () => void
  onArchive: () => void
  onReplaceImage: (file: File) => void
}) {
  return (
    <div className="group relative flex flex-col overflow-hidden rounded-sm border border-line bg-surface">
      <div className="relative aspect-square bg-[#EFE9DF]">
        {item.imageUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={item.imageUrl} alt={item.name} className="h-full w-full object-contain p-2" />
        ) : (
          <div className="flex h-full items-center justify-center text-xs text-muted/50">no image</div>
        )}
        <span className="absolute left-1.5 top-1.5 rounded-sm bg-background/85 px-1.5 py-0.5 text-[0.55rem] tracking-[0.12em] uppercase text-accent">
          {item.zone}
        </span>
        {item.inUse && (
          <span className="absolute right-1.5 top-1.5 rounded-sm bg-background/85 px-1.5 py-0.5 text-[0.55rem] tracking-[0.12em] uppercase text-muted">
            in use
          </span>
        )}
        {busy && (
          <div className="absolute inset-0 flex items-center justify-center bg-background/70 text-xs text-muted">
            working…
          </div>
        )}
      </div>
      <div className="flex flex-1 flex-col gap-1 p-2.5">
        <p className="line-clamp-2 text-xs text-foreground">{item.name}</p>
        <p className="text-[0.65rem] text-muted">
          {item.retailer}
          {item.priceCents != null && ` · $${(item.priceCents / 100).toFixed(0)}`}
        </p>
        <div className="mt-1 flex flex-wrap gap-1">
          {item.color && <Badge>{item.color}</Badge>}
          <Badge muted>{item.source}</Badge>
        </div>
        <div className="mt-2 flex gap-1.5">
          <button
            onClick={onEdit}
            className="flex-1 rounded-sm border border-line px-2 py-1 text-[0.6rem] tracking-[0.12em] uppercase text-muted transition-colors hover:text-foreground"
          >
            Edit
          </button>
          <label className="flex-1 cursor-pointer rounded-sm border border-line px-2 py-1 text-center text-[0.6rem] tracking-[0.12em] uppercase text-muted transition-colors hover:text-foreground">
            Replace
            <input
              type="file"
              accept="image/*"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0]
                if (f) onReplaceImage(f)
              }}
            />
          </label>
          <button
            onClick={onArchive}
            className="flex-1 rounded-sm border border-line px-2 py-1 text-[0.6rem] tracking-[0.12em] uppercase text-muted transition-colors hover:border-red-400 hover:text-red-500"
          >
            Remove
          </button>
        </div>
      </div>
    </div>
  )
}

function Badge({ children, muted }: { children: React.ReactNode; muted?: boolean }) {
  return (
    <span
      className={`rounded-sm px-1.5 py-0.5 text-[0.55rem] tracking-[0.1em] uppercase ${
        muted ? "bg-line/40 text-muted" : "bg-accent/10 text-accent"
      }`}
    >
      {children}
    </span>
  )
}

function EditModal({
  item,
  onClose,
  onDone,
}: {
  item: WardrobeItem
  onClose: () => void
  onDone: () => void
}) {
  const [category, setCategory] = useState(item.category ?? "")
  const [color, setColor] = useState(item.color ?? "")
  const [busy, setBusy] = useState(false)
  const zone = resolveZone(category)

  async function save() {
    setBusy(true)
    await reclassifyProduct({ productId: item.id, category, color })
    onDone()
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-stone-900/40 p-4" onClick={onClose}>
      <div
        className="w-full max-w-md rounded-sm border border-line bg-background p-5"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="mb-1 font-serif text-xl text-foreground">Reclassify</h2>
        <p className="mb-4 line-clamp-1 text-xs text-muted">{item.name}</p>
        <div className="space-y-3">
          <div>
            <label className="mb-1 block text-[0.65rem] tracking-[0.15em] uppercase text-muted">
              Category
            </label>
            <input
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              placeholder="e.g. wide-leg trousers"
              className="w-full rounded-sm border border-line bg-surface px-3 py-2 text-sm text-foreground outline-none focus:border-accent"
            />
            <p className="mt-1 text-[0.65rem] text-muted">
              type tag → <span className="text-accent uppercase tracking-[0.12em]">{zone}</span>
            </p>
          </div>
          <div>
            <label className="mb-1 block text-[0.65rem] tracking-[0.15em] uppercase text-muted">
              Color
            </label>
            <input
              value={color}
              onChange={(e) => setColor(e.target.value)}
              placeholder="e.g. chocolate brown"
              className="w-full rounded-sm border border-line bg-surface px-3 py-2 text-sm text-foreground outline-none focus:border-accent"
            />
          </div>
        </div>
        <div className="mt-5 flex justify-end gap-2">
          <button onClick={onClose} className="px-3 py-2 text-[0.7rem] tracking-[0.2em] uppercase text-muted">
            Cancel
          </button>
          <button
            onClick={save}
            disabled={busy}
            className="rounded-sm border border-foreground px-4 py-2 text-[0.7rem] tracking-[0.2em] uppercase text-foreground transition-colors hover:border-accent hover:bg-accent hover:text-surface disabled:opacity-50"
          >
            {busy ? "Saving…" : "Save"}
          </button>
        </div>
      </div>
    </div>
  )
}

function AddModal({
  onClose,
  onIntake,
}: {
  onClose: () => void
  onIntake: (url: string, category: string, file: File | null) => Promise<void>
}) {
  const [url, setUrl] = useState("")
  const [category, setCategory] = useState("")
  const [file, setFile] = useState<File | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  // Just kicks off the job and closes — the Tasks panel tracks it from here, so
  // there's no need to keep the modal open while the worker scrapes.
  async function submit() {
    if (!url.trim().startsWith("http")) {
      setError("Enter a valid product URL.")
      return
    }
    setBusy(true)
    setError(null)
    try {
      await onIntake(url.trim(), category.trim(), file)
      onClose()
    } catch (e) {
      setError(String(e))
      setBusy(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-stone-900/40 p-4" onClick={onClose}>
      <div
        className="w-full max-w-md rounded-sm border border-line bg-background p-5"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="mb-1 font-serif text-xl text-foreground">Add a piece</h2>
        <p className="mb-4 text-xs text-muted">
          Paste a direct product URL. We scrape its image only — never search. Runs in the
          background; track it in the Tasks panel. If scraping fails, attach an image to add it
          manually.
        </p>
        <div className="space-y-3">
          <input
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://retailer.com/product/…"
            className="w-full rounded-sm border border-line bg-surface px-3 py-2 text-sm text-foreground outline-none focus:border-accent"
          />
          <input
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            placeholder="Type (optional, e.g. wide-leg trousers)"
            className="w-full rounded-sm border border-line bg-surface px-3 py-2 text-sm text-foreground outline-none focus:border-accent"
          />
          <label className="flex cursor-pointer items-center gap-2 text-xs text-muted">
            <span className="rounded-sm border border-line px-2 py-1 uppercase tracking-[0.12em] hover:text-foreground">
              {file ? file.name.slice(0, 28) : "Attach image (optional)"}
            </span>
            <input
              type="file"
              accept="image/*"
              className="hidden"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          </label>
          {error && <p className="text-xs text-red-500">{error}</p>}
        </div>
        <div className="mt-5 flex justify-end gap-2">
          <button onClick={onClose} className="px-3 py-2 text-[0.7rem] tracking-[0.2em] uppercase text-muted">
            Cancel
          </button>
          <button
            onClick={submit}
            disabled={busy}
            className="rounded-sm border border-foreground px-4 py-2 text-[0.7rem] tracking-[0.2em] uppercase text-foreground transition-colors hover:border-accent hover:bg-accent hover:text-surface disabled:opacity-50"
          >
            {busy ? "Starting…" : "Add"}
          </button>
        </div>
      </div>
    </div>
  )
}
