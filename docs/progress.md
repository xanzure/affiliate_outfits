# Build Log

How Vance Archives was built, in order, with the decisions and tradeoffs behind
each stage. For how the finished system fits together, see
[architecture.md](architecture.md).

**Timeline:** June – October 2026. Shelved November 2026.

---

## Phase 1 — Core pipeline (Jun 14–15)

The first goal was a pipeline that could turn a concept into an outfit without
any UI: creative briefs, agents, a database, a collage, post records, and tests.

- **Briefs are data, not strings.** A concept like "Bad Bunny summer concert
  outfit" is stored with context notes, style cues, and avoid rules. Every
  deterministic stage passes the full brief through untouched, so nuance isn't
  flattened into "linen summer outfit" before the agent sees it.
- **AI only for subjective calls.** Agents return JSON; deterministic validators
  check it before anything is stored. Selection, scoring, sourcing, rendering,
  and publishing are plain code.
- **SQLite first, Supabase second.** Local SQLite made every stage testable in
  isolation. Supabase (Postgres + Storage) was added the same day to back the
  public website.

**Tradeoff — the SQL-over-RPC bridge.** Rather than rewrite the data layer for
Postgres, `app/db/pg_connection.py` wraps Supabase in an object that mimics the
`sqlite3` connection API and sends raw SQL through two RPC functions. Zero
changes to the data layer and tests kept passing on SQLite. The cost showed up
months later: those functions execute arbitrary SQL with elevated privileges,
which became the centre of the [security audit](#phase-7--security-ci-tests-oct-7).

## Phase 2 — Curation and sourcing (Jun 16–18)

- **An opinionated curator agent.** Generating an outfit spec in one pass routinely
  returned the wrong product type — flares instead of bootcut, ankle boots instead
  of tall western boots. The curator now **reviews the actual search results**,
  rejects mismatches, and re-searches only the rejected slots with refined
  queries, for a bounded number of rounds. It costs 1–2 extra LLM calls per
  outfit, and product relevance improved dramatically. A hand-written store
  knowledge guide (`store_knowledge.md`) teaches it which retailers carry what.
- **Product sourcing, three attempts:**
  1. **Tavily** web search — mixed editorial pages in with products. Dropped.
  2. **SerpAPI Google Shopping** — structured results (~$25 / 1k searches), but
     it indexes print-on-demand junk and only returns thumbnails and redirect
     links.
  3. **Apify** e-commerce scraper (via API) — full-size retailer images and real
     product URLs, which the collages needed. This was the production source.
- **AWIN affiliate catalog** in parallel: merchant product feeds synced into a
  local SQLite FTS5 index — free, vetted, with affiliate links built in. Gated on
  per-merchant approval, so it became the long-term target rather than the
  primary source (3 merchants joined, ~10 pending when shelved).
- **Image isolation.** Runflow's product-isolation model when configured, local
  `rembg` otherwise, with validation that rejects blank or black cutouts and falls
  back. Cutouts go to Supabase Storage once and are reused forever.
- **Public site.** Next.js on Vercel, reading Supabase directly. Each concept
  page rebuilds its collages interactively from stored layout data instead of
  showing a flat PNG.

## Phase 3 — Dashboard, worker, first deploy (Jun 19)

- **Admin dashboard** inside the same Next.js app (separate route group): approve
  posts, browse outfits, enter metrics, read the activity log.
- **Jobs table + Python worker.** Vercel can't run the Python pipeline, and
  porting it to TypeScript wasn't worth it. Dashboard actions insert a row in a
  `jobs` table; a long-running worker claims it, runs the stage, and writes the
  result back. This kept the web app and pipeline fully decoupled.

First deploy of the worker to Railway surfaced three production-only bugs in one
day:

| Symptom | Cause | Fix |
|---|---|---|
| Crash on startup | `imghdr` was removed in Python 3.13 | Sniff image type from magic bytes |
| Regenerate collage failed | Container disk is ephemeral; local images were gone | Fall back to downloading the cutout from Storage |
| Worker killed mid-run | `rembg`'s default model blew the memory limit | Switch to the smaller `u2netp` model |

**The login saga.** Magic-link email was replaced with password sign-in, and then
sign-in itself took five iterations: client-side auth → surfacing errors → a
server action → a route handler → finally setting the session cookies directly on
the redirect response. The lesson: with SSR auth, the cookie has to be on the
response the browser actually follows.

## Phase 4 — Collages as templates (Jun 23)

The collage renderer went through five designs:

1. Fixed grid — ignored aspect ratios.
2. Weighted single column — better proportions, no hierarchy.
3. **Spine + flanks** in PIL — core garments head-to-toe down the centre,
   accessories at body-appropriate heights on either side. A category resolver
   reads descriptors right-to-left so "mini crossbody **bag**" isn't classified
   as a dress.
4. Waist-anchored layout, measuring each cutout's alpha channel with numpy.
5. **HTML/CSS templates rendered in headless Chromium** (current). Real drop
   shadows, web fonts, and editorial composition that PIL geometry couldn't
   reach — ten templates keyed by outfit shape.

**Tradeoff — template first, then sourcing.** The curator picks each outfit's
template *before* generating it, and the template dictates the item composition.
Items are sourced to fit the layout, instead of forcing a layout around whatever
was found. The price is a heavier worker image: the Docker build moved to the
official Playwright base image so Chromium is available.

Also this week: TikTok OAuth required PKCE, and TikTok's `code_challenge` turned
out to be a **hex** SHA-256 digest rather than the base64url the spec defines —
found by trial and error against the live endpoint.

## Phase 5 — Cost and variety (Jun 25–26)

- **Reuse before you pay.** Before any paid search, the pipeline reuses an
  existing product: an explicit pick by the curator, then a deterministic
  near-match on garment zone + colour family + garment tokens. A seeded set of
  wardrobe basics gives every run something to reuse.
- **Diversity by structure, not temperature.** The curator model tier doesn't
  accept a temperature parameter, so variety comes from a **style facet system**:
  ~8 distinct directions per concept ("Y2K mall streetwear", "rockstar leather"),
  generated once and cached, with each outfit in a batch assigned a different
  facet, template, and gender presentation (seeded ~70/30).
- **Wardrobe tab** for every sourced product, with manual intake from a URL and
  editable name/category/colour/brand. A Tasks panel tracks long-running worker
  jobs from anywhere in the dashboard.
- Resale marketplaces (Poshmark, eBay, Depop, …) blocked outright — no affiliate
  links and unpredictable stock.
- **Model choice:** the curator moved to Sonnet 5 for close to Opus-level taste at
  roughly 40% of the cost; the high-volume caption and concept agents run on
  Haiku.

## Phase 6 — Publishing for real (Jul 3)

Getting posts onto the platforms exposed constraints that don't show up in docs:

- **TikTok only pulls media from domains you've verified you own**, and nobody can
  verify `*.supabase.co`. Fix: proxy Storage through the site
  (`/media/*` → Supabase), so TikTok sees `vancearchives.com`.
- **Unaudited TikTok apps can only post privately**, so the account was kept
  private for testing.
- **Pinterest trial apps can only write to the sandbox** — a separate host, token,
  and board.
- API error bodies were being swallowed by `urllib`'s generic exception; they're
  now surfaced on the failed post.

**Scheduler rewrite.** The original publisher pinned posts to fixed time slots
(Pinterest at 10/12/14/16/18 EST, TikTok at noon) with a rolling three-day FIFO
window. It had a hard-coded `UTC-5` that broke at daylight saving time, a
manual datetime picker that stored input as UTC, and it auto-approved generated
posts. It was replaced with a much simpler model:

```text
generate → Needs Approval → approve → per-platform FIFO queue → worker publishes
                                                                the head once per
                                                                24h cooldown
```

- **No timezones anywhere.** The cooldown is a duration, not a clock time.
- **Cooldown is derived, not stored** — the latest `published_at` or failed-attempt
  stamp for that platform. Counting failures is deliberate: with a bad token, a
  naive version would publish-fail the entire queue in a few minutes.
- **`queue_order` is a 15-digit zero-padded string**, so string order equals
  numeric order for both epoch-millis keys (on approve) and small integers (after
  a manual reorder).
- Nothing publishes on generation; "Post now" is the only bypass.

**Tradeoff — `approved` boolean vs. new status values.** Queue state is
`status='draft' AND approved=true` rather than a new `queued` status. That avoided
a CHECK-constraint migration on a live table, and every section of the UI is
still derivable from `status` + `approved`.

## Phase 7 — Security, CI, tests (Oct 7)

A security review found a **critical** issue:
every table had row-level security **off**, and the public `anon` role — whose key
ships in the browser bundle by design — had full read/write access *and* could
execute the SQL bridge from Phase 1. Anyone could have read, rewritten, or
truncated the database with one HTTP request. Verified live, then fixed with an
idempotent hardening block in `app/db/schema_postgres.sql` (details in
[security.md](security.md)).

**Lesson:** with Supabase, the anon key is public, so RLS is load-bearing from day
one. "RLS off" isn't a dev convenience; it's an open database.

Same pass:

- Patched dependency CVEs (Pillow, urllib3, PyJWT; Next.js for `sharp`) and
  scanned the full git history for secrets (clean).
- **GitHub Actions CI**: pytest (hermetic — local SQLite, no network; the two
  live-LLM tests skip without a key) plus a dashboard job.
- **Vitest suite for the dashboard** (39 tests, Supabase replaced by an in-memory
  fake): the `/admin` auth gate, allowlist and dev-bypass gating, queue ordering,
  cooldown math, metrics aggregation, and the schedule actions. Writing it found
  a real bug — TikTok slideshow posts were listed twice on the first outfit,
  because their `outfit_id` is also the first entry in `outfit_ids`.

## Shelved (Nov 2026)

The paid services (LLM, product search, worker hosting) were switched off. The
code is intact and documented so it can be reconnected with keys alone; see
[Reconnecting](../README.md#reconnecting).

---

## Tradeoffs at a Glance

| Decision | Chose | Over | Why |
|---|---|---|---|
| Where AI is used | Subjective calls only (curation, captions, concepts) | End-to-end agents | Deterministic stages are testable, reproducible, and cheap |
| Pipeline ↔ web | `jobs` table + Python worker | Port pipeline to TypeScript / edge functions | Vercel can't run Python; a queue decouples both sides |
| DB access | sqlite-shaped wrapper over Supabase RPC | Rewrite for a Postgres driver | No data-layer rewrite — **but** it created the worst security risk in the project |
| Product source | Apify (live), AWIN (target) | SerpAPI, Tavily | Image quality first; AWIN for cost + affiliate links once approved |
| Background removal | Runflow → `rembg` fallback | One provider | Quality when paid, free path always works |
| Collage rendering | HTML/CSS templates in Chromium | PIL geometry | Typography and shadows PIL can't do; heavier container |
| Outfit ↔ layout | Template chosen before sourcing | Layout fitted after | Items match the layout instead of fighting it |
| Variety | Seeded style facets | Sampling temperature | Model tier rejects temperature; structure is more controllable |
| Publishing cadence | Approval queue + derived 24h cooldown | Fixed EST time slots | No DST/timezone bugs; failure-safe; far simpler |
| Queue state | `approved` boolean | New status enum | No risky migration on a live table |
| AWIN catalog store | SQLite FTS5 | Postgres full-text | Simple, fast local text search over large feeds |
| Auth | Supabase password + email allowlist | Magic link, NextAuth/Clerk | Already on Supabase; allowlist enforced in proxy *and* server |
| Model tiers | Sonnet 5 for curation, Haiku for copy | One model everywhere | Spend where taste matters |
