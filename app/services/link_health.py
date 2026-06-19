from __future__ import annotations

from urllib.request import Request, urlopen

from app.db._helpers import utc_now

_UA = "Mozilla/5.0 (compatible; VanceArchivesBot/1.0)"


def url_is_alive(url: str, timeout: int = 10) -> bool:
    if not url or not url.startswith(("http://", "https://")):
        return False
    for method in ("HEAD", "GET"):
        try:
            req = Request(url, method=method, headers={"User-Agent": _UA})
            with urlopen(req, timeout=timeout) as resp:
                if resp.status < 400:
                    return True
        except Exception:  # noqa: BLE001
            continue
    return False


def check_post_links(post_metadata: dict) -> dict:
    """Check the product/affiliate links attached to a post's metadata."""
    urls = post_metadata.get("product_urls") or post_metadata.get("affiliate_urls") or []
    urls = [u for u in urls if isinstance(u, str)]
    dead = [u for u in urls if not url_is_alive(u)]
    return {"checked_at": utc_now(), "total": len(urls), "dead": dead}
