"""HTML/CSS collage renderer (Route 1).

Replaces the PIL geometry engine with declarative templates rendered by a
headless browser. Each template is a list of SLOTS (percentage positions on the
canvas); products are assigned to slots by their resolved zone. A human designs
each template once, so output reads as composed rather than computed.

Templates are plain data — adding one is a dict, not code.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from app.collage.export import _resolve_zone  # reuse the category→zone classifier

if TYPE_CHECKING:
    from app.agents.collage.style_agent import BatchVisualStyle

CANVAS_W = 1080
CANVAS_H = 1350
FOOTER_H = 200
STAGE_H = CANVAS_H - FOOTER_H  # area the outfit occupies

_FONT_STACK = {
    "serif": "'Cormorant Garamond', serif",
    "sans":  "'Jost', sans-serif",
}


@dataclass(frozen=True)
class Slot:
    """A placement box as fractions of the stage (top-left anchored)."""
    role: str          # which zone fills it
    left: float        # % of canvas width
    top: float         # % of stage height
    width: float       # % of canvas width
    height: float      # % of stage height
    rot: float = 0.0   # degrees
    z: int = 1


@dataclass(frozen=True)
class Template:
    name: str
    needs: frozenset[str]       # zones this template expects to fill
    slots: list[Slot] = field(default_factory=list)


# ── Templates ───────────────────────────────────────────────────────────────
# Zones (from _resolve_zone): outerwear/top/bottom/dress/bag/shoe/accessory.
# Each template is a fixed composition of slots; the outfit generator is forced
# to source exactly one product per slot role (see app/agents/outfit/curator.py).
#
# Slot positions are shared "anchors" so every template reads from the same
# visual grammar (spine down the middle, accessories on the flanks, shoe kicked
# off-axis). Distinct compositions still produce distinct layouts.

# spine — top + bottom share centre x=50 and stay perfectly straight (rot=0)
_TOP    = dict(left=28, top=9,  width=44, height=38, rot=0, z=3)
_BOTTOM = dict(left=30, top=39, width=40, height=50, rot=0, z=2)
_DRESS  = dict(left=30, top=9,  width=40, height=60, rot=0, z=2)
# shoe — kicked onto a flank, mid-low (NOT at the bottom), tilted
_SHOE_R = dict(left=73, top=58, width=25, height=20, rot=11,  z=4)
_SHOE_L = dict(left=2,  top=58, width=25, height=20, rot=-11, z=4)
# accessories on the flanks (top-left / top-right), tilted
_ACC_TL = dict(left=5,  top=13, width=21, height=18, rot=-9, z=1)
_ACC_TR = dict(left=74, top=12, width=20, height=17, rot=8,  z=1)
# bag (mid flank) — a touch bigger, tilted
_BAG_R  = dict(left=73, top=37, width=24, height=21, rot=5,  z=1)
_BAG_L  = dict(left=3,  top=37, width=24, height=21, rot=-5, z=1)
# outerwear side column — much larger; coats need real presence
_OUTER_L = dict(left=1,  top=13, width=33, height=58, rot=-3, z=1)


def _S(role: str, pos: dict) -> Slot:
    return Slot(role=role, **pos)


_TEMPLATES = [
    Template("classic_5", frozenset({"top", "bottom", "shoe", "bag", "accessory"}), [
        _S("accessory", _ACC_TL), _S("top", _TOP), _S("bag", _BAG_R),
        _S("bottom", _BOTTOM), _S("shoe", _SHOE_L)]),
    Template("layered_5", frozenset({"top", "bottom", "outerwear", "shoe", "bag"}), [
        _S("outerwear", _OUTER_L), _S("top", _TOP), _S("bag", _BAG_R),
        _S("bottom", _BOTTOM), _S("shoe", _SHOE_R)]),
    Template("dress_4", frozenset({"dress", "shoe", "bag", "accessory"}), [
        _S("accessory", _ACC_TL), _S("dress", _DRESS), _S("bag", _BAG_R),
        _S("shoe", _SHOE_L)]),
    Template("dress_layered", frozenset({"dress", "outerwear", "shoe", "bag"}), [
        _S("outerwear", _OUTER_L), _S("dress", _DRESS), _S("bag", _BAG_R),
        _S("shoe", _SHOE_R)]),
    Template("minimal_4", frozenset({"top", "bottom", "shoe", "bag"}), [
        _S("top", _TOP), _S("bag", _BAG_R), _S("bottom", _BOTTOM),
        _S("shoe", _SHOE_L)]),
    Template("statement_6", frozenset({"top", "bottom", "outerwear", "shoe", "bag", "accessory"}), [
        _S("outerwear", _OUTER_L), _S("top", _TOP), _S("accessory", _ACC_TR),
        _S("bag", _BAG_R), _S("bottom", _BOTTOM), _S("shoe", _SHOE_R)]),
    Template("accessorized_5", frozenset({"top", "bottom", "shoe", "accessory"}), [
        _S("accessory", _ACC_TL), _S("top", _TOP), _S("accessory", _ACC_TR),
        _S("bottom", _BOTTOM), _S("shoe", _SHOE_R)]),
    Template("dress_minimal", frozenset({"dress", "shoe", "accessory"}), [
        _S("dress", _DRESS), _S("accessory", _ACC_TR), _S("shoe", _SHOE_L)]),
    Template("layered_acc", frozenset({"top", "bottom", "outerwear", "shoe", "accessory"}), [
        _S("outerwear", _OUTER_L), _S("top", _TOP), _S("accessory", _ACC_TR),
        _S("bottom", _BOTTOM), _S("shoe", _SHOE_R)]),
    Template("dress_statement", frozenset({"dress", "outerwear", "shoe", "bag", "accessory"}), [
        _S("outerwear", _OUTER_L), _S("dress", _DRESS), _S("accessory", _ACC_TR),
        _S("bag", _BAG_R), _S("shoe", _SHOE_R)]),
]

_BY_NAME = {t.name: t for t in _TEMPLATES}

# Human-readable requirement per zone, for the generation prompt.
_ZONE_LABEL = {
    "top":       "top (shirt, blouse, tee, sweater, or knit)",
    "bottom":    "bottom (trousers, jeans, skirt, or shorts)",
    "dress":     "dress or jumpsuit",
    "outerwear": "outerwear (jacket, coat, blazer, or cardigan)",
    "shoe":      "shoes",
    "bag":       "bag or purse",
    "accessory": "accessory (hat, jewelry, belt, scarf, or sunglasses)",
}


# ── Type-locked sizes ───────────────────────────────────────────────────────
# Size is a property of the ITEM TYPE, not the template slot. The template only
# decides WHERE a piece goes (the slot's centre); this decides HOW BIG it is.
# (width % of canvas, height % of stage). A coat is always large, earrings always
# small, regardless of which slot they land in.
_TYPE_SIZE: dict[str, tuple[float, float]] = {
    "outerwear": (30, 50),   # coats/blazers — large
    "top":       (40, 40),
    "bottom":    (35, 52),
    "dress":     (40, 64),
    "shoe":      (17, 19),
    "bag":       (19, 20),
    "hat":       (19, 17),
    "scarf":     (17, 16),
    "belt":      (16, 12),
    "sunglasses": (14, 9),
    "earrings":  (10, 11),   # jewelry — small
    "accessory": (15, 14),   # default accessory
}


def _size_class(category: str | None, zone: str) -> str:
    """Resolve an item to a size bucket. Garment zones map 1:1; accessories split
    into hat / jewelry / belt / scarf / sunglasses so each gets its own size."""
    if zone != "accessory":
        return zone
    c = (category or "").lower()
    if "hat" in c or "cap" in c:
        return "hat"
    if any(k in c for k in ("earring", "jewelry", "necklace", "ring", "bracelet", "watch")):
        return "earrings"
    if "sunglass" in c or "glasses" in c:
        return "sunglasses"
    if "belt" in c:
        return "belt"
    if "scarf" in c:
        return "scarf"
    return "accessory"


def list_templates() -> list[Template]:
    return list(_TEMPLATES)


def get_template(name: str) -> Template | None:
    return _BY_NAME.get(name)


def template_zones(name: str) -> list[str]:
    """Ordered list of zones a template's slots require."""
    t = _BY_NAME.get(name)
    return [s.role for s in t.slots] if t else []


