# Product Sourcing

The first product source is Google Shopping through an API provider. The current adapter is SerpApi's Google Shopping engine.

No product search or product detail scraping should be used. If a provider does not expose an API, it should not be part of the automated sourcing layer.

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

The initial `AFFILIATE_PROVIDER=none` resolver intentionally leaves `affiliate_url` null. Future resolvers can populate it for ShopMy, Skimlinks, or other networks.

## Retailer Policy

The product pipeline filters suspicious or scam-prone retailers before selection.

Cheap retailers are not automatically blocked if the item is low-stakes and gimmicky, such as a hat, sunglasses, jewelry, or small accessory. For reusable wardrobe pieces like shoes, outerwear, denim, or dresses, suspicious and ultra-disposable sources should be avoided.

After filtering, the deterministic ranking prefers cheaper safe items first, with missing prices ranked last.

## Candidate Storage

For each search query, the pipeline stores accepted candidates and marks their `candidate_rank` in metadata. The outfit only selects one product per search slot initially, but the stored candidate set remains available for audit, debugging, and later replacement logic.

## Images

Product image URLs are downloaded into local storage before collage rendering. The image pipeline prefers:

1. existing `local_image_path`
2. downloaded `image_url`
3. deterministic placeholder image

Downloaded images are normalized before collage rendering and the normalized local path is written back to the product record.
