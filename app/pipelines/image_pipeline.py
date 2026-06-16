from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from app.collage.image_utils import write_solid_png
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
    prepared_images: list[PreparedImage] = []

    for product in products:
        prepared = _prepare_one(product, service)
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


def _prepare_one(product: Product, service: ImageService) -> PreparedImage:
    # Already processed locally
    if product.local_image_path:
        path = Path(product.local_image_path)
        if path.exists():
            return service.prepare_local_image(path, asset_id=product.id)

    # Public image URL → Runflow model removal (falls back to rembg)
    if product.image_url:
        try:
            return service.process_from_url(product.image_url, asset_id=product.id)
        except Exception:
            logger.warning("process_from_url failed for %s, using placeholder", product.id)

    return _placeholder(product, service)


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
