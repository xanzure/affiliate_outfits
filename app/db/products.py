from __future__ import annotations

import sqlite3

from app.db._helpers import dumps_json, loads_json, new_id, require_row, utc_now
from app.db.models import JsonDict, Product


def _row_get(row: object, key: str, default: object = None) -> object:
    """Read a column from a Row/dict that may predate a migration."""
    try:
        value = row[key]  # type: ignore[index]
    except (KeyError, IndexError):
        return default
    return default if value is None else value


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
        archived_at=_row_get(row, "archived_at"),
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


def list_products(
    conn: sqlite3.Connection,
    *,
    category: str | None = None,
    include_archived: bool = False,
) -> list[Product]:
    """List products. Archived (soft-deleted) products are excluded by default so
    the cache and curator never reuse them; the Wardrobe view can opt them in."""
    clauses, params = [], []
    if category:
        clauses.append("category = ?")
        params.append(category)
    if not include_archived:
        clauses.append("archived_at IS NULL")
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = conn.execute(
        f"SELECT * FROM products {where} ORDER BY retailer, name", tuple(params)
    ).fetchall()
    return [_to_product(row) for row in rows]


def archive_product(conn: sqlite3.Connection, product_id: str) -> None:
    """Soft-delete: remove from the cache so no new outfit uses it, but keep the
    row + image so existing outfits that reference it don't break."""
    conn.execute(
        "UPDATE products SET archived_at = ?, updated_at = ? WHERE id = ?",
        (utc_now(), utc_now(), product_id),
    )


def unarchive_product(conn: sqlite3.Connection, product_id: str) -> None:
    conn.execute(
        "UPDATE products SET archived_at = NULL, updated_at = ? WHERE id = ?",
        (utc_now(), product_id),
    )


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
