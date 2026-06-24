from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from app.agents.collage.renderer import render_deterministic_collage
from app.collage.export import CollageExportResult
from app.collage.layout import Canvas, CollageLayout, Placement
from app.config import Settings, load_settings
from app.services.image_service import PreparedImage

if TYPE_CHECKING:
    from app.agents.collage.style_agent import BatchVisualStyle


def render_collage_for_images(
    prepared_images: list[PreparedImage],
    *,
    output_name: str,
    settings: Settings | None = None,
    style: "BatchVisualStyle | None" = None,
    concept_name: str = "",
    outfit_number: int = 1,
    categories: list[str | None] | None = None,
) -> Path:
    return render_collage_manifest_for_images(
        prepared_images,
        output_name=output_name,
        settings=settings,
        style=style,
        concept_name=concept_name,
        outfit_number=outfit_number,
        categories=categories,
    ).image_path


def render_collage_manifest_for_images(
    prepared_images: list[PreparedImage],
    *,
    output_name: str,
    settings: Settings | None = None,
    style: "BatchVisualStyle | None" = None,
    concept_name: str = "",
    outfit_number: int = 1,
    categories: list[str | None] | None = None,
) -> CollageExportResult:
    settings = settings or load_settings()
    output_path = settings.data_dir / "images" / "collages" / output_name
    image_paths = [item.normalized_path for item in prepared_images]
    return render_deterministic_collage(
        image_paths,
        output_path,
        style=style,
        concept_name=concept_name,
        outfit_number=outfit_number,
        categories=categories,
    )


def render_html_collage_for_images(
    prepared_images: list[PreparedImage],
    *,
    output_name: str,
    settings: Settings | None = None,
    style: "BatchVisualStyle | None" = None,
    concept_name: str = "",
    outfit_number: int = 1,
    categories: list[str | None] | None = None,
    template_name: str | None = None,
) -> CollageExportResult:
    """Render a collage with the HTML/CSS template engine (Route 1)."""
    import base64

    from app.collage.html_export import render_collage, CANVAS_W, CANVAS_H

    settings = settings or load_settings()
    output_path = settings.data_dir / "images" / "collages" / output_name
    # Embed cutouts as base64 data URIs — Chromium blocks file:// subresources on
    # a set_content page, and data URIs need no network and work the same on Railway.
    image_urls = [
        "data:image/png;base64," + base64.b64encode(Path(item.normalized_path).read_bytes()).decode()
        for item in prepared_images
    ]
    manifest = render_collage(
        image_urls,
        categories or [None] * len(prepared_images),
        output_path,
        concept_name=concept_name,
        outfit_number=outfit_number,
        style=style,
        template_name=template_name,
    )
    placements = [
        Placement(index=p["index"], x=p["x"], y=p["y"], width=p["width"], height=p["height"])
        for p in manifest["pieces"]
    ]
    layout = CollageLayout(canvas=Canvas(width=CANVAS_W, height=CANVAS_H), placements=placements)
    return CollageExportResult(image_path=output_path, layout=layout, manifest=manifest)
