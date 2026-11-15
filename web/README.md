# Vance Archives — Web

Next.js app with two halves:

- **Public site** (`app/(site)/`) — read-only concept and outfit pages, reading
  Supabase directly with the anon key. Collages are rebuilt interactively from
  stored layout data.
- **Admin dashboard** (`app/admin/`) — auth-gated tabs for approving and queueing
  posts, managing outfits and the product wardrobe, metrics, and an activity log.

See [../docs/website.md](../docs/website.md) for pages, the data layer, and the
dashboard.

## Develop

```bash
cp .env.example .env.local   # fill in Supabase values
npm install
npm run dev                  # http://localhost:3100
npm test                     # Vitest (Supabase is mocked; no keys needed)
```

Set `ADMIN_DEV_BYPASS=true` in `.env.local` to skip the admin login locally (it's
ignored in production).

## Structure

- `app/(site)/` — `/` concepts index, `/concept/[id]` detail, `terms`, `privacy`
- `app/admin/` — dashboard routes; `(dashboard)/*/actions.ts` are server actions
- `proxy.ts` — guards `/admin/*` (session + email allowlist)
- `components/` — public components (`OutfitCanvas`, `ConceptCard`, …) and
  `components/admin/`
- `lib/data.ts` — public-site data access
- `lib/admin.ts` — dashboard data layer (queue sections, cooldowns, outfits, metrics)
- `lib/auth.ts` — admin allowlist and dev bypass
- `tests/` — Vitest suite, with an in-memory Supabase fake (`fakeSupabase.ts`)
