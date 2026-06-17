# Robust Image Service — Plan & Status

> **STATUS: BUILT & verified end-to-end (2026-06-16).** Implemented in
> `app/services/image_service.py`, wired into `app/pipelines/image_pipeline.py`.
> Verified with live Runflow calls: model shots, lifestyle shots, and multi-item
> photos all isolate to clean transparent product cutouts. Remaining: full
> pipeline run for a Bad Bunny outfit (curator → search → images → collage).

## Final architecture — Runflow `product-isolation` as the catch-all

We discovered Runflow's **`product-isolation`** model, which is a strict superset of
model-removal + background-removal and the same price ($0.27/run, ~30-45s — *faster*
than model-removal). It generatively isolates a **prompt-named** item from ANY source
(model shot, lifestyle, flat-lay, multi-item) and returns a clean product on off-white.

This became the **primary path**, replacing the model-removal + classification design.
The prompt is the key win: we pass the curator/product description (e.g. *"the cobalt
blue ruched mini skirt"*) so it extracts the exact piece — fixing "wrong item / only
3 of 5 items / dark lifestyle blob" problems at the source.

**Pipeline (`ImageService.process_batch(items)`)** — items are `(asset_id, url, prompt)`:
1. Download all sources → `originals/` (parallel).
2. Submit all `product-isolation` runs with their prompts (parallel).
3. Poll all runs (parallel).
4. Per asset: isolation result → **rembg alpha pass** (off-white → transparent) →
   trim → `normalized/`. Verified output: clean cutout, ~0.7% halo.

**Fallback path** (`_finalize_local`) when no Runflow key or a run fails/returns
garbage: local rembg cutout of the original, with transparent-PNG pass-through.

**Safety nets:** `validate_runflow_result` (rejects black/blank isolation output →
fallback), `validate_cutout` (rejects blank/black alpha pass → keep isolation raw),
`_trim_transparent` (tight collage tiles), shared cached rembg sessions.

**Prompt building** (`image_pipeline._isolation_prompt`): prefers a curator
`item_description`/`search_query` in product metadata, else the product name with
retailer/SEO prefixes stripped ("Amazon.com : Royal Blue Dress" → "the Royal Blue Dress").

**Tuning knobs** (constants atop `image_service.py`): `_RUNFLOW_RESOLUTION` ("1K"),
`_RUNFLOW_ASPECT_RATIO` ("3:4"), `_RUNFLOW_TIMEOUT`, `_MIN_VISIBLE_FRACTION`,
`_MIN_VISIBLE_BRIGHTNESS`, `_TRIM_PADDING`.

**Still available but no longer primary:** the `classify_image` /`u2net_human_seg`
classifier (`MODEL_SHOT`/`PRODUCT`/`ALREADY_CUTOUT`) and the legacy `model-removal`
submit (`_runflow_submit`) remain in the module as utilities / future experiments.

### Open follow-ups
- If isolation quality dips on accessories, try per-category `aspect_ratio` (1:1 for
  bags/jewelry) and feed richer curator descriptions into product metadata as
  `item_description` so prompts are even more precise.
- Consider bumping `_RUNFLOW_RESOLUTION` to "2K" if collage tiles look soft (cost is flat).

---

# Original Plan (for reference — superseded by product-isolation above)


## Problem Summary

Current `image_service.py` blindly routes every product image through Runflow model-removal,
which causes two failure modes:

1. **No model in source image** → Runflow corrupts clean product shots (smears the product itself)
2. **Runflow succeeds but leaves white/solid background** → collage looks wrong (opaque square behind product)

We need a smarter routing system that classifies each image first, applies only the right tools,
and always produces a clean transparent PNG at the end.

---

## Image Types We Encounter

| Type | Example | Correct treatment |
|------|---------|-------------------|
| Lifestyle / model shot | Dark lit photo, model wearing item | Runflow → rembg cleanup |
| Product on white bg | ASOS/Mango CDN clean shot | rembg only (skip Runflow) |
| Product on colored bg | Gradient or busy bg, no model | rembg only |
| Already transparent PNG | Supplier-provided cutout | Pass through (validate only) |

---

## Pipeline Stages

### Stage 1 — Download & Save Original
- Download source URL to `originals/{asset_id}.jpg`
- Already done after today's fix

### Stage 2 — Classify Image
Function: `classify_image(path: Path) -> ImageClass`

Detection logic (all local, no API calls, fast):

**has_model** — True if any of:
- Significant skin-tone pixel cluster (HSV hue 0-50, low saturation, medium value) covering >3% of image area
- Image aspect ratio is portrait-ish (H/W > 1.2) AND skin tones present

**has_white_bg** — True if:
- >40% of edge pixels (1px border all around) are near-white (RGB all >230)
- OR image is already RGBA with alpha=0 on edges

**is_transparent** — True if:
- Image mode is RGBA and has substantial alpha-0 pixels (>10% of area)

Resulting classes:
```
MODEL_SHOT       → has_model=True
PRODUCT_WHITE_BG → has_model=False, has_white_bg=True
PRODUCT_COLORED_BG → has_model=False, has_white_bg=False, is_transparent=False
ALREADY_CUTOUT   → is_transparent=True
```

### Stage 3 — Route to Tool

```
MODEL_SHOT        → [Runflow] → [validate_result] → [rembg if bg remains]
PRODUCT_WHITE_BG  → [rembg]
PRODUCT_COLORED_BG → [rembg]
ALREADY_CUTOUT    → [skip to stage 4]
```

Runflow is only called for `MODEL_SHOT`. All other types go directly to rembg.
This prevents Runflow from corrupting clean product shots.

### Stage 4 — Validate Runflow Result
Function: `validate_runflow_result(path: Path) -> bool`

After Runflow, check:
- Image is not mostly black (mean pixel value < 20 → bad result)
- Image is not mostly transparent already (Runflow sometimes returns blank)
- Width/height not drastically different from source (sanity check)

If validation fails → fall back to rembg on the original image.

### Stage 5 — Background Cleanup
Function: `remove_background(path: Path) -> Path`

Always run rembg as a final pass for:
- `MODEL_SHOT` after Runflow (cleans any residual white/gray bg left by Runflow)
- `PRODUCT_WHITE_BG` and `PRODUCT_COLORED_BG` as primary tool

Use `rembg` with model `u2net` (default) or `isnet-general-use` (better quality, slower).

Output: transparent RGBA PNG saved to `normalized/{asset_id}.png`

### Stage 6 — Final Validation
- Ensure result has alpha channel
- Ensure non-transparent area > 5% of image (not blank)
- If blank → use a placeholder gradient tile instead of black square

---

## Parallel Batch Processing

Current flow submits all Runflow jobs in parallel, then polls in parallel — keep this.

New flow:
1. Download all source images in parallel (threads)
2. Classify all images locally (fast, CPU only, no I/O wait — can be sequential)
3. Submit MODEL_SHOT images to Runflow in parallel
4. While Runflow runs, start rembg on non-model images in parallel threads
5. Poll Runflow results, validate, run rembg cleanup
6. Save all normalized PNGs

---

## Files to Change

### `app/services/image_service.py`
- Add `ImageClass` enum: `MODEL_SHOT`, `PRODUCT_WHITE_BG`, `PRODUCT_COLORED_BG`, `ALREADY_CUTOUT`
- Add `classify_image(path) -> ImageClass` using Pillow pixel analysis
- Add `validate_runflow_result(path) -> bool`
- Add `remove_background(path) -> Path` wrapping rembg
- Rewrite `process_from_url()` to follow the 6-stage pipeline above
- Rewrite `runflow_process_batch()` to skip non-model images

### `app/pipelines/image_pipeline.py`
- `prepare_product_images()` already calls `process_from_url` per product
- May need to pass classification results through to enable smarter batching
- Minor changes only

---

## Dependencies

- `Pillow` — already installed (used in `image_utils.py`)
- `rembg` — already installed (used as fallback today)
- `runflow` — HTTP API (already integrated)
- No new dependencies needed

---

## Expected Outcome

| Scenario | Before | After |
|----------|--------|-------|
| Clean ASOS CDN product shot | Runflow corrupts it | rembg only → clean cutout |
| Dark lifestyle model shot | Runflow leaves white box | Runflow → rembg cleanup → transparent |
| Already-transparent PNG | Runflow may corrupt | Pass through |
| Runflow returns black image | Saved as black square in collage | Detected, fallback to rembg |
| Residual white bg after Runflow | White rectangle in collage | rembg cleanup pass removes it |

---

## Implementation Order

1. `classify_image()` — test against a sample of originals we have
2. `validate_runflow_result()` — test against the bad black results from last run  
3. `remove_background()` wrapper — verify rembg still works as standalone
4. Wire into `process_from_url()` with new routing logic
5. Update `runflow_process_batch()` to only submit MODEL_SHOT images
6. End-to-end test with 1 Bad Bunny outfit
