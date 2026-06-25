"""Deterministic near-match cache gate.

Before paying to search for a product, check whether a cached (already-sourced,
image-ready) product is a close-enough match: same garment zone, same colour
family, and overlapping garment-type words. "Cream" and "ivory" are the same
family, so a near-identical sweater is reused instead of re-sourced; "black" is
a different family, so it still searches fresh.

stdlib only — colour families + token overlap, no embeddings.
"""
from __future__ import annotations

import re
import sqlite3

from app.collage.export import _resolve_zone
from app.db.models import Product
from app.db.products import list_products

# Colour word → coarse family. Each word appears once; ambiguous words resolved
# to their most common fashion meaning (khaki→brown, rust→red, olive→green).
_COLOR_FAMILY: dict[str, str] = {
    # light / white
    "white": "light", "ivory": "light", "cream": "light", "ecru": "light",
    "eggshell": "light", "offwhite": "light", "vanilla": "light", "bone": "light",
    "chalk": "light", "oat": "light", "oatmeal": "light", "alabaster": "light",
    # black
    "black": "black", "jet": "black", "onyx": "black", "noir": "black",
    # grey
    "grey": "grey", "gray": "grey", "charcoal": "grey", "slate": "grey",
    "heather": "grey", "silver": "grey", "ash": "grey", "graphite": "grey",
    # brown / tan
    "brown": "brown", "chocolate": "brown", "espresso": "brown", "coffee": "brown",
    "mocha": "brown", "tan": "brown", "camel": "brown", "khaki": "brown",
    "taupe": "brown", "beige": "brown", "sand": "brown", "cognac": "brown",
    "caramel": "brown", "chestnut": "brown", "walnut": "brown", "tobacco": "brown",
    # blue
    "blue": "blue", "navy": "blue", "cobalt": "blue", "denim": "blue",
    "indigo": "blue", "sky": "blue", "teal": "blue", "azure": "blue",
    # green
    "green": "green", "olive": "green", "sage": "green", "emerald": "green",
    "forest": "green", "mint": "green", "moss": "green", "hunter": "green",
    # red
    "red": "red", "burgundy": "red", "maroon": "red", "wine": "red",
    "crimson": "red", "rust": "red", "brick": "red", "scarlet": "red",
    # pink
    "pink": "pink", "blush": "pink", "rose": "pink", "fuchsia": "pink",
    "magenta": "pink", "coral": "pink", "salmon": "pink",
    # warm (yellow/orange/gold)
    "yellow": "warm", "mustard": "warm", "gold": "warm", "ochre": "warm",
    "orange": "warm", "amber": "warm", "honey": "warm",
    # purple
    "purple": "purple", "lavender": "purple", "lilac": "purple",
    "plum": "purple", "violet": "purple", "mauve": "purple",
}

_STOP = {
    "the", "and", "with", "for", "women", "womens", "men", "mens", "fit",
    "fitted", "size", "new", "set", "pair", "style", "classic", "premium",
}


def color_family(text: str | None) -> str | None:
    for w in re.findall(r"[a-z]+", (text or "").lower()):
        if w in _COLOR_FAMILY:
            return _COLOR_FAMILY[w]
    return None


def extract_color_word(text: str | None) -> str | None:
    """First recognised colour word in text (e.g. 'cream'), or None."""
    for w in re.findall(r"[a-z]+", (text or "").lower()):
        if w in _COLOR_FAMILY:
            return w
    return None


def _tokens(text: str | None) -> set[str]:
    return {w for w in re.findall(r"[a-z]+", (text or "").lower())
            if len(w) > 2 and w not in _STOP and w not in _COLOR_FAMILY}


def match_score(
    a_zone: str, a_color: str | None, a_desc: str,
    b_zone: str, b_color: str | None, b_desc: str,
) -> float | None:
    """Score how close two garments are, or None if not a reuse-worthy match.

    Rule: same zone required. If both colours are known they must share a family.
    Token overlap must reach the threshold — 1 when colours confirm-match, 2 when
    colour can't be confirmed (stay conservative).
    """
    if a_zone != b_zone:
        return None
    fa, fb = color_family(a_color), color_family(b_color)
    same_color = bool(fa and fb and fa == fb)
    # If either colour is known, we must positively confirm they're the same
    # family — never reuse when a shade can't be verified (that's the whole point
    # of the gate). Only when BOTH colours are unknown do we fall back to a
    # stricter garment-type match.
    if (fa or fb) and not same_color:
        return None
    overlap = len(_tokens(a_desc) & _tokens(b_desc))
    if overlap < (1 if same_color else 2):
        return None
    return float(overlap + (1 if same_color else 0))


def find_cached_match(
    conn: sqlite3.Connection,
    *,
    zone: str,
    color: str | None,
    descriptor: str,
) -> Product | None:
    """Return the best cached product that's a near-match, or None to search."""
    best: Product | None = None
    best_score = 0.0
    for p in list_products(conn):
        if "supabase.co/storage" not in (p.image_url or ""):
            continue  # only image-ready cached products
        p_color = (p.metadata or {}).get("color") or p.name
        p_desc = f"{p.category or ''} {p.name or ''}"
        score = match_score(zone, color, descriptor, _resolve_zone(p.category), p_color, p_desc)
        if score is not None and score > best_score:
            best_score, best = score, p
    return best


def _demo() -> None:
    # cream sweater reuses an ivory one (same family + shared garment word)
    assert match_score("top", "cream", "ribbed knit turtleneck sweater",
                       "top", "ivory", "fine knit turtleneck") is not None
    # different colour family → no reuse
    assert match_score("top", "cream", "knit turtleneck",
                       "top", "black", "knit turtleneck") is None
    # different zone → no reuse
    assert match_score("top", "cream", "knit turtleneck",
                       "bottom", "cream", "knit trousers") is None
    # same family but unrelated garment → no reuse (no token overlap)
    assert match_score("top", "cream", "cropped halter tank",
                       "top", "ivory", "oversized cardigan blazer") is None
    # target colour known, cached colour unknown → no reuse (can't confirm shade)
    assert match_score("bottom", "chocolate", "wide leg trousers",
                       "bottom", None, "wide leg trousers") is None
    print("product_cache self-check OK")


if __name__ == "__main__":
    _demo()
