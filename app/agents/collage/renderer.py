from __future__ import annotations

from pathlib import Path

from app.collage.export import CollageExportResult, export_collage
from app.collage.layout import Canvas


def render_deterministic_collage(
    image_paths: list[Path],
    output_path: Path,
    *,
    canvas: Canvas | None = None,
) -> CollageExportResult:
    return export_collage(image_paths, output_path, canvas=canvas)
