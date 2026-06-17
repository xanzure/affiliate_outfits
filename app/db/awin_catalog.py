from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path


CATALOG_SCHEMA = """
CREATE TABLE IF NOT EXISTS awin_products (
    aw_product_id       TEXT NOT NULL,
    merchant_id         TEXT NOT NULL,
    merchant_name       TEXT NOT NULL,
    product_name        TEXT NOT NULL,
    brand_name          TEXT,
    category            TEXT,
    merchant_category   TEXT,
    colour              TEXT,
    price_cents         INTEGER,
    currency            TEXT DEFAULT 'GBP',
    image_url           TEXT,
    affiliate_url       TEXT NOT NULL,
    product_url         TEXT,
    description         TEXT,
    in_stock            INTEGER DEFAULT 1,
    last_seen_at        TEXT NOT NULL,
    PRIMARY KEY (aw_product_id, merchant_id)
);

CREATE VIRTUAL TABLE IF NOT EXISTS awin_products_fts USING fts5(
    aw_product_id UNINDEXED,
    merchant_id   UNINDEXED,
    merchant_name,
    product_name,
    brand_name,
    category,
    colour,
    description,
    content='awin_products',
    content_rowid='rowid'
);

CREATE TRIGGER IF NOT EXISTS awin_products_ai AFTER INSERT ON awin_products BEGIN
    INSERT INTO awin_products_fts(rowid, aw_product_id, merchant_id, merchant_name, product_name, brand_name, category, colour, description)
    VALUES (new.rowid, new.aw_product_id, new.merchant_id, new.merchant_name, new.product_name, new.brand_name, new.category, new.colour, new.description);
END;

CREATE TRIGGER IF NOT EXISTS awin_products_au AFTER UPDATE ON awin_products BEGIN
    INSERT INTO awin_products_fts(awin_products_fts, rowid, aw_product_id, merchant_id, merchant_name, product_name, brand_name, category, colour, description)
    VALUES ('delete', old.rowid, old.aw_product_id, old.merchant_id, old.merchant_name, old.product_name, old.brand_name, old.category, old.colour, old.description);
    INSERT INTO awin_products_fts(rowid, aw_product_id, merchant_id, merchant_name, product_name, brand_name, category, colour, description)
    VALUES (new.rowid, new.aw_product_id, new.merchant_id, new.merchant_name, new.product_name, new.brand_name, new.category, new.colour, new.description);
END;
"""


@dataclass(frozen=True)
class CatalogProduct:
    aw_product_id: str
    merchant_id: str
    merchant_name: str
    product_name: str
    brand_name: str | None
    category: str | None
    colour: str | None
    price_cents: int | None
    currency: str
    image_url: str | None
    affiliate_url: str
    product_url: str | None
    in_stock: bool


def connect_catalog(catalog_path: Path) -> sqlite3.Connection:
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(catalog_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(CATALOG_SCHEMA)
    conn.commit()
    return conn


def upsert_catalog_product(conn: sqlite3.Connection, row: dict) -> None:
    conn.execute(
        """
        INSERT INTO awin_products (
            aw_product_id, merchant_id, merchant_name, product_name, brand_name,
            category, merchant_category, colour, price_cents, currency,
            image_url, affiliate_url, product_url, description, in_stock, last_seen_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(aw_product_id, merchant_id) DO UPDATE SET
            product_name      = excluded.product_name,
            brand_name        = excluded.brand_name,
            category          = excluded.category,
            merchant_category = excluded.merchant_category,
            colour            = excluded.colour,
            price_cents       = excluded.price_cents,
            currency          = excluded.currency,
            image_url         = excluded.image_url,
            affiliate_url     = excluded.affiliate_url,
            product_url       = excluded.product_url,
            description       = excluded.description,
            in_stock          = excluded.in_stock,
            last_seen_at      = excluded.last_seen_at
        """,
        (
            row["aw_product_id"],
            row["merchant_id"],
            row["merchant_name"],
            row["product_name"],
            row.get("brand_name"),
            row.get("category"),
            row.get("merchant_category"),
            row.get("colour"),
            row.get("price_cents"),
            row.get("currency", "GBP"),
            row.get("image_url"),
            row["affiliate_url"],
            row.get("product_url"),
            row.get("description"),
            1 if row.get("in_stock", True) else 0,
            row["last_seen_at"],
        ),
    )


def search_catalog(
    conn: sqlite3.Connection,
    query: str,
    *,
    category: str | None = None,
    limit: int = 10,
) -> list[CatalogProduct]:
    fts_query = " OR ".join(f'"{term}"' for term in query.split() if term)
    if category:
        rows = conn.execute(
            """
            SELECT p.* FROM awin_products p
            JOIN awin_products_fts fts ON fts.rowid = p.rowid
            WHERE awin_products_fts MATCH ?
              AND p.in_stock = 1
              AND (p.category = ? OR p.merchant_category LIKE ?)
            ORDER BY rank
            LIMIT ?
            """,
            (fts_query, category, f"%{category}%", limit),
        ).fetchall()
        if not rows:
            rows = conn.execute(
                """
                SELECT p.* FROM awin_products p
                JOIN awin_products_fts fts ON fts.rowid = p.rowid
                WHERE awin_products_fts MATCH ? AND p.in_stock = 1
                ORDER BY rank LIMIT ?
                """,
                (fts_query, limit),
            ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT p.* FROM awin_products p
            JOIN awin_products_fts fts ON fts.rowid = p.rowid
            WHERE awin_products_fts MATCH ? AND p.in_stock = 1
            ORDER BY rank LIMIT ?
            """,
            (fts_query, limit),
        ).fetchall()

    return [
        CatalogProduct(
            aw_product_id=r["aw_product_id"],
            merchant_id=r["merchant_id"],
            merchant_name=r["merchant_name"],
            product_name=r["product_name"],
            brand_name=r["brand_name"],
            category=r["category"],
            colour=r["colour"],
            price_cents=r["price_cents"],
            currency=r["currency"] or "GBP",
            image_url=r["image_url"],
            affiliate_url=r["affiliate_url"],
            product_url=r["product_url"],
            in_stock=bool(r["in_stock"]),
        )
        for r in rows
    ]


def catalog_stats(conn: sqlite3.Connection) -> dict:
    total = conn.execute("SELECT COUNT(*) FROM awin_products").fetchone()[0]
    merchants = conn.execute("SELECT COUNT(DISTINCT merchant_id) FROM awin_products").fetchone()[0]
    in_stock = conn.execute("SELECT COUNT(*) FROM awin_products WHERE in_stock = 1").fetchone()[0]
    return {"total_products": total, "merchants": merchants, "in_stock": in_stock}
