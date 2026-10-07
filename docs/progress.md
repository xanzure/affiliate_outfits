# Vance Archives — Build Log & Technical Decisions

An AI-powered affiliate fashion content engine. Generates outfit concepts, sources
products, renders collages, and schedules posts to TikTok and Pinterest — fully
automated from concept seed to published content.

---

## System Overview

```
Concept seed → Outfit agent (Claude) → Product search (SerpAPI / AWIN)
→ Image isolation (Runflow + rembg) → Collage renderer (PIL)
→ Supabase storage → Next.js dashboard → TikTok / Pinterest
```

**Stack:** Python pipeline · Next.js (TypeScript) · Supabase (Postgres + Storage) · Vercel · Anthropic Claude · SerpAPI · AWIN affiliate network

---

## What Was Built

### 1. Outfit Generation Pipeline (`app/pipelines/daily_pipeline.py`)

A multi-agent LLM pipeline that takes a concept seed ("Bad Bunny Concert", "Dark
Academia") and produces a fully styled outfit with sourced products.

**Agents (all Claude via Anthropic API):**
- **Outfit agent** — generates a structured outfit spec from a concept seed: which
  garments, what aesthetic, what colour story
- **Curator agent** — evaluates candidate products against the spec, rejects mismatches
  (wrong silhouette, wrong price tier, wrong colourway), requests better alternatives
  in retry rounds
- **Style agent** — picks collage background colour, accent, font style
- **Engagement agent** — writes captions and hashtags for each platform

**Tradeoff — multi-round curator vs. single-pass:**
A single-pass approach would be faster but routinely returns wrong product types
(flare pants when bootcut was requested, ankle boots when tall western was requested).
The curator's reject-and-retry loop costs 1–2 extra LLM calls but dramatically
improves product relevance. Currently capped at 1 retry round; can be increased.

---

### 2. Product Sourcing

**Phase 1 — Tavily web search:** General web search. Returned inconsistent results,
mixed product pages with editorial content. Replaced.

**Phase 2 — SerpAPI Google Shopping (`app/services/product_search_service.py`):**
Structured product results with price, image, merchant. Much cleaner than raw web
search. Blocked resale/secondhand marketplaces (Poshmark, ThredUp, eBay, Depop,
Vinted, Vestiaire) via `BLOCKED_RETAILER_TERMS`.

**Tradeoff — Google Shopping vs. affiliate feeds:**
Google Shopping is a search index — indexes whatever is listed, including
print-on-demand junk and wrong product categories. 1,000 searches/month = ~$25.
AWIN affiliate feeds are vetted retailer catalogs with pre-built affiliate URLs,
no per-search cost, and far higher product quality. AWIN is the long-term path;
Google Shopping is the bridge until merchant approvals come through.

**Phase 3 — AWIN affiliate catalog (in progress):**
`app/db/awin_catalog.py` — SQLite FTS5 catalog populated from AWIN CSV product feeds.
`app/services/awin_feed_service.py` — downloads and ingests feeds per merchant.
`scripts/sync_awin_feeds.py` — sync runner.
3 merchants joined so far: eFootwear.com (shoes), Bonheur Jewelry, WJD Exclusives.
~10 more in pending.

---

### 3. Image Pipeline (`app/pipelines/image_pipeline.py`)

Takes raw product listing images and isolates the product (removes background).

**Runflow + rembg:** Sends images through a background-removal ML model. Results
are uploaded to Supabase Storage with public URLs so the collage renderer and
dashboard can access them.

**Tradeoff — local rembg vs. external API:**
rembg runs locally via ONNX, which means the pipeline requires a machine with
enough RAM and the model downloaded. PhotoRoom API (~$0.05/image) would remove
this dependency entirely and enable a pure-cloud deployment. Kept local for now
to avoid per-image costs during development.

---

### 4. Collage Renderer (`app/collage/export.py`)

PIL-based collage layout engine. Canvas: 1080×1350px (Instagram/TikTok portrait).

**Layout system — spine + flanks:**
- **Spine** (centre, 42% of width): core garments stacked head-to-toe (top →
  bottom → shoes)
- **Flanks** (left + right of spine): accessories (bag, jewellery, hat) placed at
  body-appropriate heights — jewellery rides high, bag sits mid
- **Outerwear** (coats, blazers, jackets): placed on whichever flank has fewer
  accessories, as a full-height editorial column piece

**Key decisions:**
- Items are fit-to-box (aspect ratio preserved) rather than fill-to-box (no distortion)
- Transparent borders are trimmed before scaling (`_trim_alpha`) so sizing reflects
  the actual product, not canvas padding
- Category resolver scans words from the right ("chunky hoop **earrings**", "mini
  woven **bag**") to find the head noun — prevents "mini" matching "dress" in
  "mini crossbody bag"
- Per-zone vertical weight controls proportions: dress/outerwear get 3.0–3.5x the
  height budget of shoes (0.8x), preventing shoes from dominating the layout
- Slight random rotation (apparel ±2.5°, accessories ±6°) for editorial feel

**Iterations:**
1. Original zone-based grid — items placed in fixed grid cells, ignored aspect ratios
2. Weight-based single column — better proportions but no hierarchy
3. Current spine+flank — outfits read like actual editorial flat-lays

---

### 5. Database (`app/db/`, Supabase Postgres)

**Core tables:** `concepts`, `outfits`, `products`, `posts`, `collages`, `metrics`

**Post lifecycle:** `draft` + `approved=false` (Needs Approval) → `draft` +
`approved=true` (Queue) → `draft` + `scheduled_for` set (Scheduled) → `published`

**Tradeoff — approved boolean vs. status enum:**
Originally considered adding `needs_approval` / `queued` as new status values.
Chose `approved: bool` on the existing `posts` table instead — avoids a risky
CHECK constraint migration on a live table with data, and the same UX is derivable
from the combination of `status` + `approved` + `scheduled_for`.

**Jobs table:** Pipeline work triggered from the dashboard goes through a `jobs`
table (`queued → running → done/failed`). The Python worker polls this table.
Decouples the web app (Next.js/Vercel) from the Python pipeline cleanly.

**AWIN catalog:** Separate SQLite FTS5 database (`awin_catalog.sqlite3`). Not in
Supabase — product feed data is large, changes frequently, and full-text search
is better served by SQLite FTS5 than Postgres for local dev. Would move to
Postgres for a hosted deployment.

---

### 6. Admin Dashboard (`web/app/admin/`)

Next.js app router, server components + server actions, Supabase Auth.

**Auth:** Magic-link email login, `ADMIN_EMAILS` allowlist enforced in both
middleware (`web/middleware.ts`) and server-side (`getAdminUser()`). Service role
key never sent to browser — all writes through server actions only.
Dev bypass via `ADMIN_DEV_BYPASS=true` (non-production only, gitignored).

**Schedule tab:**
- Three sections: Needs Approval / Scheduled / Queue
- FIFO auto-schedule (`reconcileSchedule()` in `web/lib/admin.ts`) fills a 3-day
  rolling window from the queue. Currently disabled (`AUTO_SCHEDULE_ENABLED=false`)
  while the approval flow is being validated
- Pinterest slots: 10/12/14/16/18 EST. TikTok: 12:00 EST
- Manual "Schedule now" pins a post to a specific time (bypasses FIFO)
- Post cards: swipeable multi-slide carousel, inline caption edit, 3-dots action menu

**Outfits tab:** Card grid with Posted/Scheduled/On site badges. Detail sheet with
product list, regenerate image/collage buttons (enqueues jobs), delete outfit.

**Metrics tab:** Summary stat cards, concept performance with retirement-proximity
indicator (red as `ranking_score` approaches 25), posts table, manual metrics entry.

**Global actions:** Run pipeline (concept picker + batch toggle), check links,
activity log. All enqueue jobs; status polls every 2.5s and shows in sidebar.

**Tradeoff — Python worker vs. Supabase Edge Functions:**
Vercel can't run Python. Rather than rewriting the pipeline in TypeScript, a
`jobs` table acts as a queue between the web app and the Python process. The
worker (`scripts/worker.py --loop`) runs locally or on a cheap cloud service
(Render/Railway free tier). Long-term, swapping rembg for PhotoRoom API and PIL
for `sharp` would make the pipeline pure TypeScript and eliminate the worker
entirely — Supabase Edge Functions + pg_cron would replace it.

---

### 7. Public Website (`web/app/(site)/`)

**Design system:** Cormorant Garamond serif headings, Geist body, bronze accent
(`#9a6f4a`), warm off-white canvas (`#efeae2`), linen surface.

**Route group restructure:** Public pages moved into `(site)/` route group
(shared header/footer) with `admin/` as a separate auth-gated group. This keeps
admin chrome out of public pages with zero URL change.

**Logo:** Original PNG had ~99% transparent canvas (content was 0.9% of pixels).
Auto-cropped with PIL's `getbbox()` on the alpha channel + 16px padding to
`logo_cropped.png`. Header now renders it at a legible size.

**Hover states:** Scale + gradient overlay + bronze drop shadow + `drop-shadow`
with bronze halo on outfit cards. Dark shadow prevents the card from disappearing
against the warm background.

---

### 8. Publishing Pipeline (`app/pipelines/publish_pipeline.py`)

**TikTok:** Photo slideshow (one collage per outfit in the concept run). Stubbed
behind `AUTOPOSTING_ENABLED` flag — TikTok requires an app audit for Direct Post
API access. The dashboard itself is the "demo" TikTok requires to see before
granting Direct Post.

**Pinterest:** Single image pin per outfit. Lighter approval process.

**Affiliate links:** Embedded in captions as product URLs. AWIN provides pre-built
affiliate URLs per product in their feed; Google Shopping results currently link
to the merchant page directly (no affiliate tracking until AWIN feeds are live).

---

## Key Technical Tradeoffs Summary

| Decision | Chose | Alternative | Why |
|---|---|---|---|
| Product source | SerpAPI Google Shopping → AWIN | Skimlinks / Amazon Associates | No traction requirement for AWIN; Skimlinks/Amazon require established traffic |
| Image background removal | rembg (local) | PhotoRoom API | Zero per-image cost during dev; API needed for cloud deployment |
| Collage rendering | PIL (Python) | sharp/canvas (Node.js) | Already in Python; migration path exists when going full-TypeScript |
| Worker architecture | Jobs table + Python worker | Supabase Edge Functions | Pipeline is Python; Edge Functions are TypeScript-only |
| Post approval state | `approved` boolean | New status enum values | Safer migration on live table; same UX derivable from combinations |
| AWIN catalog | SQLite FTS5 | Postgres full-text | Local dev: FTS5 is simpler and faster for text search on feed data |
| Auth | Supabase magic-link + allowlist | NextAuth / Clerk | Already using Supabase; magic-link = no password to manage |
| Long-term language | TypeScript (future) | Python (current) | Pipeline is API calls, not local ML; unified codebase eliminates worker |
| DB access layer | REST RPC bridge (`_rpc_query`/`_rpc_exec`) | Direct pooled Postgres | Reused the sqlite-shaped API over Supabase REST; **tradeoff: SECURITY DEFINER arbitrary-SQL functions are a security smell — replace with a real PG connection** |
| Row security | RLS on + anon SELECT on 3 public tables only | RLS off (initial) | Initial state left RLS off → public anon key had full DB write + arbitrary SQL; fixed 2026-10-07 (see below) |

### Security hardening (2026-10-07)

An audit found the initial Supabase setup shipped with **RLS disabled on every
table** and the public `anon` role (whose key ships in the browser bundle) granted
full write access *and* EXECUTE on the `SECURITY DEFINER` `_rpc_query`/`_rpc_exec`
SQL bridge — a remotely exploitable total-DB compromise (arbitrary SQL / `TRUNCATE`
by anyone). Fixed with an idempotent hardening block at the end of
`app/db/schema_postgres.sql`: revoke the RPC bridge and all writes/non-public reads
from the public roles, enable RLS everywhere, add anon SELECT-only policies for the
three tables the public site reads (`concepts`/`outfits`/`products`), and lock down
default privileges so future tables aren't auto-exposed. Lesson: Supabase's public
anon key makes RLS load-bearing by default; "RLS off" is a live vulnerability, not a
dev convenience.

---

## Current State (June 2026)

**Live:** Public website (Vercel), Supabase DB + Storage, image pipeline, collage
renderer, dashboard (local dev, ready to deploy)

**In progress:** AWIN merchant approvals (~13 pending, 3 joined)

**Blocked on:** TikTok Direct Post app audit (requires dashboard demo)

**Next:** Deploy dashboard to Vercel production, get AWIN feeds populated, run
pipeline with real affiliate products, apply for TikTok Direct Post

---

## Running the Project

```bash
# Python pipeline
source .venv/bin/activate
python scripts/daily_pipeline.py --concept "concept_id"

# Worker (processes dashboard-triggered jobs)
.venv/bin/python3 scripts/worker.py --loop

# Web dashboard
cd web && npm run dev   # localhost:3100/admin

# AWIN feed sync
.venv/bin/python3 scripts/sync_awin_feeds.py

# Schema migration
.venv/bin/python3 scripts/migrate_dashboard.py
```
