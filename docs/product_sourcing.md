# Product Sourcing

Set the active source with `PRODUCT_SEARCH_PROVIDER`. Supported providers, in
the order they were adopted:

| Provider | Cost | Notes |
|---|---|---|
| `tavily` | paid | General web search. First attempt; mixed editorial pages in with products. Retired. |
| `serpapi` / `google_shopping` | paid (~$25 / 1k searches) | SerpAPI's Google Shopping engine. Structured price/image/merchant, but indexes print-on-demand junk. |
| `apify` | paid | Apify's managed e-commerce scraper, called via API. Returns full-size retailer images and real product URLs, where Google Shopping only gave thumbnails and redirect links. The last provider used in production. |
| `awin` | free | Local catalog built from AWIN affiliate feeds (below). Pre-built affiliate URLs, no per-search cost. The intended long-term source. |
| `fixtures` | free | Built-in sample products for tests and offline runs. The default. |

Every provider implements the same `ProductSearchProvider` interface and returns
the same normalized `ProductSearchResult`, so switching sources is a config change.

Before any provider is called, the pipeline tries to reuse a product it already
has (an explicit pick from the curator, then a deterministic near-match on
garment zone + colour family + garment tokens). See
[architecture.md#caching](architecture.md#caching).

The project doesn't run its own scrapers. Every source is reached through an API
or a feed; a source with neither isn't part of the automated sourcing layer. Apify
is the one nuance — a managed scraping service, used because image quality from
search APIs wasn't good enough for collages — and it's the reason AWIN's
first-party feeds were the long-term target.

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

The pipeline can swap providers without changing outfit generation, image processing, collage rendering, publishing, or the website.

## Links

Product records store two link fields:

- `url`: standard product page URL
- `affiliate_url`: tracked affiliate URL, nullable

The website uses one shopping link per product: `affiliate_url` when present, otherwise `url`.

The `AFFILIATE_PROVIDER=none` resolver intentionally leaves `affiliate_url`
null for search-API providers. The `awin` provider supplies affiliate URLs
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

Each product image is isolated into a transparent cutout once (see
[image_service.md](image_service.md)) and uploaded to Supabase Storage; the
Storage URL is written back to the product. Later runs — including a worker on a
fresh container with an empty disk — reuse that cutout instead of reprocessing.
A deterministic placeholder is used only if no image can be obtained.
