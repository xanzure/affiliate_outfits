# Image Service

The image service turns raw product photos (model shots, lifestyle scenes,
flat-lays, multi-item images, or already-clean CDN shots) into clean transparent
PNG cutouts ready for collage rendering.

Implemented in `app/services/image_service.py`, wired into
`app/pipelines/image_pipeline.py`. The collage renderer consumes only
`PreparedImage.normalized_path`, which is always a valid transparent PNG.

## Primary path — Runflow `product-isolation`

Runflow's `product-isolation` model is the catch-all. It generatively isolates a
**prompt-named** item from any source and returns a clean product on off-white
(~$0.27/run, ~30–45s).

`ImageService.process_batch(items)` — each item is `(asset_id, url, prompt)`:

1. Download all sources → `originals/` (parallel).
2. Submit all `product-isolation` runs with their prompts (parallel).
3. Poll all runs (parallel).
4. Per asset: isolation result → **rembg alpha pass** (off-white → transparent)
   → trim → `normalized/`.

The prompt is the key win: the curator/product description (e.g. *"the cobalt
blue ruched mini skirt"*) is passed so the model extracts the exact piece. This
fixes "wrong item / only 3 of 5 items / dark lifestyle blob" problems at the
source. Prompts are built by `image_pipeline._isolation_prompt`, which prefers a
curator `item_description`/`search_query` from product metadata, else the product
name with retailer/SEO prefixes stripped.

## Fallback path

`_finalize_local` runs when there is no Runflow key, or a run fails / returns
garbage: a local rembg cutout of the original, with transparent-PNG pass-through
for images that are already cutouts.

## Safety nets

- `validate_runflow_result` — rejects black/blank isolation output → fallback.
- `validate_cutout` — rejects a blank/black alpha pass → keep isolation raw.
- `_trim_transparent` — tight collage tiles.
- Shared cached rembg sessions (`isnet-general-use`).

## Tuning knobs

Constants at the top of `image_service.py`: `_RUNFLOW_RESOLUTION` ("1K"),
`_RUNFLOW_ASPECT_RATIO` ("3:4"), `_RUNFLOW_TIMEOUT`, `_MIN_VISIBLE_FRACTION`,
`_MIN_VISIBLE_BRIGHTNESS`, `_TRIM_PADDING`.

Possible improvements: per-category `aspect_ratio` (1:1 for bags/jewelry), or
bumping `_RUNFLOW_RESOLUTION` to "2K" if collage tiles look soft (cost is flat).
