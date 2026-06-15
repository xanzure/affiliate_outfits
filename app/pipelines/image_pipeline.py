from __future__ import annotations

import sqlite3
from pathlib import Path

from app.collage.image_utils import write_solid_png
from app.db.models import Product
from app.db.products import update_product_local_image_path
from app.services.image_service import ImageService, PreparedImage


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
) -> list[PreparedImage]:
    service = image_service or ImageService()
    prepared_images: list[PreparedImage] = []

    for product in products:
        source_path = _source_or_placeholder(product, service)
        prepared = service.prepare_local_image(source_path, asset_id=product.id)
        update_product_local_image_path(conn, product.id, str(prepared.normalized_path))
        prepared_images.append(prepared)

    return prepared_images


def _source_or_placeholder(product: Product, service: ImageService) -> Path:
    if product.local_image_path:
        path = Path(product.local_image_path)
        if path.exists():
            return path

    if product.image_url:
        try:
            return service.download_image(product.image_url, asset_id=product.id)
        except Exception:
            pass

    placeholder_path = service.image_dir / "placeholders" / f"{product.id}.png"
    rgb = _product_rgb(product)
    return write_solid_png(placeholder_path, width=800, height=1000, rgb=rgb)


def _product_rgb(product: Product) -> tuple[int, int, int]:
    colors = product.metadata.get("colors", [])
    if isinstance(colors, list):
        for color in colors:
            if isinstance(color, str) and color.lower() in COLOR_MAP:
                return COLOR_MAP[color.lower()]
    return (220, 220, 220)
