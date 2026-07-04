import { getScheduleData, type AdminPost } from "@/lib/admin"
import PostCard from "@/components/admin/PostCard"
import QueueList from "@/components/admin/QueueList"

export const dynamic = "force-dynamic"

type GridSection = "needsApproval" | "failed"

function GridSection({
  title,
  hint,
  posts,
  section,
}: {
  title: string
  hint?: string
  posts: AdminPost[]
  section: GridSection
}) {
  return (
    <section className="mb-12">
      <div className="mb-4 flex items-baseline gap-3">
        <h2 className="text-[0.7rem] font-medium tracking-[0.28em] uppercase text-foreground/70">
          {title}
        </h2>
        <span className="text-[0.7rem] tracking-wider text-muted/60">{posts.length}</span>
        {hint && <span className="text-[0.7rem] text-muted/50">{hint}</span>}
      </div>
      {posts.length === 0 ? (
        <p className="text-sm text-muted/60">Nothing here.</p>
      ) : (
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {posts.map((p) => (
            <PostCard key={p.id} post={p} section={section} />
          ))}
        </div>
      )}
    </section>
  )
}

export default async function SchedulePage() {
  const { needsApproval, queues, cooldowns, failed } = await getScheduleData()
  const queuedCount = queues.tiktok.length + queues.pinterest.length

  return (
    <div>
      <header className="mb-8">
        <h1 className="font-serif text-3xl text-foreground sm:text-4xl">Schedule</h1>
        <p className="mt-1 text-sm text-muted">
          {needsApproval.length} awaiting approval · {queuedCount} queued
          {failed.length > 0 && ` · ${failed.length} failed`}
        </p>
      </header>

      {failed.length > 0 && (
        <GridSection
          title="Failed"
          hint="publish attempt errored — fix the cause, then retry"
          posts={failed}
          section="failed"
        />
      )}

      <GridSection
        title="Needs Approval"
        hint="approve to enter the queue"
        posts={needsApproval}
        section="needsApproval"
      />

      <section className="mb-12">
        <div className="mb-4 flex items-baseline gap-3">
          <h2 className="text-[0.7rem] font-medium tracking-[0.28em] uppercase text-foreground/70">
            Queue
          </h2>
          <span className="text-[0.7rem] tracking-wider text-muted/60">{queuedCount}</span>
          <span className="text-[0.7rem] text-muted/50">
            FIFO — one auto-post per platform every 24h; drag with ↑↓, or Post now
          </span>
        </div>
        <div className="grid grid-cols-1 gap-8 md:grid-cols-2">
          <QueueList platform="tiktok" posts={queues.tiktok} cooldown={cooldowns.tiktok} />
          <QueueList platform="pinterest" posts={queues.pinterest} cooldown={cooldowns.pinterest} />
        </div>
      </section>
    </div>
  )
}
