import { getMetricsData } from "@/lib/admin"
import AddMetricsForm from "@/components/admin/AddMetricsForm"

export const dynamic = "force-dynamic"

const RETIRE = 25

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-sm border border-line/70 bg-surface p-4">
      <p className="text-[0.6rem] uppercase tracking-[0.2em] text-muted/70">{label}</p>
      <p className="mt-1 font-serif text-2xl text-foreground">{value}</p>
    </div>
  )
}

export default async function MetricsPage() {
  const { totals, concepts, posts, postOptions } = await getMetricsData()

  return (
    <div>
      <header className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-serif text-3xl text-foreground sm:text-4xl">Metrics</h1>
          <p className="mt-1 text-sm text-muted">Performance across posts and concepts.</p>
        </div>
        <AddMetricsForm postOptions={postOptions} />
      </header>

      <div className="mb-10 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="Views" value={totals.views.toLocaleString()} />
        <Stat label="Clicks" value={totals.clicks.toLocaleString()} />
        <Stat label="Saves" value={totals.saves.toLocaleString()} />
        <Stat label="Avg score" value={totals.avgScore} />
      </div>

      <section className="mb-10">
        <h2 className="mb-3 text-[0.7rem] font-medium tracking-[0.28em] uppercase text-foreground/70">
          Concept performance
        </h2>
        <div className="overflow-hidden rounded-sm border border-line/70">
          {concepts.map((c) => {
            const danger = c.ranking_score - RETIRE
            const tone =
              danger <= 5 ? "text-red-600" : danger <= 15 ? "text-amber-600" : "text-foreground"
            return (
              <div
                key={c.id}
                className="flex items-center justify-between gap-3 border-b border-line/50 bg-surface px-4 py-3 last:border-0"
              >
                <div className="min-w-0">
                  <span className="block truncate text-sm text-foreground">{c.name}</span>
                  <span className="text-[0.65rem] uppercase tracking-wider text-muted/70">
                    {c.status} · used {c.usage_count}×
                  </span>
                </div>
                <div className="text-right">
                  <span className={`font-mono text-sm ${tone}`}>{c.ranking_score.toFixed(0)}</span>
                  <div className="mt-1 h-1 w-24 overflow-hidden rounded bg-line/60">
                    <div
                      className={`h-full ${danger <= 5 ? "bg-red-500" : danger <= 15 ? "bg-amber-500" : "bg-accent"}`}
                      style={{ width: `${Math.max(0, Math.min(100, c.ranking_score))}%` }}
                    />
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </section>

      <section>
        <h2 className="mb-3 text-[0.7rem] font-medium tracking-[0.28em] uppercase text-foreground/70">
          Posts
        </h2>
        {posts.length === 0 ? (
          <p className="text-sm text-muted/60">No metrics recorded yet. Use “Add metrics”.</p>
        ) : (
          <div className="overflow-x-auto rounded-sm border border-line/70">
            <table className="w-full text-sm">
              <thead className="bg-surface text-left text-[0.6rem] uppercase tracking-wider text-muted/70">
                <tr>
                  <th className="px-3 py-2">Platform</th>
                  <th className="px-3 py-2">Concept</th>
                  <th className="px-3 py-2 text-right">Views</th>
                  <th className="px-3 py-2 text-right">Clicks</th>
                  <th className="px-3 py-2 text-right">Saves</th>
                  <th className="px-3 py-2 text-right">Score</th>
                </tr>
              </thead>
              <tbody>
                {posts.map((p) => (
                  <tr key={p.post_id} className="border-t border-line/50">
                    <td className="px-3 py-2 capitalize">{p.platform}</td>
                    <td className="px-3 py-2 text-muted">{p.conceptName ?? "—"}</td>
                    <td className="px-3 py-2 text-right">{p.views.toLocaleString()}</td>
                    <td className="px-3 py-2 text-right">{p.clicks.toLocaleString()}</td>
                    <td className="px-3 py-2 text-right">{p.saves.toLocaleString()}</td>
                    <td className="px-3 py-2 text-right">{p.score}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  )
}
