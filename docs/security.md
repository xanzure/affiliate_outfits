# Security Pass — 2026-10-07

A one-pass security review of the project: database access control, dependency
CVEs, and secret hygiene. Findings and remediations below.

## 1. Database access control — 🔴 Critical (fixed)

**Finding.** The Supabase database shipped with **RLS disabled on all 8 tables**,
the public `anon` role granted full `SELECT/INSERT/UPDATE/DELETE/TRUNCATE`, and
`EXECUTE` on the `SECURITY DEFINER` `_rpc_query` / `_rpc_exec` SQL bridge. Since
`NEXT_PUBLIC_SUPABASE_ANON_KEY` ships in the browser bundle, **anyone on the
internet could run arbitrary SQL or wipe the database** with one HTTP request.
Verified live: the anon key read `posts` and executed `SELECT 1` via the RPC.

**Fix (applied + verified).** See the hardening block at the end of
`app/db/schema_postgres.sql` (idempotent):
- Revoked the `_rpc_*` bridge from `PUBLIC`/`anon`/`authenticated` (only
  `service_role` may run it).
- Revoked all writes + non-public reads from the public roles (TRUNCATE is **not**
  gated by RLS, so the grant revoke is required, not optional).
- Enabled RLS on every table; `service_role` (worker + dashboard) bypasses it.
- Added anon `SELECT`-only policies for the 3 tables the public site reads
  (`concepts`/`outfits`/`products`).
- Locked default privileges so future tables aren't auto-exposed.

**Verified after fix:** anon read of `posts` → 401; anon `_rpc_query` → 401; anon
`DELETE` → 401; public gallery reads → 200; service-role path → unaffected.

**Follow-up.** The `_rpc_query`/`_rpc_exec` SECURITY DEFINER bridge is a smell even
locked down — longer term, replace the REST-RPC DB layer (`app/db/pg_connection.py`)
with a real pooled Postgres connection.

## 2. Dependency CVEs

Audited with `pip-audit` (Python) and `npm audit` (dashboard).

**Python — fixed.** Pinned secure minimums in `requirements.txt` and upgraded:
- `Pillow` 12.2.0 → **12.3.0** (PYSEC-2026-3493..3496, 3454 — image parsing; used
  directly by the collage renderer).
- `urllib3` → **2.8.0**, `PyJWT` → **2.15.1** (transitive via supabase/requests).
- `pip` / `setuptools` advisories remain — build tooling only, not shipped; CI uses
  a fresh pip.
- Re-audited clean; test suite still green (71 passed, 2 live-skipped).

**Dashboard (npm).**
- Fixed: `sharp`/libvips/libheif/librsvg CVEs (1 critical + highs) by bumping
  `next` 16.2.9 → **16.4.0**; production build verified.
- Accepted: 5 high in `braces`/`micromatch` via `eslint-config-next` — **dev-only**
  (lint tooling, not in the production bundle; `npm audit --omit=dev` is clean). The
  only "fix" downgrades eslint-config-next to v14 (breaking), so not applied.

## 3. Secret hygiene — clean

- `.env` / `web/.env.local` are gitignored and **not tracked**.
- Scanned all tracked files and the full git history for secret value prefixes
  (`sk-ant-api03-`, `sb_secret_`, `apify_api_`, `rf_live_`, `pina_`, TikTok
  `act.`): **no real secret values ever committed.**

## Recommended follow-ups
- Replace the SECURITY DEFINER SQL bridge with a pooled Postgres connection.
- Re-run the schema hardening block after any new table (default privileges make a
  new table anon-exposed until a policy/revoke is applied).
- Add `pip-audit` + `npm audit` to CI to catch new CVEs on every push.
