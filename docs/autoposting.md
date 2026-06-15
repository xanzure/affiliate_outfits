# Autoposting

Autoposting is optional and disabled by default.

The pipeline always creates local post records. When `AUTOPOSTING_ENABLED=true`, the publisher attempts to send due records to TikTok and Pinterest and then stores platform IDs in the database.

## Required Hosting

TikTok and Pinterest need public media URLs. Local files such as `data/images/collages/outfit.png` must be available from a public base URL.

Set:

```env
PUBLIC_ASSET_BASE_URL=https://your-public-asset-host.example
```

The publisher maps a local path like:

```text
data/images/collages/outfit.png
```

to:

```text
https://your-public-asset-host.example/data/images/collages/outfit.png
```

## TikTok

TikTok uses the Content Posting API photo endpoint for slideshow-style posts. The daily TikTok record uses all five collage image paths from the selected concept.

Required environment:

```env
TIKTOK_ACCESS_TOKEN=
TIKTOK_POST_MODE=DIRECT_POST
TIKTOK_PRIVACY_LEVEL=SELF_ONLY
TIKTOK_DISABLE_COMMENT=false
TIKTOK_AUTO_ADD_MUSIC=true
TIKTOK_BRAND_CONTENT_TOGGLE=false
TIKTOK_BRAND_ORGANIC_TOGGLE=false
```

Notes:

- `DIRECT_POST` requires the user access token to include the correct TikTok posting scope.
- Unaudited TikTok clients may be restricted to private posting.
- The image URLs must be on a domain/prefix accepted by TikTok for URL pulling.

## Pinterest

Pinterest creates one pin per outfit collage. Pins are scheduled locally at spaced times; Pinterest posting happens only when `scripts/publish_due.py` runs and the scheduled time has arrived.

Required environment:

```env
PINTEREST_ACCESS_TOKEN=
PINTEREST_BOARD_ID=
```

## Commands

Daily generation:

```bash
python3 scripts/run_daily.py
```

Publish due posts:

```bash
python3 scripts/publish_due.py
```

Run `publish_due.py` periodically if you want Pinterest posts to go out through the day.
