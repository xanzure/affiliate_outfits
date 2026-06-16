from __future__ import annotations

from pathlib import Path


class SupabaseAssetStorage:
    """Uploads processed images to Supabase Storage and returns public URLs."""

    PRODUCT_BUCKET = "product-images"
    COLLAGE_BUCKET = "collages"

    def __init__(self, url: str, service_role_key: str) -> None:
        from supabase import create_client
        self._sb = create_client(url, service_role_key)
        self._buckets_ensured: set[str] = set()

    def _ensure_bucket(self, bucket: str) -> None:
        if bucket in self._buckets_ensured:
            return
        existing = [b.name for b in self._sb.storage.list_buckets()]
        if bucket not in existing:
            self._sb.storage.create_bucket(bucket, options={"public": True})
        self._buckets_ensured.add(bucket)

    def upload_product_image(self, product_id: str, png_path: Path) -> str:
        self._ensure_bucket(self.PRODUCT_BUCKET)
        dest = f"products/{product_id}.png"
        with open(png_path, "rb") as f:
            self._sb.storage.from_(self.PRODUCT_BUCKET).upload(
                dest, f,
                file_options={"content-type": "image/png", "upsert": "true"},
            )
        return self._sb.storage.from_(self.PRODUCT_BUCKET).get_public_url(dest)

    def upload_collage(self, collage_id: str, png_path: Path) -> str:
        self._ensure_bucket(self.COLLAGE_BUCKET)
        dest = f"collages/{collage_id}.png"
        with open(png_path, "rb") as f:
            self._sb.storage.from_(self.COLLAGE_BUCKET).upload(
                dest, f,
                file_options={"content-type": "image/png", "upsert": "true"},
            )
        return self._sb.storage.from_(self.COLLAGE_BUCKET).get_public_url(dest)


def asset_storage_from_env() -> SupabaseAssetStorage | None:
    import os
    from pathlib import Path as P

    env: dict[str, str] = {}
    env_path = P(__file__).resolve().parents[2] / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")

    url = os.environ.get("SUPABASE_URL") or env.get("SUPABASE_URL") or ""
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or env.get("SUPABASE_SERVICE_ROLE_KEY") or ""
    if not url or not key:
        return None
    return SupabaseAssetStorage(url, key)
