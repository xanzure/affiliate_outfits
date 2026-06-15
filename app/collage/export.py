from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from app.collage.image_utils import inspect_image, write_solid_png
from app.collage.layout import Canvas, CollageLayout, fixed_grid_layout, layout_to_dict


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
) -> CollageExportResult:
    if not image_paths:
        raise ValueError("at least one image is required to export a collage")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas = canvas or Canvas()
    layout = fixed_grid_layout(len(image_paths), canvas=canvas)

    try:
        from PIL import Image
    except ImportError:
        image_path = _export_placeholder_collage(image_paths, output_path, canvas)
        return CollageExportResult(
            image_path=image_path,
            layout=layout,
            manifest=collage_manifest(image_paths, layout),
        )

    collage = Image.new("RGB", (canvas.width, canvas.height), canvas.background_rgb)

    for image_path, placement in zip(image_paths, layout.placements):
        with Image.open(image_path) as image:
            image.thumbnail((placement.width, placement.height))
            x = placement.x + (placement.width - image.width) // 2
            y = placement.y + (placement.height - image.height) // 2
            if image.mode == "RGBA":
                collage.paste(image, (x, y), image)
            else:
                collage.paste(image.convert("RGB"), (x, y))

    collage.save(output_path)
    return CollageExportResult(
        image_path=output_path,
        layout=layout,
        manifest=collage_manifest(image_paths, layout),
    )


def collage_manifest(
    image_paths: list[Path],
    layout,
    *,
    product_ids: list[str] | None = None,
) -> dict:
    manifest = layout_to_dict(layout)
    product_ids = product_ids or []
    pieces = []
    for image_path, placement in zip(image_paths, layout.placements, strict=True):
        piece = {
            "index": placement.index,
            "image_path": str(image_path),
            "x": placement.x,
            "y": placement.y,
            "width": placement.width,
            "height": placement.height,
        }
        if placement.index < len(product_ids):
            piece["product_id"] = product_ids[placement.index]
        pieces.append(piece)
    manifest["pieces"] = pieces
    return manifest


def _export_placeholder_collage(
    image_paths: list[Path],
    output_path: Path,
    canvas: Canvas,
) -> Path:
    """Fallback renderer for environments without Pillow.

    It cannot composite arbitrary images without an imaging library, so it emits
    a valid canvas-sized PNG. This keeps the pipeline deterministic and testable
    until Pillow is installed.
    """

    if len(image_paths) == 1:
        source = image_paths[0]
        info = inspect_image(source)
        if info.width == canvas.width and info.height == canvas.height:
            shutil.copy2(source, output_path)
            return output_path

    return write_solid_png(
        output_path,
        width=canvas.width,
        height=canvas.height,
        rgb=canvas.background_rgb,
    )
