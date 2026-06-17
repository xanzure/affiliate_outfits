from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from urllib.request import Request, urlopen

from app.collage.image_utils import inspect_image, write_solid_png
from app.db.models import Product
from app.db.products import update_product_local_image_path, update_product_image_url
from app.services.asset_storage import SupabaseAssetStorage, asset_storage_from_env
from app.services.image_service import ImageService, PreparedImage

logger = logging.getLogger(__name__)


COLOR_MAP: dict[str, tuple[int, int, int]] = {
    "black": (32, 32, 32),
    "blue": (52, 92, 160),
    "cream": (235, 226, 205),
    "gray": (160, 160, 160),
    "grey": (160, 160, 160),
    "green": (80, 120, 80),
    "ivory": (242, 238, 222),
    "navy": (28, 46, 82),
    "olive": (105, 116, 70),
    "oat": (214, 199, 171),
    "red": (190, 54, 54),
    "soft gray": (178, 178, 174),
    "white": (245, 245, 240),
}


def prepare_product_images(
    conn: sqlite3.Connection,
    products: list[Product],
    *,
    image_service: ImageService | None = None,
    asset_storage: SupabaseAssetStorage | None = None,
) -> list[PreparedImage]:
    service = image_service or ImageService()
    storage = asset_storage or asset_storage_from_env()

    # Split products into cache hits (already processed) and ones needing work.
    # Each work item carries an isolation prompt so Runflow extracts the exact piece.
    needs_processing: list[tuple[str, str, str | None]] = []  # (asset_id, url, prompt)
    for product in products:
        if _is_already_processed(product, service):
            logger.info("cache hit %s — reusing processed image", product.id)
        elif product.image_url:
            needs_processing.append((product.id, product.image_url, _isolation_prompt(product)))

    # Robustly process all uncached images (isolate → alpha-pass → cutout) in one batch.
    batch_results: dict[str, PreparedImage] = {}
    if needs_processing:
        logger.info("Processing %d image(s) through image service...", len(needs_processing))
        batch_results = service.process_batch(needs_processing)

    # Assemble final PreparedImage per product (cache → batch result → placeholder).
    prepared_images: list[PreparedImage] = []
    for product in products:
        prepared = _prepare_one(product, service, batch_result=batch_results.get(product.id))
        if prepared.route:
            logger.info("prepared %s via %s", product.id, prepared.route)
        update_product_local_image_path(conn, product.id, str(prepared.normalized_path))

        if storage:
            try:
                public_url = storage.upload_product_image(product.id, prepared.normalized_path)
                update_product_image_url(conn, product.id, public_url)
                logger.info("uploaded %s → %s", product.id, public_url[:80])
            except Exception:
                logger.exception("storage upload failed for %s", product.id)

        prepared_images.append(prepared)

    return prepared_images


def _isolation_prompt(product: Product) -> str | None:
    """Build a short prompt naming the item to isolate, e.g. 'the cobalt ruched skirt'.

    Prefers the curator's clean item description (stored in metadata) and falls back
    to the product name with retailer/SEO noise stripped.
    """
    # Curator description is the cleanest signal when present.
    for key in ("item_description", "search_query"):
        value = product.metadata.get(key)
        if isinstance(value, str) and value.strip():
            return f"the {_clean_prompt_text(value)}"

    name = _clean_prompt_text(product.name or "")
    if not name:
        return f"the {product.category}" if product.category else None
    return f"the {name}"


def _clean_prompt_text(text: str) -> str:
    """Strip retailer prefixes and marketing noise for a tidy isolation prompt."""
    cleaned = text.strip()
    # Drop a leading "Retailer.com : " / "Retailer: " style prefix.
    for sep in (" : ", ": ", " | ", " - "):
        if sep in cleaned[:40]:
            head, _, tail = cleaned.partition(sep)
            if any(token in head.lower() for token in (".com", "amazon", "shop", "buy")):
                cleaned = tail
                break
    # Collapse whitespace and cap length so the prompt stays focused.
    cleaned = " ".join(cleaned.split())
    return cleaned[:120].strip()


def _is_already_processed(product: Product, service: ImageService) -> bool:
    """True if this product already has a clean processed image we can reuse."""
    # Already have a local normalized PNG
    local = service.normalized_dir / f"{product.id}.png"
    if local.exists():
        return True
    # image_url was already updated to our Supabase storage URL (processed + uploaded)
    if product.image_url and "supabase.co/storage" in product.image_url:
        return True
    return False


def _prepare_one(
    product: Product,
    service: ImageService,
    *,
    batch_result: PreparedImage | None = None,
) -> PreparedImage:
    # Freshly processed by the batch image service — preferred.
    if batch_result is not None:
        return batch_result

    # Already has a local processed file from a previous run.
    if product.local_image_path:
        path = Path(product.local_image_path)
        if path.exists():
            info = inspect_image(path)
            return PreparedImage(
                source_path=path,
                original_path=path,
                normalized_path=path,
                info=info,
                normalized=True,
            )

    # Local normalized PNG exists from a previous run.
    local_normalized = service.normalized_dir / f"{product.id}.png"
    if local_normalized.exists():
        info = inspect_image(local_normalized)
        return PreparedImage(
            source_path=local_normalized,
            original_path=local_normalized,
            normalized_path=local_normalized,
            info=info,
            normalized=True,
        )

    # Supabase already has the processed image — download it.
    if product.image_url and "supabase.co/storage" in product.image_url:
        try:
            return _download_to_normalized(product.image_url, product.id, service)
        except Exception:
            logger.warning("Failed to download cached Supabase image for %s", product.id)

    # Last resort: run the full image service on the source URL.
    if product.image_url:
        try:
            return service.process_from_url(product.image_url, asset_id=product.id)
        except Exception:
            logger.warning("process_from_url failed for %s, using placeholder", product.id)

    return _placeholder(product, service)


def _download_to_normalized(url: str, product_id: str, service: ImageService) -> PreparedImage:
    service.normalized_dir.mkdir(parents=True, exist_ok=True)
    dest = service.normalized_dir / f"{product_id}.png"
    req = Request(url, headers={"User-Agent": "affiliate-outfits/0.1"})
    with urlopen(req, timeout=30) as resp:
        dest.write_bytes(resp.read())
    info = inspect_image(dest)
    return PreparedImage(
        source_path=dest,
        original_path=dest,
        normalized_path=dest,
        info=info,
        normalized=True,
    )


def _placeholder(product: Product, service: ImageService) -> PreparedImage:
    placeholder_path = service.image_dir / "placeholders" / f"{product.id}.png"
    rgb = _product_rgb(product)
    source = write_solid_png(placeholder_path, width=800, height=1000, rgb=rgb)
    return service.prepare_local_image(source, asset_id=product.id)


def _product_rgb(product: Product) -> tuple[int, int, int]:
    colors = product.metadata.get("colors", [])
    if isinstance(colors, list):
        for color in colors:
            if isinstance(color, str) and color.lower() in COLOR_MAP:
                return COLOR_MAP[color.lower()]
    return (220, 220, 220)
