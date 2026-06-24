from __future__ import annotations

import hashlib
import random
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from app.collage.image_utils import inspect_image, write_solid_png
from app.collage.layout import Canvas, CollageLayout, Placement, layout_to_dict

if TYPE_CHECKING:
    from app.agents.collage.style_agent import BatchVisualStyle


# ── canvas ─────────────────────────────────────────────────────────────────────
CANVAS_W = 1080
CANVAS_H = 1350
TEXT_STRIP_H = 200
CONTENT_H = CANVAS_H - TEXT_STRIP_H  # 1150

# ── fonts ──────────────────────────────────────────────────────────────────────
_FONTS: dict[str, dict[str, str]] = {
    "sans": {
        "heading": "/usr/share/fonts/truetype/lato/Lato-Black.ttf",
        "sub":     "/usr/share/fonts/truetype/lato/Lato-Light.ttf",
    },
    "serif": {
        "heading": "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
        "sub":     "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf",
    },
}

# ── visual hierarchy ────────────────────────────────────────────────────────────
# Items are arranged in two columns: an "apparel" column (garments stacked
# head-to-toe) and an "accessories" column (bag / shoe / jewelry). Each item is
# scaled to FIT a box (preserving aspect ratio) whose height is proportional to
# the item's visual weight — so a dress reads large, earrings read small, and
# nothing balloons just because the source image happens to be wide.

# Relative vertical weight of each zone within its column
_TIER_WEIGHT: dict[str, float] = {
    "outerwear": 3.5,
    "dress":     3.0,
    "top":       2.5,
    "bottom":    2.5,
    "bag":       1.7,
    "shoe":      0.8,
    "accessory": 1.0,
}

# Max width an item may occupy, as a fraction of its column width
_TIER_MAX_WIDTH: dict[str, float] = {
    "outerwear": 1.00,
    "dress":     0.94,
    "top":       0.90,
    "bottom":    0.90,
    "bag":       0.95,
    "shoe":      0.66,
    "accessory": 0.58,
}

# Which column each zone belongs to
_APPAREL_ZONES = {"outerwear", "top", "bottom", "dress"}
_EXTRA_ZONES = {"bag", "shoe", "accessory"}

# Stacking order within a column (head-to-toe / bag-to-shoe)
_APPAREL_ORDER = {"outerwear": 0, "top": 1, "dress": 1, "bottom": 2}
_EXTRA_ORDER = {"bag": 0, "accessory": 1, "shoe": 2}

# How to normalise category strings → zone keys
_CATEGORY_MAP: dict[str, str] = {
    # outerwear
    "coat": "outerwear", "jacket": "outerwear", "blazer": "outerwear",
    "outerwear": "outerwear", "trench": "outerwear", "cardigan": "outerwear",
    "vest": "outerwear", "puffer": "outerwear", "parka": "outerwear",
    # tops
    "top": "top", "shirt": "top", "blouse": "top", "tee": "top",
    "t-shirt": "top", "sweater": "top", "knit": "top", "turtleneck": "top",
    "tank": "top", "crop": "top", "polo": "top",
    # bottoms
    "bottom": "bottom", "pants": "bottom", "trousers": "bottom",
    "jeans": "bottom", "skirt": "bottom", "shorts": "bottom",
    "leggings": "bottom", "denim": "bottom", "slacks": "bottom",
    # dress/jumpsuit
    "dress": "dress", "jumpsuit": "dress", "romper": "dress",
    "mini": "dress", "maxi": "dress", "bodysuit": "dress",
    # shoes
    "shoe": "shoe", "shoes": "shoe", "boot": "shoe", "boots": "shoe",
    "sneaker": "shoe", "sneakers": "shoe", "loafer": "shoe", "loafers": "shoe",
    "sandal": "shoe", "sandals": "shoe", "heel": "shoe", "heels": "shoe",
    "mule": "shoe", "flat": "shoe", "oxford": "shoe",
    # bags
    "bag": "bag", "purse": "bag", "tote": "bag", "clutch": "bag",
    "backpack": "bag", "crossbody": "bag", "handbag": "bag", "satchel": "bag",
    # accessories
    "accessory": "accessory", "accessories": "accessory", "belt": "accessory",
    "scarf": "accessory", "hat": "accessory", "cap": "accessory",
    "jewelry": "accessory", "necklace": "accessory", "ring": "accessory",
    "bracelet": "accessory", "earring": "accessory", "earrings": "accessory",
    "sunglasses": "accessory", "glasses": "accessory", "watch": "accessory",
    "sock": "accessory", "socks": "accessory",
}

