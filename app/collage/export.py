from __future__ import annotations

import hashlib
import random
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

# ── category zone definitions ──────────────────────────────────────────────────
# Each zone: (center_x, center_y, target_width, base_rotation_deg)
# cx/cy are pixel positions in the content area (0,0) = top-left of canvas
_ZONES: dict[str, tuple[int, int, int, float]] = {
    "outerwear": (540, 290, 460,  0.0),
    "top":       (340, 270, 370, -5.0),
    "bottom":    (490, 660, 370,  4.0),
    "dress":     (540, 440, 420, -3.0),
    "shoe":      (490, 950, 250,  8.0),
    "bag":       (820, 590, 250, -6.0),
    "accessory": (210, 710, 180,  7.0),
}

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

# Conflict offsets when multiple items share a zone (alternate left/right/up/down)
_CONFLICT_OFFSETS = [(-90, 0), (90, 0), (0, -70), (0, 70)]


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

    placements = _compute_placements(
        image_paths,
        categories or [None] * len(image_paths),
        rng,
    )

    # (canvas_x, canvas_y, render_w, render_h, rotation) for web layout
    placed_bboxes: list[tuple[int, int, int, int, float]] = []

    for img_path, (cx, cy, rotation, target_w) in zip(image_paths, placements):
        with Image.open(img_path) as img:
            img = img.convert("RGBA")
            scale = target_w / img.width
            new_w = target_w
            new_h = int(img.height * scale)
            if new_h > int(CONTENT_H * 0.62):
                new_h = int(CONTENT_H * 0.62)
                new_w = int(img.width * new_h / img.height)
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

def _compute_placements(
    image_paths: list[Path],
    categories: list[str | None],
    rng: random.Random,
) -> list[tuple[int, int, float, int]]:
    """
    Returns (center_x, center_y, rotation_deg, target_width) for each item,
    using zone-based positioning when categories are available, scattered
    fallback otherwise.
    """
    zone_counts: dict[str, int] = {}
    result: list[tuple[int, int, float, int]] = []

    for i, (img_path, cat) in enumerate(zip(image_paths, categories)):
        zone_key = _resolve_zone(cat)
        count = zone_counts.get(zone_key, 0)
        zone_counts[zone_key] = count + 1

        cx, cy, target_w, base_rot = _ZONES[zone_key]

        # Offset when multiple items share the same zone
        if count > 0 and count <= len(_CONFLICT_OFFSETS):
            ox, oy = _CONFLICT_OFFSETS[count - 1]
            cx += ox
            cy += oy

        # Small random nudge for organic feel
        cx += rng.randint(-28, 28)
        cy += rng.randint(-20, 20)
        rotation = base_rot + rng.uniform(-3.0, 3.0)

        # Clamp so items stay on canvas
        cx = max(target_w // 2 + 20, min(CANVAS_W - target_w // 2 - 20, cx))
        cy = max(80, min(CONTENT_H - 80, cy))

        result.append((cx, cy, rotation, target_w))

    return result


def _resolve_zone(category: str | None) -> str:
    """Map a free-text category string to one of the defined zone keys."""
    if not category:
        return "accessory"
    cat_lower = category.lower().strip()
    # Direct match
    if cat_lower in _CATEGORY_MAP:
        return _CATEGORY_MAP[cat_lower]
    # Partial match — check if any map key appears in the category string
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
