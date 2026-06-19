import { getActivity } from "@/lib/admin"

export const dynamic = "force-dynamic"

export default async function ActivityPage() {
  const entries = await getActivity()

  return (
    <div>
      <header className="mb-8">
        <h1 className="font-serif text-3xl text-foreground sm:text-4xl">Activity</h1>
        <p className="mt-1 text-sm text-muted">Recent admin actions.</p>
      </header>

      {entries.length === 0 ? (
        <p className="text-sm text-muted/60">No activity yet.</p>
      ) : (
        <ul className="overflow-hidden rounded-sm border border-line/70">
          {entries.map((e) => (
            <li
              key={e.id}
              className="flex items-center justify-between gap-3 border-b border-line/50 bg-surface px-4 py-2.5 text-sm last:border-0"
            >
              <span className="font-mono text-[0.75rem] text-foreground">{e.action}</span>
              <span className="truncate text-[0.7rem] text-muted/60">{e.target_id ?? ""}</span>
              <span className="shrink-0 text-[0.7rem] text-muted/60">
                {new Date(e.created_at).toLocaleString()}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