@dataclass(frozen=True)
class CollageExportResult:
    image_path: Path
    layout: CollageLayout
    manifest: dict


def export_collage(
    image_paths: list[Path],
    output_path: Path,
    *,
    canvas: Canvas | None = None,
    style: "BatchVisualStyle | None" = None,
    concept_name: str = "",
    outfit_number: int = 1,
    categories: list[str | None] | None = None,
    seed: str = "",
) -> CollageExportResult:
    if not image_paths:
        raise ValueError("at least one image is required to export a collage")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas = canvas or Canvas()

    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        placeholder = _export_placeholder_collage(image_paths, output_path, canvas)
        dummy_bboxes = [(0, 0, 420, 580, 0.0)] * len(image_paths)
        return CollageExportResult(
            image_path=placeholder,
            layout=_build_layout_from_bboxes(dummy_bboxes, canvas),
            manifest=_build_manifest_from_bboxes(image_paths, dummy_bboxes),
        )

    bg_rgb    = _hex_to_rgb(style.background_hex if style else "#F0ECE4")
    accent_rgb = _hex_to_rgb(style.accent_hex    if style else "#1A1A1A")
    font_style = style.font_style                if style else "sans"

    collage = Image.new("RGBA", (CANVAS_W, CANVAS_H), (*bg_rgb, 255))
    rng = random.Random(_rng_seed(seed or output_path.name))

    placements = _compute_layout(
        image_paths,
        categories or [None] * len(image_paths),
        rng,
    )

    # (canvas_x, canvas_y, render_w, render_h, rotation) for web layout
    placed_bboxes: list[tuple[int, int, int, int, float]] = []

    for img_path, (cx, cy, box_w, box_h, rotation) in zip(image_paths, placements):
        with Image.open(img_path) as img:
            img = img.convert("RGBA")
            img = _trim_alpha(img)
            # Scale to FIT the box, preserving aspect ratio (no distortion,
            # no ballooning — whichever dimension binds first wins)
            scale = min(box_w / img.width, box_h / img.height)
            new_w = max(1, int(round(img.width * scale)))
            new_h = max(1, int(round(img.height * scale)))
            img = img.resize((new_w, new_h), Image.LANCZOS)

            rotated = img.rotate(
                rotation, resample=Image.BICUBIC, expand=True,
                fillcolor=(0, 0, 0, 0),
            )
            paste_x = cx - rotated.width  // 2
            paste_y = cy - rotated.height // 2
            collage.paste(rotated, (paste_x, paste_y), rotated)
            # Store unrotated top-left + dimensions for the website layout
            placed_bboxes.append((cx - new_w // 2, cy - new_h // 2, new_w, new_h, rotation))

    _draw_text_strip(collage, concept_name, outfit_number, accent_rgb, font_style)
    collage.convert("RGB").save(output_path, format="PNG", optimize=False)

    layout = _build_layout_from_bboxes(placed_bboxes, canvas)
    manifest = _build_manifest_from_bboxes(image_paths, placed_bboxes)

    return CollageExportResult(
        image_path=output_path, layout=layout, manifest=manifest,
    )


# ── placement logic ────────────────────────────────────────────────────────────

# Layout geometry
_PAD = 50                 # outer margin
_ITEM_GAP = 22            # vertical gap between stacked items in a column
_SPINE_FRACTION = 0.50    # share of usable width for the central apparel+shoe spine
_FLANK_GAP = 18           # gap between the spine and a side flank
_APPAREL_ROT = 2.5        # max rotation (deg) for garments + shoes
_ACCESSORY_ROT = 6.0      # max rotation (deg) for accessories — slightly tilted

# Waist anchor: fraction of content height where tops meet bottoms
_WAIST_Y_FRAC = 0.40
# Target waist width as fraction of spine width
_WAIST_WIDTH_FRAC = 0.60


def _measure_edge_width(alpha: "np.ndarray", edge: str, sample_frac: float = 0.06) -> int:
    """Return avg pixel span (rightmost − leftmost non-transparent col) over edge rows."""
    try:
        import numpy as np
        h = alpha.shape[0]
        n = max(1, int(h * sample_frac))
        rows = alpha[-n:] if edge == "bottom" else alpha[:n]
        spans = []
        for row in rows:
            cols = np.where(row > 32)[0]
            if len(cols) >= 2:
                spans.append(int(cols[-1] - cols[0]))
        return int(np.median(spans)) if spans else 0
    except Exception:
        return 0


def _measure_garment(img_path: Path, zone: str) -> tuple[int, int, int]:
    """Open an image, trim alpha, then measure waist/hem width.

    Returns (trimmed_w, trimmed_h, waist_width_px).
    waist_width_px is 0 on any failure.
    """
    try:
        import numpy as np
        from PIL import Image
        with Image.open(img_path) as img:
            img = img.convert("RGBA")
            img = _trim_alpha(img)
            w, h = img.size
            alpha = np.array(img)[:, :, 3]
            if zone == "top":
                waist_px = _measure_edge_width(alpha, "bottom")
            elif zone == "bottom":
                waist_px = _measure_edge_width(alpha, "top")
            elif zone in ("dress",):
                # Approximate waist at 35 % from top
                row = int(h * 0.35)
                sample = alpha[max(0, row - 4): row + 5, :]
                spans = []
                for r in sample:
                    c = np.where(r > 32)[0]
                    if len(c) >= 2:
                        spans.append(int(c[-1] - c[0]))
                waist_px = int(np.median(spans)) if spans else 0
            else:
                waist_px = 0
            return w, h, waist_px
    except Exception:
        return 1, 1, 0

# Where an accessory sits vertically on a flank, by where it's worn on the body
# (fraction of usable height for the item's centre). Jewelry / head items ride high.
_FLANK_ANCHOR: dict[str, float] = {"accessory": 0.22, "bag": 0.58}

# Per-accessory size as (flank-width fraction, usable-height fraction). A hat is
# wide so it needs a high width cap or it stays tiny; earrings are small both ways.
# Keyed on a keyword found in the category string; falls back to "default".
_ACC_SIZE: dict[str, tuple[float, float]] = {
    "hat":        (0.95, 0.20),
    "cap":        (0.95, 0.20),
    "scarf":      (0.72, 0.16),
    "belt":       (0.72, 0.13),
    "sunglasses": (0.55, 0.10),
    "glasses":    (0.55, 0.10),
    "earring":    (0.42, 0.09),
    "earrings":   (0.42, 0.09),
    "jewelry":    (0.42, 0.09),
    "necklace":   (0.45, 0.11),
    "ring":       (0.38, 0.08),
    "bracelet":   (0.42, 0.09),
    "watch":      (0.42, 0.09),
    "bag":        (0.95, 0.26),
    "default":    (0.58, 0.16),
}


def _acc_size(category: str | None) -> tuple[float, float]:
    c = (category or "").lower()
    for word in reversed(re.findall(r"[a-z]+", c)):  # head noun first
        if word in _ACC_SIZE:
            return _ACC_SIZE[word]
    return _ACC_SIZE["default"]


def _place_flank(
    items: list[int],
    *,
    flank_w: int,
    flank_cx: int,
    y0: int,
    usable_h: int,
    zones: list[str],
    categories: list[str | None],
    rng: random.Random,
) -> list[tuple[int, tuple[int, int, int, int, float]]]:
    """Place flank accessories at a body-appropriate height (head items high),
    stacking downward to avoid collisions when a side holds more than one."""
    out: list[tuple[int, tuple[int, int, int, int, float]]] = []
    ordered = sorted(items, key=lambda i: _FLANK_ANCHOR.get(zones[i], 0.4))
    prev_bottom = y0
    for i in ordered:
        z = zones[i]
        w_frac, h_frac = _acc_size(categories[i])
        box_w = int(flank_w * w_frac)
        box_h = int(usable_h * h_frac)
        cy = int(y0 + _FLANK_ANCHOR.get(z, 0.40) * usable_h)
        if cy - box_h // 2 < prev_bottom + _ITEM_GAP:
            cy = prev_bottom + _ITEM_GAP + box_h // 2
        cx = flank_cx + rng.randint(-8, 8)
        out.append((i, (cx, cy, box_w, box_h, rng.uniform(-_ACCESSORY_ROT, _ACCESSORY_ROT))))
        prev_bottom = cy + box_h // 2
    return out


def _stack_column(
    items: list[int],
    *,
    col_w: int,
    col_cx: int,
    y0: int,
    avail_h: float,
    zones: list[str],
    rng: random.Random,
    max_rot: float,
    order_map: dict[str, int] | None = None,
) -> list[tuple[int, tuple[int, int, int, int, float]]]:
    """Stack items vertically in a column, each given a weight-proportional cell."""
    if not items:
        return []
    ordered = (
        sorted(items, key=lambda i: (order_map.get(zones[i], 9), i))
        if order_map else items
    )
    weights = [_TIER_WEIGHT[zones[i]] for i in ordered]
    weight_sum = sum(weights) or 1.0
    avail = avail_h - _ITEM_GAP * (len(ordered) - 1)

    out: list[tuple[int, tuple[int, int, int, int, float]]] = []
    y = y0
    for i, w in zip(ordered, weights):
        cell_h = avail * (w / weight_sum)
        box_h = int(cell_h)
        box_w = int(col_w * _TIER_MAX_WIDTH[zones[i]])
        cx = col_cx + rng.randint(-8, 8)
        cy = int(y + cell_h / 2)
        out.append((i, (cx, cy, box_w, box_h, rng.uniform(-max_rot, max_rot))))
        y += cell_h + _ITEM_GAP
    return out


def _compute_layout(
    image_paths: list[Path],
    categories: list[str | None],
    rng: random.Random,
) -> list[tuple[int, int, int, int, float]]:
    """
    Returns (center_x, center_y, box_w, box_h, rotation_deg) for each item.

    Layout mirrors a classic outfit flat-lay:
      • a central vertical SPINE: garments stacked head-to-toe, then shoes —
        so the shoes sit in line directly beneath the top and bottom
      • ACCESSORIES (bag / jewelry / hat) flank the spine on BOTH sides,
        balanced left and right, with a slight tilt for an editorial feel
    Each item is scaled to FIT a bounding box whose height is proportional to its
    visual weight, so proportions stay sane and items never overlap.
    """
    n = len(image_paths)
    usable_x0, usable_y0 = _PAD, _PAD
    usable_x1, usable_y1 = CANVAS_W - _PAD, CONTENT_H - 40
    usable_w = usable_x1 - usable_x0
    usable_h = usable_y1 - usable_y0

    zones = [_resolve_zone(c) for c in categories]
    shoes      = [i for i in range(n) if zones[i] == "shoe"]
    outerwear  = [i for i in range(n) if zones[i] == "outerwear"]
    apparel    = [i for i in range(n) if zones[i] in _APPAREL_ZONES and zones[i] != "outerwear"]
    accessories = [i for i in range(n) if zones[i] in _EXTRA_ZONES and zones[i] != "shoe"]

    placements: list[tuple[int, int, int, int, float] | None] = [None] * n

    spine_w  = int(usable_w * _SPINE_FRACTION)
    spine_cx = (usable_x0 + usable_x1) // 2
    waist_y  = usable_y0 + int(usable_h * _WAIST_Y_FRAC)
    target_waist_px = int(spine_w * _WAIST_WIDTH_FRAC)

    tops    = sorted([i for i in apparel if zones[i] == "top"],    key=lambda i: i)
    bottoms = sorted([i for i in apparel if zones[i] == "bottom"], key=lambda i: i)
    dresses = sorted([i for i in apparel if zones[i] == "dress"],  key=lambda i: i)

    # Height budget for each garment zone
    # ponytail: small reserve — shoes place dynamically below the lowest garment
    # and may overlap the jean hem (realistic for boots), so bottoms no longer
    # need to surrender a big strip that strangled their width.
    _SHOE_RESERVE = 60   # px to leave below bottoms for shoes
    top_max_h    = waist_y - usable_y0 - _ITEM_GAP
    bottom_max_h = (usable_y1 - _SHOE_RESERVE) - waist_y
    dress_max_h  = usable_y1 - usable_y0 - _ITEM_GAP

    def _waist_dims(idx: int, zone: str, max_h: int | None = None) -> tuple[int, int]:
        orig_w, orig_h, waist_px = _measure_garment(image_paths[idx], zone)
        if orig_w < 1 or orig_h < 1:
            return target_waist_px, target_waist_px
        if waist_px > 10:
            s = target_waist_px / waist_px
        else:
            # Measurement failed — fill ~85 % of spine width
            s = (spine_w * 0.85) / orig_w
        dw = int(orig_w * s)
        dh = int(orig_h * s)
        if dw > spine_w:          # never wider than spine
            r = spine_w / dw
            dw, dh = spine_w, int(dh * r)
        if max_h is not None and dh > max_h > 0:   # clamp to available height
            r = max_h / dh
            dw, dh = int(dw * r), max_h
        return dw, dh

    # ── Tops: bottom edge at waist_y, stacked upward ─────────────────────────
    y_above = waist_y
    for i in tops:
        dw, dh = _waist_dims(i, "top", max_h=top_max_h)
        cy = y_above - dh // 2
        placements[i] = (spine_cx + rng.randint(-8, 8), cy, dw, dh,
                         rng.uniform(-_APPAREL_ROT, _APPAREL_ROT))
        y_above -= dh + _ITEM_GAP

    # ── Dresses: waist (≈35 % from top) at waist_y ──────────────────────────
    for i in dresses:
        dw, dh = _waist_dims(i, "dress", max_h=dress_max_h)
        waist_offset = int(dh * 0.35)
        cy = waist_y - waist_offset + dh // 2
        placements[i] = (spine_cx + rng.randint(-8, 8), cy, dw, dh,
                         rng.uniform(-_APPAREL_ROT, _APPAREL_ROT))

    # ── Bottoms: top edge at waist_y, stacked downward ──────────────────────
    y_below = waist_y
    for i in bottoms:
        dw, dh = _waist_dims(i, "bottom", max_h=bottom_max_h)
        cy = y_below + dh // 2
        placements[i] = (spine_cx + rng.randint(-8, 8), cy, dw, dh,
                         rng.uniform(-_APPAREL_ROT, _APPAREL_ROT))
        y_below += dh + _ITEM_GAP

    # ── Shoes: below the lowest placed garment, at a guaranteed target size ──
    # ponytail: fixed target box, not leftover space — fitting a tall boot into
    # whatever scraps remained was what made shoes render tiny.
    if shoes:
        placed_bottoms = [
            placements[i][1] + placements[i][3] // 2
            for i in tops + bottoms + dresses
            if placements[i] is not None
        ]
        shoe_y0 = (max(placed_bottoms) if placed_bottoms else waist_y) + _ITEM_GAP
        shoe_target_h = int(usable_h * 0.18)
        shoe_box_w = int(spine_w * 0.80)
        y = shoe_y0
        for i in shoes:
            cy = min(y + shoe_target_h // 2, usable_y1 - shoe_target_h // 2)
            placements[i] = (spine_cx + rng.randint(-8, 8), cy,
                             shoe_box_w, shoe_target_h,
                             rng.uniform(-_APPAREL_ROT, _APPAREL_ROT))
            y += shoe_target_h + _ITEM_GAP

    # Fallback: if nothing on the spine (all accessories), promote accessories
    if not any(placements[i] is not None for i in range(n) if zones[i] not in _EXTRA_ZONES):
        if accessories:
            for i, p in _stack_column(
                accessories[:3], col_w=spine_w, col_cx=spine_cx, y0=usable_y0,
                avail_h=usable_h, zones=zones, rng=rng, max_rot=_ACCESSORY_ROT,
            ):
                placements[i] = p
                accessories = [a for a in accessories if a != i]

    # Compute flank geometry (needed for both accessories and outerwear)
    spine_left  = spine_cx - spine_w // 2
    spine_right = spine_cx + spine_w // 2
    left_cx  = (usable_x0 + spine_left  - _FLANK_GAP) // 2
    right_cx = (spine_right + _FLANK_GAP + usable_x1) // 2
    left_w   = max(150, spine_left  - _FLANK_GAP - usable_x0)
    right_w  = max(150, usable_x1 - spine_right  - _FLANK_GAP)

    # Accessories: alternate right / left
    acc_sorted  = sorted(accessories, key=lambda i: (_EXTRA_ORDER.get(zones[i], 9), i))
    right_acc   = acc_sorted[0::2]
    left_acc    = acc_sorted[1::2]

    for items, fw, fcx in ((right_acc, right_w, right_cx), (left_acc, left_w, left_cx)):
        for i, p in _place_flank(
            items, flank_w=fw, flank_cx=fcx, y0=usable_y0,
            usable_h=usable_h, zones=zones, categories=categories, rng=rng,
        ):
            placements[i] = p

    # Outerwear: editorial side column, but sized like a real garment — not capped
    # to the narrow flank width (that made coats read tiny). Widen toward the spine
    # and clamp the centre so it never clips the canvas edge.
    if outerwear:
        left_side = len(left_acc) <= len(right_acc)
        ow_w = max(left_w if left_side else right_w, int(spine_w * 0.62))
        base_cx = left_cx if left_side else right_cx
        half = ow_w // 2
        ow_cx = min(max(base_cx, usable_x0 + half), usable_x1 - half)
        for i, p in _stack_column(
            outerwear, col_w=ow_w, col_cx=ow_cx, y0=usable_y0,
            avail_h=usable_h, zones=zones, rng=rng, max_rot=_APPAREL_ROT,
            order_map=_APPAREL_ORDER,
        ):
            placements[i] = p

    # Safety: any item that somehow wasn't placed gets a centered fallback box
    for i in range(n):
        if placements[i] is None:
            placements[i] = (CANVAS_W // 2, CONTENT_H // 2, 300, 300, 0.0)

    return placements  # type: ignore[return-value]


def _trim_alpha(img: "Image.Image") -> "Image.Image":
    """Crop fully-transparent borders so fit-to-box sizing is accurate."""
    bbox = img.getbbox()
    if bbox:
        return img.crop(bbox)
    return img


def _resolve_zone(category: str | None) -> str:
    """Map a free-text category string to one of the defined zone keys.

    The head noun of a fashion descriptor is almost always the LAST word
    ("woven straw crossbody BAG", "platform strappy SANDAL", "chunky hoop
    EARRINGS"), so we scan words from the end. This avoids ambiguous modifiers
    like "mini"/"maxi" hijacking the match (e.g. "mini ... bag" → dress).
    """
    if not category:
        return "accessory"
    cat_lower = category.lower().strip()
    # Direct full-string match
    if cat_lower in _CATEGORY_MAP:
        return _CATEGORY_MAP[cat_lower]
    # Scan words from the end — head noun is the strongest signal
    words = re.findall(r"[a-z]+", cat_lower)
    for word in reversed(words):
        if word in _CATEGORY_MAP:
            return _CATEGORY_MAP[word]
    # Last resort: any substring match anywhere
    for key, zone in _CATEGORY_MAP.items():
        if key in cat_lower:
            return zone
    return "accessory"


# ── text strip ─────────────────────────────────────────────────────────────────

def _draw_text_strip(
    collage: "Image.Image",
    concept_name: str,
    outfit_number: int,
    accent_rgb: tuple[int, int, int],
    font_style: str,
) -> None:
    from PIL import ImageDraw, ImageFont

    draw = ImageDraw.Draw(collage)
    line_y = CONTENT_H
    draw.line([(60, line_y), (CANVAS_W - 60, line_y)], fill=(*accent_rgb, 50), width=1)

    fonts = _FONTS.get(font_style, _FONTS["sans"])
    try:
        font_heading = ImageFont.truetype(fonts["heading"], 62)
        font_sub     = ImageFont.truetype(fonts["sub"],     38)
    except Exception:
        font_heading = ImageFont.load_default()
        font_sub     = font_heading

    name_display   = concept_name.upper() if concept_name else ""
    number_display = f"#{str(outfit_number).zfill(3)}"

    text_y = CONTENT_H + 32
    draw.text((70, text_y), name_display, font=font_heading, fill=(*accent_rgb, 255))

    bbox = draw.textbbox((0, 0), number_display, font=font_sub)
    num_w = bbox[2] - bbox[0]
    draw.text(
        (CANVAS_W - 70 - num_w, text_y + 14),
        number_display,
        font=font_sub,
        fill=(*accent_rgb, 180),
    )


# ── helpers ────────────────────────────────────────────────────────────────────

def _hex_to_rgb(hex_str: str) -> tuple[int, int, int]:
    h = hex_str.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _rng_seed(s: str) -> int:
    return int(hashlib.md5(s.encode()).hexdigest(), 16) % (2 ** 32)


def _build_layout_from_bboxes(
    bboxes: list[tuple[int, int, int, int, float]],
    canvas: Canvas,
) -> CollageLayout:
    placements = [
        Placement(index=i, x=x, y=y, width=w, height=h)
        for i, (x, y, w, h, _rot) in enumerate(bboxes)
    ]
    return CollageLayout(canvas=canvas, placements=placements)


def _build_manifest_from_bboxes(
    image_paths: list[Path],
    bboxes: list[tuple[int, int, int, int, float]],
    *,
    product_ids: list[str] | None = None,
) -> dict:
    product_ids = product_ids or []
    pieces = []
    for i, (img_path, (x, y, w, h, rotation)) in enumerate(zip(image_paths, bboxes)):
        piece: dict = {
            "index": i,
            "image_path": str(img_path),
            "x": x,
            "y": y,
            "width": w,
            "height": h,
            "rotation": rotation,
            "z_index": i + 1,
        }
        if i < len(product_ids):
            piece["product_id"] = product_ids[i]
        pieces.append(piece)
    return {
        "canvas": {"width": CANVAS_W, "height": CANVAS_H},
        "pieces": pieces,
    }


# Keep for backward compat (collage_pipeline fallback path)
def collage_manifest(
    image_paths: list[Path],
    layout: CollageLayout,
    *,
    product_ids: list[str] | None = None,
) -> dict:
    product_ids = product_ids or []
    pieces = []
    for i, (image_path, placement) in enumerate(zip(image_paths, layout.placements)):
        piece: dict = {
            "index": placement.index,
            "image_path": str(image_path),
            "x": placement.x,
            "y": placement.y,
            "width": placement.width,
            "height": placement.height,
        }
        if i < len(product_ids):
            piece["product_id"] = product_ids[i]
        pieces.append(piece)
    return {
        "canvas": {"width": CANVAS_W, "height": CANVAS_H},
        "pieces": pieces,
    }


def _export_placeholder_collage(
    image_paths: list[Path],
    output_path: Path,
    canvas: Canvas,
) -> Path:
    return write_solid_png(
        output_path, width=canvas.width, height=canvas.height, rgb=canvas.background_rgb,
    )
