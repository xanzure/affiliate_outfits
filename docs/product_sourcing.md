# Product Sourcing

Set the active source with `PRODUCT_SEARCH_PROVIDER`. Supported providers:

- `google_shopping` — SerpApi's Google Shopping engine (current default). Returns
  merchant product photos and links across retailers.
- `awin` — the local AWIN affiliate catalog (see below). Queries a downloaded
  product feed, so results carry pre-built affiliate URLs and zero per-search cost.
- `fixtures` — local fixtures for tests/offline development.

No product search or product detail scraping should be used. If a provider does
not expose an API or feed, it should not be part of the automated sourcing layer.

## AWIN Affiliate Catalog

`AWINProductSearchProvider` queries a local SQLite catalog
(`data/awin_catalog.sqlite3`) built from approved AWIN merchant product feeds.
Each feed is a bulk CSV/XML of products with names, images, prices, and
pre-built affiliate URLs — no per-search API cost.

- `scripts/sync_awin_feeds.py` downloads every approved feed into the catalog
  (`--stats` prints counts). It needs `AWIN_PUBLISHER_ID` and `AWIN_OAUTH2_TOKEN`
  in `.env`.
- Implemented in `app/services/awin_feed_service.py` (download/parse/upsert) and
  `app/db/awin_catalog.py` (catalog + full-text search).
- Switch the pipeline over with `PRODUCT_SEARCH_PROVIDER=awin` once merchants are
  approved and the catalog is populated.

## Provider Boundary

Product search providers return normalized candidates with:

- retailer
- name
- category
- normal product URL
- product image URL
- price
- currency
- source metadata

The pipeline should be able to swap `google_shopping` for a future affiliate catalog provider without changing outfit generation, image processing, collage rendering, publishing, or the website.

## Links

Product records store two link fields:

- `url`: standard product page URL
- `affiliate_url`: tracked affiliate URL, nullable

The website uses one shopping link per product: `affiliate_url` when present, otherwise `url`.

The initial `AFFILIATE_PROVIDER=none` resolver intentionally leaves `affiliate_url`
null when using `google_shopping`. The `awin` provider supplies affiliate URLs
directly from the feed. Future resolvers can populate `affiliate_url` for other
networks (CJ, Impact, etc.).

## Retailer Policy

The product pipeline filters suspicious or scam-prone retailers before selection
(`is_allowed_retailer` / `BLOCKED_RETAILER_TERMS` in `product_search_service.py`).

Hard-blocked: ultra-disposable dropship sources (AliExpress, Temu, Wish, etc.) and
resale/secondhand marketplaces (Poshmark, eBay, Depop, ThredUp, Vinted, etc.) —
the latter have no affiliate links and unpredictable stock.

Cheap retailers are not automatically blocked if the item is low-stakes and
gimmicky, such as a hat, sunglasses, jewelry, or small accessory. For reusable
wardrobe pieces like shoes, outerwear, denim, or dresses, suspicious and
ultra-disposable sources should be avoided.

After filtering, the deterministic ranking prefers cheaper safe items first, with missing prices ranked last.

## Candidate Storage

For each search query, the pipeline stores accepted candidates and marks their `candidate_rank` in metadata. The outfit only selects one product per search slot initially, but the stored candidate set remains available for audit, debugging, and later replacement logic.

## Images

Product image URLs are downloaded into local storage before collage rendering. The image pipeline prefers:

1. existing `local_image_path`
2. downloaded `image_url`
3. deterministic placeholder image

Downloaded images are normalized before collage rendering and the normalized local path is written back to the product record.
