# Admin Dashboard — Build Plan

> **Historical document.** This is the plan the dashboard was built from in June
> 2026, kept to show how the plan compared to what shipped. The scheduling
> design below (fixed EST slots, `reconcileSchedule`, `scheduled_for`) was later
> replaced by an approval queue with a per-platform cooldown — see
> [autoposting.md](../autoposting.md) and Phase 6 of the
> [build log](../progress.md#phase-6--publishing-for-real-jul-3).

Status: **BUILT** (all build-order steps 1–8 implemented and verified; TikTok
publish stays stubbed behind `AUTOPOSTING_ENABLED` pending the audit — step 9).

Implementation notes / deviations from the original plan:
- Approval state is stored with an `approved` boolean on `posts` (plus the existing
  `status`) rather than new `needs_approval`/`queued` status values — this avoided a
  risky CHECK-constraint migration. Sections derive the same UX: `needs_approval` =
  `draft` + not approved; `queued` = `draft` + approved + no `scheduled_for`.
- The FIFO reconcile runs in TypeScript (`web/lib/admin.ts → reconcileSchedule`) on
  schedule-tab load, not in a Python `schedule_service.py`. The Python worker
  (`scripts/worker.py`) handles only the heavy pipeline jobs.
- A gated **local-dev auth bypass** (`ADMIN_DEV_BYPASS=true`, non-production only,
  in gitignored `.env.local`) exists so `/admin` can be previewed without email
  login. Production uses real Supabase magic-link auth + the `ADMIN_EMAILS` allowlist.

Key files: schema (`scripts/migrate_dashboard.py`, `app/db/schema*.sql`),
`app/db/posts.py` + `app/db/jobs.py`, `scripts/worker.py`,
`app/services/link_health.py`, `web/lib/admin.ts`, `web/lib/auth.ts`,
`web/middleware.ts`, `web/app/admin/**`, `web/components/admin/**`.

---



An internal, authenticated control panel for approving and scheduling posts,
reviewing outfits, and tracking metrics. It lives inside the existing Next.js app
under `/admin`, separate from the public read-only site. Desktop is the primary
experience; mobile has full feature parity for use away from home.

This dashboard also serves as the **"Post to TikTok" UI that TikTok's app audit
requires**. The path is: build the dashboard → apply for the TikTok dev account and
pass the audit → flip TikTok from stub to live **Direct Post** (fully automated, no
manual upload step).

Tabs: **Schedule · Outfits · Metrics**.

---

## 1. Architecture & tech approach

| Concern | Decision |
|---|---|
| Location | New route group `web/app/admin/` → `/admin/schedule`, `/admin/outfits`, `/admin/metrics` |
| Reads | Server components → new `web/lib/admin.ts` (server-only Supabase client) |
| Writes | Next.js **server actions** using `SUPABASE_SERVICE_ROLE_KEY` (server-only) |
| Auth | **Supabase Auth** + email allowlist, middleware-guarded (§2) |
| Pipeline triggers | **Job queue** executed by a Python worker (§1.1) |
| Styling | Reuse the existing design tokens (bronze accent, serif headings, Geist) in a denser, responsive admin layout |

The public site keeps using the anon key and stays read-only. The admin area is the
only part that writes.

### 1.1 Triggering the Python pipeline from the web

The dashboard deploys as Next.js (e.g. Vercel) and cannot run Python directly, while
the pipeline is Python (runs in WSL / on your machine). Actions that need the pipeline
— regenerate an outfit's image or collage, or run a concept — go through a queue:

1. The button inserts a row into a new **`jobs`** table:
   `{id, type ('regenerate_image' | 'regenerate_collage' | 'run_concept' |
   'link_check'), payload jsonb, status ('queued' | 'running' | 'done' | 'failed'),
   result jsonb, created_at, updated_at}`.
2. A small **Python worker** (`scripts/worker.py`, run via cron each minute or as a
   persistent process where the pipeline lives) polls `jobs`, executes the matching
   call, and updates `status`/`result`.
3. The dashboard reads the row to show live status (queued → running → done).

---

## 2. Authentication & verification

The public site uses the **anon** key and is read-only. The admin area writes data and
exposes private controls, so it is locked down:

1. **Login** at `/admin/login` via Supabase Auth — email **magic link** (passwordless),
   restricted to your address.
2. **Allowlist**: gate on `ADMIN_EMAILS` (env) even after valid auth, so a stray signup
   can never reach `/admin`.
3. **Middleware** (`web/middleware.ts`) verifies the Supabase session cookie on every
   `/admin/*` request; unauthenticated requests redirect to login.
4. **Server-side writes only**, holding `SUPABASE_SERVICE_ROLE_KEY` (never
   `NEXT_PUBLIC_`, never sent to the browser).
5. **Row Level Security**: anon keeps `SELECT` on public data; all writes run through
   the service role behind the auth check.
6. Optional hardening: 2FA, short session TTL, and the audit log (§9).

Env additions (`web/.env.local`): `SUPABASE_SERVICE_ROLE_KEY`, `ADMIN_EMAILS`.

---

## 3. Responsive design

Desktop is the main version; mobile is a complete, first-class adaptation — every
action available on desktop is available on mobile.

- **Desktop (primary)**: a left **sidebar** (logo, the three tabs, a "Run pipeline"
  action, logout) with a max-width content area and multi-column grids.
- **Mobile (full parity)**: the sidebar collapses to a **bottom tab bar** (thumb-
  reachable Schedule / Outfits / Metrics) plus a compact top bar with an overflow "⋯"
  for global actions. Cards stack full-width, carousels are **swipeable**, and menus /
  date-time pickers open as **bottom sheets**.
- Tap targets ≥ 44px, sticky section headers, generous spacing.

```
DESKTOP (primary)                     MOBILE (full parity)
┌────────┬───────────────────┐        ┌───────────────────────┐
│ VA     │  <Tab content>    │        │ VA   Schedule      ⋯  │  top bar
│ ─────  │                   │        ├───────────────────────┤
│ ▸Sched │                   │        │                       │
│  Outfit│   multi-column    │        │   full-width cards    │
│  Metric│                   │        │                       │
│ ─────  │                   │        ├───────────────────────┤
│ ▶ Run  │                   │        │ [Sched][Outfit][Metric]│  bottom tabs
│ logout │                   │        └───────────────────────┘
└────────┴───────────────────┘
```

---

## 4. Data model changes

`posts` already has: `id, concept_id, outfit_id, platform, status, image_path,
caption, platform_post_id, published_at, created_at, updated_at, metadata_json`.
Slideshow slides already live in `metadata.image_paths`.

**Add to `posts`:**

| Column | Type | Purpose |
|---|---|---|
| `scheduled_for` | `timestamptz` null | Intended post time (frees `published_at` to mean "actually posted"). |
| `queue_order` | `timestamptz` default `created_at` | FIFO ordering of the queue; set to `now()` on cancel → back of queue. |
| `is_manual_schedule` | `bool` default false | Human-pinned time; the auto-queue never moves it. |
| `link_check` | `jsonb` null | Affiliate link health result (`{checked_at, dead:[...]}`). |

**Status lifecycle:** `needs_approval` → `queued` → `scheduled` → `published` /
`failed`. (`queued` replaces the old generic `draft` for an approved, unscheduled
post.) Delete is a true row delete, allowed only before `published` (see §5).

**New tables:**
- `jobs` — pipeline trigger queue (§1.1).
- `admin_actions` — lightweight audit log: `{id, action, target_id, at}`.

All changes are additive; existing pipeline code continues to work.

---

## 5. Tab — Schedule

The core tab: approval gate feeding a FIFO queue, with manual overrides.

### Layout

- **Top**: a one-line summary ("2 scheduled today · 4 queued · 3 awaiting approval")
  and platform filter chips: **All / TikTok / Pinterest**.
- **Three sections** in workflow order (all visible on desktop; a segmented control
  switches between them on mobile):
  1. **Needs Approval** — newly generated posts, each with a prominent **Approve**
     action. Approving moves the post into the queue.
  2. **Scheduled** — `status='scheduled'`, grouped by **day** with sticky date
     subheaders, each card showing its **time**, sorted ascending.
  3. **Queue** — approved `queued` posts in FIFO order (`queue_order`): the exact
     order they will auto-fill upcoming slots.

### Post card

```
┌─────────────────────────────────────┐
│ [TikTok ▣]            10:00 AM  ⋯   │  platform badge · time (if scheduled) · 3-dots
│ ┌─────────────────┐                 │
│ │  ◀  slide 2/5  ▶ │  swipeable      │  carousel for TikTok slideshows
│ │   [collage img]  │                 │
│ └─────────────────┘                 │
│ "Full generated caption and          │  caption (editable inline)
│  hashtags…"                          │
│ Concept: Bad Bunny · Outfit #003  ⚠ │  reference link → Outfits · link warning
└─────────────────────────────────────┘
```

- **TikTok** cards render a **click-through carousel** of slides
  (`metadata.image_paths`, one collage per outfit) with a counter; **Pinterest** cards
  show a single image.
- The **caption** sits below the media and is **editable inline** (3-dots → Edit
  caption; a bottom sheet on mobile).
- A **⚠ link warning** appears when the link health check flags a dead product link.

### 3-dots menu (bottom sheet on mobile)

| Action | Available in | Effect |
|---|---|---|
| **Approve** | Needs Approval | `needs_approval` → `queued`; enters the FIFO queue. |
| **Edit caption** | any | Inline edit of `caption`. |
| **Schedule now…** | Queue / Scheduled | Date + time picker. Sets `scheduled_for`, `status='scheduled'`, `is_manual_schedule=true`. **Bypasses FIFO** — pinned to that time. |
| **Cancel schedule** | Scheduled | `status='queued'`, `scheduled_for=null`, `queue_order=now()` → **back of the queue**. |
| **Delete** | pre-published | **True delete** of the row. |

Approving a post only moves it into the FIFO queue; assigning a specific time is a
separate, explicit **Schedule now** action.

### FIFO auto-queue (reconcile)

`schedule_service` keeps a rolling **3-day window** filled from the `queued` posts:

1. Fixed daily **slot template** per platform (§8): Pinterest at 10:00 / 12:00 / 14:00
   / 16:00 / 18:00 EST; TikTok once a day at 12:00 EST.
2. For each empty slot in `[today, today+3)`, pop the oldest `queued` post of that
   platform by `queue_order` → set `scheduled_for = slot`, `status='scheduled'`.
3. `is_manual_schedule=true` posts are never moved.
4. Runs on `/admin/schedule` load **and** via a daily cron (`/api/admin/reconcile`),
   so the window stays filled even when the dashboard is closed.

---

## 6. Tab — Outfits

### Layout

- **Top**: filter chips by **concept** and by **status** (Posted / Scheduled / On site
  / Unused).
- **Card grid** (desktop 3–4 columns, mobile 2 → 1 on small screens):

```
┌──────────────┐
│  [collage]   │
│  Bad Bunny   │   concept · #003
│ ●Posted ●Site│   status badges
└──────────────┘
```

- **Status badges**, derived via joins:
  - **Posted** — a `posts` row for the outfit is `published`.
  - **Scheduled** — a `posts` row is `scheduled` (tap shows the time).
  - **On site** — concept is `active`, the outfit has a usable layout and hosted
    images (it would render on `/concept/[id]`).

### Detail sheet (tap a card)

A full-screen sheet on mobile, side drawer on desktop:
- Rendered collage, full product list (name, retailer, price, link), captions.
- **⚠ link health** per product.
- Actions that enqueue jobs (§1.1) with a live status chip:
  - **Regenerate image** (re-isolate a product image)
  - **Regenerate collage** (re-render the layout)
- Links to the outfit's posts in the Schedule tab.

---

## 7. Tab — Metrics

Reads the existing `metrics` table and concept `ranking_score`.

### Layout

- **Top**: a date-range selector and a row of **summary stat cards** (Views, Clicks,
  Saves, Avg score) — 4-up on desktop, 2-up on mobile.
- **Concept performance** list: each concept with `ranking_score`, a trend sparkline,
  usage count, and a **retirement-proximity** indicator that shifts toward red as the
  score nears the 25 threshold. Sorted worst-trending first.
- **Posts table** (desktop) / **stacked metric cards** (mobile): per-post views, likes,
  comments, shares, saves, clicks, and computed score; sortable.
- **+ Add metrics** button → a form to enter platform numbers for a post (reuses
  `record_metrics`), since metrics are entered manually today.

---

## 8. Global actions (sidebar / overflow)

- **Run pipeline**: a sheet to pick a **concept** + **batch size (1 or 5)**, enqueuing a
  `run_concept` job (§1.1) with live status.
- **Check links**: enqueues a `link_check` job that HEAD-requests each product link and
  writes results to `posts.link_check`, surfacing **⚠** on the relevant cards.
- **Activity log**: a chronological list from `admin_actions` (action, target, time).
- **Logout**.

---

## 9. Backend & pipeline changes

| File | Change |
|---|---|
| Supabase schema (`storage_service.py` / migrations) | Add the `posts` columns (`scheduled_for`, `queue_order`, `is_manual_schedule`, `link_check`); add `jobs`, `admin_actions`. |
| `app/db/posts.py` | Support the new fields; add `list_posts_by_status`, `approve_post`, `reschedule_post`, `cancel_schedule`, `delete_post` (hard, pre-published only), `set_queue_order`. |
| `app/pipelines/publish_pipeline.py` | Write `scheduled_for` instead of overloading `published_at`; create new posts as `needs_approval` so they flow through the approval gate. |
| New `app/services/schedule_service.py` | FIFO reconcile (slot template, fill the 3-day window, respect manual pins). |
| `app/services/asset_storage.py` + collage pipeline | **Upload rendered collages to Supabase storage** and store the public URL, so schedule/outfit cards can display slide images. Required — today only product cutouts are uploaded; collages stay on local disk. |
| New `scripts/worker.py` | Polls `jobs`; runs regenerate / run-concept / link-check; updates status. |
| New `app/services/link_health.py` | HEAD-checks product/affiliate URLs; writes `posts.link_check`. |
| New `web/lib/admin.ts`, `web/middleware.ts`, `web/app/admin/**` | Server data layer + mutations, the auth guard, and the three tabs + login. |

The public site (`web/lib/data.ts`, `/`, `/concept/[id]`) is untouched.

---

## 10. TikTok (stubbed until audit)

- The Schedule UI, approval flow, queue, 3-dots actions, and a "Post now" affordance
  are fully built.
- The real TikTok publish (`autopublish_posts` → `_publish_tiktok_post`) stays behind
  the existing `AUTOPOSTING_ENABLED` flag with a clear "TikTok not connected" UI state.
- Once the audit approves **Direct Post**, the flag flips and the same UI drives fully
  automated public posts. Pinterest can go live sooner (lighter approval).

---

## 11. Configuration (fixed constants)

| Setting | Value |
|---|---|
| Schedule window | **3 days** (fixed) |
| Pinterest slots | **10:00, 12:00, 14:00, 16:00, 18:00 EST** |
| TikTok slot | **12:00 EST**, once per day |
| Approval behavior | Approve → FIFO queue; assigning a time is the separate **Schedule now** action |
| Delete | True row delete, pre-published posts only |

---

## 12. Build order

1. **Auth + `/admin` shell** — Supabase Auth, middleware, allowlist, sidebar/bottom-tab
   nav, empty tabs.
2. **Collage → Supabase storage** upload (unblocks showing slide images).
3. **Schedule tab read-only** — three sections, swipeable carousel cards, over real data.
4. **Schedule writes** — approve, edit caption, schedule/cancel/delete, FIFO reconcile + cron.
5. **Jobs system** — `jobs` table + `scripts/worker.py`.
6. **Outfits tab** — status badges, detail sheet, regenerate via jobs.
7. **Metrics tab** — summary, concept trends, manual entry.
8. **Link health + activity log.**
9. Flip TikTok/Pinterest from stub to live once access is approved.
