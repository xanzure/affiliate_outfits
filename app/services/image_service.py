from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from app.collage.image_utils import ImageInfo, inspect_image, safe_image_filename
from app.config import Settings, load_settings


@dataclass(frozen=True)
class PreparedImage:
    source_path: Path
    original_path: Path
    normalized_path: Path
    info: ImageInfo
    normalized: bool


class ImageService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or load_settings()
        self.image_dir = self.settings.data_dir / "images"
        self.originals_dir = self.image_dir / "originals"
        self.normalized_dir = self.image_dir / "normalized"
        self.downloads_dir = self.image_dir / "downloads"

    def download_image(
        self,
        image_url: str,
        *,
        asset_id: str,
        max_bytes: int = 10_000_000,
        timeout_seconds: int = 30,
    ) -> Path:
        self.downloads_dir.mkdir(parents=True, exist_ok=True)
        request = Request(
            image_url,
            headers={"User-Agent": "affiliate-outfits/0.1"},
        )
        with urlopen(request, timeout=timeout_seconds) as response:
            content_type = response.headers.get("Content-Type", "")
            payload = response.read(max_bytes + 1)

        if len(payload) > max_bytes:
            raise ValueError(f"image download exceeded {max_bytes} bytes: {image_url}")

        extension = _image_extension(image_url, content_type)
        destination = self.downloads_dir / f"{asset_id}{extension}"
        destination.write_bytes(payload)
        return destination

    def prepare_local_image(
        self,
        source_path: Path,
        *,
        asset_id: str,
        min_width: int = 1,
        min_height: int = 1,
    ) -> PreparedImage:
        source_path = source_path.resolve()
        info = inspect_image(source_path)
        if info.width < min_width or info.height < min_height:
            raise ValueError(
                f"image too small: {source_path} is {info.width}x{info.height}, "
                f"expected at least {min_width}x{min_height}"
            )

        self.originals_dir.mkdir(parents=True, exist_ok=True)
        self.normalized_dir.mkdir(parents=True, exist_ok=True)

        original_path = self.originals_dir / f"{asset_id}-{safe_image_filename(source_path)}"
        shutil.copy2(source_path, original_path)

        normalized_path, normalized = normalize_image(original_path, self.normalized_dir / original_path.name)
        normalized_info = inspect_image(normalized_path)

        return PreparedImage(
            source_path=source_path,
            original_path=original_path,
            normalized_path=normalized_path,
            info=normalized_info,
            normalized=normalized,
        )


def normalize_image(source_path: Path, destination_path: Path) -> tuple[Path, bool]:
    """Normalize an image when Pillow is available; otherwise copy it unchanged."""

    try:
        from PIL import Image, ImageOps
    except ImportError:
        shutil.copy2(source_path, destination_path)
        return destination_path, False

    with Image.open(source_path) as image:
        image = ImageOps.exif_transpose(image)
        if image.mode not in {"RGB", "RGBA"}:
            image = image.convert("RGBA" if "A" in image.mode else "RGB")
        image.save(destination_path)

    return destination_path, True


def _image_extension(image_url: str, content_type: str) -> str:
    content_type = content_type.lower().split(";", 1)[0].strip()
    if content_type == "image/png":
        return ".png"
    if content_type in {"image/jpeg", "image/jpg"}:
        return ".jpg"
    if content_type == "image/webp":
        return ".webp"

    suffix = Path(urlparse(image_url).path).suffix.lower()
    if suffix in {".png", ".jpg", ".jpeg", ".webp"}:
        return ".jpg" if suffix == ".jpeg" else suffix
    return ".jpg"
