from __future__ import annotations

import sqlite3

from app.db._helpers import dumps_json, loads_json, new_id, require_row, utc_now
from app.db.models import JsonDict, Product


def _to_product(row: sqlite3.Row) -> Product:
    return Product(
        id=row["id"],
        retailer=row["retailer"],
        name=row["name"],
        category=row["category"],
        url=row["url"],
        affiliate_url=row["affiliate_url"],
        image_url=row["image_url"],
        local_image_path=row["local_image_path"],
        price_cents=row["price_cents"],
        currency=row["currency"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        metadata=loads_json(row["metadata_json"], {}),
    )


def upsert_product(
    conn: sqlite3.Connection,
    *,
    retailer: str,
    name: str,
    url: str,
    category: str | None = None,
    affiliate_url: str | None = None,
    image_url: str | None = None,
    local_image_path: str | None = None,
    price_cents: int | None = None,
    currency: str = "USD",
    metadata: JsonDict | None = None,
    product_id: str | None = None,
) -> Product:
    now = utc_now()
    product_id = product_id or new_id("product")
    conn.execute(
        """
        INSERT INTO products (
            id, retailer, name, category, url, affiliate_url, image_url,
            local_image_path, price_cents, currency, created_at, updated_at,
            metadata_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(retailer, url) DO UPDATE SET
            name = excluded.name,
            category = excluded.category,
            affiliate_url = excluded.affiliate_url,
            image_url = excluded.image_url,
            local_image_path = excluded.local_image_path,
            price_cents = excluded.price_cents,
            currency = excluded.currency,
            updated_at = excluded.updated_at,
            metadata_json = excluded.metadata_json
        """,
        (
            product_id,
            retailer,
            name,
            category,
            url,
            affiliate_url,
            image_url,
            local_image_path,
            price_cents,
            currency,
            now,
            now,
            dumps_json(metadata or {}),
        ),
    )
    return get_product_by_retailer_url(conn, retailer, url)


def get_product(conn: sqlite3.Connection, product_id: str) -> Product:
    row = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    return _to_product(require_row(row, "product", product_id))


def get_product_by_retailer_url(conn: sqlite3.Connection, retailer: str, url: str) -> Product:
    row = conn.execute(
        "SELECT * FROM products WHERE retailer = ? AND url = ?",
        (retailer, url),
    ).fetchone()
    return _to_product(require_row(row, "product", f"{retailer}:{url}"))


def list_products(conn: sqlite3.Connection, *, category: str | None = None) -> list[Product]:
    if category:
        rows = conn.execute(
            "SELECT * FROM products WHERE category = ? ORDER BY retailer, name",
            (category,),
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM products ORDER BY retailer, name").fetchall()
    return [_to_product(row) for row in rows]


def update_product_local_image_path(
    conn: sqlite3.Connection,
    product_id: str,
    local_image_path: str,
) -> Product:
    now = utc_now()
    conn.execute(
        """
        UPDATE products
        SET local_image_path = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (local_image_path, now, product_id),
    )
    return get_product(conn, product_id)


def update_product_image_url(
    conn: sqlite3.Connection,
    product_id: str,
    image_url: str,
) -> Product:
    now = utc_now()
    conn.execute(
        """
        UPDATE products
        SET image_url = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (image_url, now, product_id),
    )
    return get_product(conn, product_id)
