import { getScheduleData, reconcileSchedule, type AdminPost } from "@/lib/admin"
import PostCard from "@/components/admin/PostCard"

export const dynamic = "force-dynamic"

type Section = "needsApproval" | "scheduled" | "queue"

function Section({
  title,
  hint,
  posts,
  section,
}: {
  title: string
  hint?: string
  posts: AdminPost[]
  section: Section
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
  await reconcileSchedule()
  const { needsApproval, scheduled, queue } = await getScheduleData()

  return (
    <div>
      <header className="mb-8">
        <h1 className="font-serif text-3xl text-foreground sm:text-4xl">Schedule</h1>
        <p className="mt-1 text-sm text-muted">
          {scheduled.length} scheduled · {queue.length} queued · {needsApproval.length} awaiting approval
        </p>
      </header>

      <Section
        title="Needs Approval"
        hint="approve to enter the queue"
        posts={needsApproval}
        section="needsApproval"
      />
      <Section
        title="Scheduled"
        posts={scheduled}
        section="scheduled"
      />
      <Section
        title="Queue"
        hint="FIFO — fills the next 3 days automatically"
        posts={queue}
        section="queue"
      />
    </div>
  )
}
