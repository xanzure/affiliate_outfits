from __future__ import annotations

from pathlib import Path

from app.agents.collage.renderer import render_deterministic_collage
from app.collage.export import CollageExportResult
from app.config import Settings, load_settings
from app.services.image_service import PreparedImage


def render_collage_for_images(
    prepared_images: list[PreparedImage],
    *,
    output_name: str,
    settings: Settings | None = None,
) -> Path:
    return render_collage_manifest_for_images(
        prepared_images,
        output_name=output_name,
        settings=settings,
    ).image_path


def render_collage_manifest_for_images(
    prepared_images: list[PreparedImage],
    *,
    output_name: str,
    settings: Settings | None = None,
) -> CollageExportResult:
    settings = settings or load_settings()
    output_path = settings.data_dir / "images" / "collages" / output_name
    image_paths = [item.normalized_path for item in prepared_images]
    return render_deterministic_collage(image_paths, output_path)
