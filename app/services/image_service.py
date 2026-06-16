from __future__ import annotations

import io
import json
import logging
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from app.collage.image_utils import ImageInfo, inspect_image, safe_image_filename
from app.config import Settings, load_settings

log = logging.getLogger(__name__)

_RUNFLOW_API = "https://api.runflow.io/v1/models/runflow/model-removal"
_RUNFLOW_POLL_INTERVAL = 3  # seconds between status checks
_RUNFLOW_TIMEOUT = 90  # seconds before giving up


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

    @property
    def _runflow_api_key(self) -> str | None:
        return self.settings.runflow_api_key

    def process_from_url(self, image_url: str, *, asset_id: str) -> PreparedImage:
        """
        Primary image path: send a public image URL through Runflow model-removal,
        download the result, and save as a normalized PNG.
        Falls back to download + rembg if Runflow fails or no key is set.
        """
        self.normalized_dir.mkdir(parents=True, exist_ok=True)
        self.originals_dir.mkdir(parents=True, exist_ok=True)
        normalized_dest = self.normalized_dir / f"{asset_id}.png"

        if self._runflow_api_key:
            result_url = _runflow_remove_model(image_url, api_key=self._runflow_api_key)
            if result_url:
                log.info("Runflow succeeded for %s", asset_id)
                downloaded = self._download_raw(result_url, asset_id=f"{asset_id}_runflow", ext=".png")
                shutil.copy2(downloaded, normalized_dest)
                info = inspect_image(normalized_dest)
                return PreparedImage(
                    source_path=downloaded,
                    original_path=downloaded,
                    normalized_path=normalized_dest,
                    info=info,
                    normalized=True,
                )
            log.warning("Runflow failed for %s, falling back to rembg", asset_id)

        # Fallback: download locally + rembg
        source = self.download_image(image_url, asset_id=asset_id)
        return self.prepare_local_image(source, asset_id=asset_id)

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

    def _download_raw(self, url: str, *, asset_id: str, ext: str = ".png") -> Path:
        self.downloads_dir.mkdir(parents=True, exist_ok=True)
        request = Request(url, headers={"User-Agent": "affiliate-outfits/0.1"})
        with urlopen(request, timeout=30) as response:
            payload = response.read()
        destination = self.downloads_dir / f"{asset_id}{ext}"
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

        normalized_dest = self.normalized_dir / f"{asset_id}.png"
        normalized_path, normalized = normalize_image(original_path, normalized_dest)
        normalized_info = inspect_image(normalized_path)

        return PreparedImage(
            source_path=source_path,
            original_path=original_path,
            normalized_path=normalized_path,
            info=normalized_info,
            normalized=normalized,
        )


def _runflow_remove_model(image_url: str, *, api_key: str) -> str | None:
    """POST to Runflow, poll until done, return the result image URL or None on failure."""
    try:
        payload = json.dumps({
            "input": {"image_url": image_url, "config": {}},
        }).encode()

        req = Request(
            f"{_RUNFLOW_API}/runs",
            data=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urlopen(req, timeout=30) as resp:
            run = json.loads(resp.read())

        run_id = run.get("id") or run.get("run_id")
        if not run_id:
            log.warning("Runflow: no run_id in response: %s", run)
            return None

        # May already be done synchronously
        if run.get("status") == "succeeded":
            return _extract_runflow_image(run)

        # Poll until terminal state
        deadline = time.time() + _RUNFLOW_TIMEOUT
        while time.time() < deadline:
            time.sleep(_RUNFLOW_POLL_INTERVAL)
            req = Request(
                f"{_RUNFLOW_API}/runs/{run_id}",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            with urlopen(req, timeout=15) as resp:
                run = json.loads(resp.read())

            status = run.get("status")
            if status == "succeeded":
                return _extract_runflow_image(run)
            if status in ("failed", "cancelled"):
                log.warning("Runflow run %s: %s", run_id, status)
                return None

        log.warning("Runflow run %s timed out after %ds", run_id, _RUNFLOW_TIMEOUT)
        return None

    except Exception:
        log.exception("Runflow API error")
        return None


def _extract_runflow_image(run: dict) -> str | None:
    output = run.get("output") or {}
    urls = output.get("image_urls") or []
    return urls[0] if urls else None


def normalize_image(source_path: Path, destination_path: Path) -> tuple[Path, bool]:
    """Normalize and remove background from a local image using rembg, saving as PNG."""
    try:
        from PIL import Image, ImageOps
    except ImportError:
        shutil.copy2(source_path, destination_path)
        return destination_path, False

    with Image.open(source_path) as image:
        image = ImageOps.exif_transpose(image)
        if image.mode not in {"RGB", "RGBA"}:
            image = image.convert("RGBA" if "A" in image.mode else "RGB")

        image = _rembg_remove(image)
        destination_path = destination_path.with_suffix(".png")
        image.save(destination_path, format="PNG")

    return destination_path, True


def _rembg_remove(image: "PIL.Image.Image") -> "PIL.Image.Image":
    try:
        from rembg import remove
        result = remove(image)
        if _rembg_failed(result):
            return image
        return result
    except Exception:
        return image


def _rembg_failed(result: "PIL.Image.Image") -> bool:
    try:
        import numpy as np
        rgba = result.convert("RGBA")
        arr = np.array(rgba)
        alpha = arr[:, :, 3]
        total_pixels = alpha.size
        if total_pixels == 0:
            return True
        pct_transparent = (alpha < 10).sum() / total_pixels
        if pct_transparent > 0.80:
            return True
        visible = arr[alpha > 10]
        if len(visible) > 0:
            mean_brightness = visible[:, :3].mean()
            if mean_brightness < 30:
                return True
        return False
    except Exception:
        return False


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
