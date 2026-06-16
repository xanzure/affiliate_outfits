from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from app.collage.export import CollageExportResult, export_collage
from app.collage.layout import Canvas

if TYPE_CHECKING:
    from app.agents.collage.style_agent import BatchVisualStyle


def render_deterministic_collage(
    image_paths: list[Path],
    output_path: Path,
    *,
    canvas: Canvas | None = None,
    style: "BatchVisualStyle | None" = None,
    concept_name: str = "",
    outfit_number: int = 1,
    categories: list[str | None] | None = None,
) -> CollageExportResult:
    return export_collage(
        image_paths,
        output_path,
        canvas=canvas,
        style=style,
        concept_name=concept_name,
        outfit_number=outfit_number,
        categories=categories,
        seed=output_path.stem,
    )