def template_requirement_labels(name: str) -> list[str]:
    return [_ZONE_LABEL.get(z, z) for z in template_zones(name)]


def _pick_template(zones: list[str]) -> Template:
    present = set(zones)
    for t in _TEMPLATES:
        if t.needs <= present:
            return t
    return _TEMPLATES[0]  # fallback


def _assign(zones: list[str], template: Template) -> dict[int, Slot]:
    """Map product index → slot. Greedy: each slot takes the first unused
    product whose zone matches its role, then leftovers fill leftover slots."""
    used: set[int] = set()
    out: dict[int, Slot] = {}
    for slot in template.slots:
        for i, z in enumerate(zones):
            if i in used:
                continue
            if z == slot.role:
                out[i] = slot
                used.add(i)
                break
    free_slots = [s for s in template.slots if s not in out.values()]
    for i in range(len(zones)):
        if i in used or not free_slots:
            continue
        out[i] = free_slots.pop(0)
        used.add(i)
    return out


def build_html(
    image_urls: list[str],
    zones: list[str],
    categories: list[str | None],
    *,
    concept_name: str,
    outfit_number: int,
    bg_hex: str,
    accent_hex: str,
    font_style: str,
    template_name: str | None = None,
) -> tuple[str, dict]:
    """Return (html, manifest). Manifest carries each product's box in canvas
    pixels for the website's shoppable overlay."""
    template = (template_name and get_template(template_name)) or _pick_template(zones)
    assignment = _assign(zones, template)
    font = _FONT_STACK.get(font_style, _FONT_STACK["sans"])

    pieces, divs = [], []
    for i, url in enumerate(image_urls):
        slot = assignment.get(i)
        if slot is None:
            continue
        # Size comes from the item TYPE; the slot only provides the anchor (its
        # centre). So a coat is always large and earrings always small, wherever
        # the template places them.
        w, h = _TYPE_SIZE.get(_size_class(categories[i], zones[i]), _TYPE_SIZE["accessory"])
        cx = slot.left + slot.width / 2
        cy = slot.top + slot.height / 2
        left = round(cx - w / 2, 2)
        top = round(cy - h / 2, 2)
        divs.append(
            f'<div class="piece" style="left:{left}%;top:{top}%;'
            f'width:{w}%;height:{h}%;'
            f'transform:rotate({slot.rot}deg);z-index:{slot.z};">'
            f'<img src="{url}"></div>'
        )
        pieces.append({
            "index": i,
            "x": int(left / 100 * CANVAS_W),
            "y": int(top / 100 * STAGE_H),
            "width": int(w / 100 * CANVAS_W),
            "height": int(h / 100 * STAGE_H),
            "rotation": slot.rot,
            "z_index": slot.z,
        })

    html = _PAGE.format(
        bg=bg_hex, accent=accent_hex, font=font,
        canvas_w=CANVAS_W, canvas_h=CANVAS_H, footer_h=FOOTER_H,
        pieces="".join(divs),
        title=concept_name.upper(),
        num=str(outfit_number).zfill(3),
    )
    manifest = {"canvas": {"width": CANVAS_W, "height": CANVAS_H}, "pieces": pieces}
    return html, manifest


