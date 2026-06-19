# Vance Archives — Frontend

Public-facing Next.js site for the affiliate content engine. It's read-only and
reads concepts/outfits/products directly from Supabase. See
[../docs/website.md](../docs/website.md) for brand direction, pages, and the data
layer.

## Develop

```bash
npm install
npm run dev   # http://localhost:3000
```

Requires Supabase credentials in `web/.env.local`:

```env
NEXT_PUBLIC_SUPABASE_URL=...
NEXT_PUBLIC_SUPABASE_ANON_KEY=...
```

## Structure

- `app/` — routes (`/` concepts index, `/concept/[id]` detail, `terms`, `privacy`)
- `components/` — `ConceptCard`, `OutfitCanvas` (interactive flat-lay), `ProductPanel`
- `lib/data.ts` — the only data-access module (Supabase queries)
- `lib/types.ts` — types mirroring the backend `models.py`
- `app/globals.css` — design tokens (warm paper bg, bronze accent, serif display)
