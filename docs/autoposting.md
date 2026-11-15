# Autoposting

Autoposting is disabled by default (`AUTOPOSTING_ENABLED=false`). With it off,
the pipeline still creates every post record; nothing is sent to a platform.

## Lifecycle

```text
draft, approved=false  →  Needs Approval   (pipeline output lands here)
draft, approved=true   →  Queue            (per platform, FIFO by queue_order)
published              →  Live             (cannot be deleted)
failed                 →  Failed           (Retry available)
```

1. **Generate.** A pipeline run creates 1 TikTok slideshow draft (all five
   collages as slides) and 5 Pinterest drafts (one pin per outfit). Nothing is
   approved automatically.
2. **Approve.** Approving a draft in the dashboard appends it to the tail of its
   platform's queue (`queue_order` = epoch millis). Queues can be reordered.
3. **Publish.** The worker loop runs `process_queue_tick` about once a minute.
   For each platform, if its cooldown has elapsed — or it has never posted — it
   publishes the head of that platform's queue.
4. **Post now / Retry** enqueue a `retry_post` job that publishes immediately,
   bypassing the cooldown, and restarts that platform's window.

### Cooldown

`POST_COOLDOWN_HOURS` (default 24) is the minimum gap between posts per
platform. It is **derived, not stored**: the latest of any post's
`published_at` and its `last_publish_attempt_at` stamp. Failed attempts count
too — otherwise a bad token would publish-fail the entire queue into Failed in a
few minutes. Set it low (e.g. `0.05`) to smoke-test end to end.

There are no timezones or time slots anywhere in this model; an earlier
design that pinned posts to fixed Eastern-time slots was removed because it was
DST-buggy and complicated to reason about. See the [build log](progress.md).

`queue_order` is a 15-digit zero-padded numeric string so that string order
equals numeric order for both kinds of key (epoch millis on approve, small
integers after a manual reorder).

## Public media URLs

TikTok and Pinterest pull images from public URLs. Collages live in Supabase
Storage, but TikTok's `PULL_FROM_URL` only accepts URLs on a domain you've
verified you own — and nobody can verify `*.supabase.co`. So storage is proxied
through the site:

```text
https://<project>.supabase.co/storage/v1/object/public/<path>
  → https://www.vancearchives.com/media/<path>      (rewrite in web/next.config.ts)
```

The publisher rewrites Storage URLs to the proxied form when `SUPABASE_URL` and
`PUBLIC_ASSET_BASE_URL` are both set. Local file paths are mapped onto
`PUBLIC_ASSET_BASE_URL` directly.

## TikTok

Content Posting API, photo mode (slideshows).

```env
TIKTOK_CLIENT_KEY=
TIKTOK_CLIENT_SECRET=
TIKTOK_REDIRECT_URI=
TIKTOK_ACCESS_TOKEN=          # from scripts/tiktok_auth.py
TIKTOK_REFRESH_TOKEN=
TIKTOK_POST_MODE=DIRECT_POST
TIKTOK_PRIVACY_LEVEL=SELF_ONLY
```

- `scripts/tiktok_auth.py` runs the OAuth flow. TikTok requires PKCE, and its
  `code_challenge` is a **hex** SHA-256 digest rather than the base64url the
  spec calls for.
- Unaudited apps can only post to private accounts with `SELF_ONLY` privacy.
  Public posting requires TikTok's app audit.
- The media domain must be verified in the TikTok developer portal (see above).

## Pinterest

API v5, one image pin per outfit, linking to the first product.

```env
PINTEREST_API_BASE_URL=https://api-sandbox.pinterest.com
PINTEREST_CLIENT_ID=
PINTEREST_CLIENT_SECRET=
PINTEREST_REDIRECT_URI=
PINTEREST_ACCESS_TOKEN=       # from scripts/pinterest_auth.py
PINTEREST_REFRESH_TOKEN=
PINTEREST_BOARD_ID=
```

- Trial-access apps can only write to the **sandbox** host, with a separate
  sandbox token and a board created in the sandbox
  (`scripts/pinterest_auth.py create-board`). Switch the base URL to
  `https://api.pinterest.com` after Standard access is granted.

## Commands

```bash
python3 scripts/worker.py --loop     # jobs + queue tick (production path)
python3 scripts/publish_due.py       # run one queue tick by hand
```