def render_collage(
    image_urls: list[str],
    categories: list[str | None],
    output_path: Path,
    *,
    concept_name: str = "",
    outfit_number: int = 1,
    style: "BatchVisualStyle | None" = None,
    template_name: str | None = None,
) -> dict:
    """Render to PNG via headless Chromium; return the manifest."""
    from playwright.sync_api import sync_playwright

    zones = [_resolve_zone(c) for c in categories]
    html, manifest = build_html(
        image_urls, zones, categories,
        concept_name=concept_name, outfit_number=outfit_number,
        bg_hex=style.background_hex if style else "#EFE9DF",
        accent_hex=style.accent_hex if style else "#2A2018",
        font_style=style.font_style if style else "serif",
        template_name=template_name,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(
            viewport={"width": CANVAS_W, "height": CANVAS_H}, device_scale_factor=2,
        )
        page.set_content(html, wait_until="networkidle")
        page.wait_for_timeout(400)  # font settle
        page.screenshot(path=str(output_path))
        browser.close()
    return manifest


_PAGE = """<!DOCTYPE html><html><head><meta charset="utf-8">
<style>
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@500;600&family=Jost:wght@300;400&display=swap');
*{{margin:0;padding:0;box-sizing:border-box;}}
body{{width:{canvas_w}px;height:{canvas_h}px;background:{bg};position:relative;overflow:hidden;font-family:'Jost',sans-serif;}}
.stage{{position:absolute;left:0;right:0;top:0;bottom:{footer_h}px;}}
.piece{{position:absolute;}}
.piece img{{width:100%;height:100%;object-fit:contain;filter:drop-shadow(0 20px 26px rgba(60,45,30,0.22));}}
.footer{{position:absolute;left:0;right:0;bottom:0;height:{footer_h}px;padding:0 70px;display:flex;align-items:center;justify-content:space-between;}}
.rule{{position:absolute;left:60px;right:60px;top:0;height:1px;background:rgba(40,30,20,0.18);}}
.title{{font-family:{font};font-weight:600;font-size:58px;letter-spacing:0.02em;color:{accent};text-transform:uppercase;}}
.num{{font-family:'Jost',sans-serif;font-weight:300;font-size:30px;letter-spacing:0.3em;color:#9A8A74;}}
.kicker{{font-family:'Jost',sans-serif;font-weight:400;font-size:15px;letter-spacing:0.42em;color:#B08D57;text-transform:uppercase;margin-bottom:8px;}}
</style></head><body>
<div class="stage">{pieces}</div>
<div class="footer"><div class="rule"></div>
<div><div class="kicker">The Edit</div><div class="title">{title}</div></div>
<div class="num">{num}</div></div>
</body></html>"""


if __name__ == "__main__":
    # Self-check: every slot in every template has a unique, on-canvas box.
    for t in _TEMPLATES:
        for s in t.slots:
            assert 0 <= s.left <= 100 and 0 <= s.top <= 100, (t.name, s.role)
            assert s.left + s.width <= 101 and s.top + s.height <= 101, (t.name, s.role)
    print("templates ok:", [t.name for t in _TEMPLATES])
