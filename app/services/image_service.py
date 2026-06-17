from __future__ import annotations

import json
import logging
import shutil
import threading
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from app.collage.image_utils import ImageInfo, inspect_image, safe_image_filename
from app.config import Settings, load_settings

log = logging.getLogger(__name__)

# ── Runflow ──────────────────────────────────────────────────────────────────────
# product-isolation: PRIMARY. Generative isolation of a prompt-named item from ANY
#   source (model shot, lifestyle, flat-lay). Returns a clean product on off-white.
# model-removal: legacy, kept for reference / fallback experiments.
_RUNFLOW_ISOLATION_URL = "https://api.runflow.io/v1/models/runflow/product-isolation/runs"
_RUNFLOW_MODEL_REMOVAL_URL = "https://api.runflow.io/v1/models/runflow/model-removal/runs"
_RUNFLOW_POLL_URL = "https://api.runflow.io/v1/runs"
_RUNFLOW_POLL_INTERVAL = 5   # seconds between status checks
_RUNFLOW_TIMEOUT = 240       # seconds before giving up (isolation runs take ~30-45s)
_RUNFLOW_RESOLUTION = "1K"   # 1024px long side — plenty for collage tiles
_RUNFLOW_ASPECT_RATIO = "3:4"  # portrait frame fits most fashion items without cropping

# ── rembg models ────────────────────────────────────────────────────────────────
# u2net_human_seg: human silhouette segmentation — used to DETECT model shots.
# isnet-general-use: high-quality general object cutout — used to REMOVE backgrounds.
_HUMAN_SEG_MODEL = "u2net_human_seg"
_CUTOUT_MODEL = "isnet-general-use"

# ── classification thresholds (tunable) ─────────────────────────────────────────
# Fraction of image area that must be "human" for an image to count as a model shot.
_MODEL_HUMAN_FRACTION = 0.10
# Fraction of image that must already be transparent to count as a pre-cut PNG.
_TRANSPARENT_FRACTION = 0.08
# Downscale longest edge to this before running human segmentation (speed).
_CLASSIFY_MAX_EDGE = 384

# ── final cutout validation thresholds ──────────────────────────────────────────
_MIN_VISIBLE_FRACTION = 0.015   # below this the cutout is effectively blank
_MIN_VISIBLE_BRIGHTNESS = 18    # mean brightness of visible pixels; below = black blob
_TRIM_PADDING = 10              # px of transparent padding kept around trimmed cutouts


class ImageClass(str, Enum):
    """How a source image should be routed through the pipeline."""

    MODEL_SHOT = "model_shot"          # person/mannequin present → Runflow model-removal
    PRODUCT = "product"                # flat/on-white/colored bg, no model → rembg cutout
    ALREADY_CUTOUT = "already_cutout"  # already transparent → pass through


@dataclass(frozen=True)
class Classification:
    image_class: ImageClass
    human_fraction: float = 0.0
    transparent_fraction: float = 0.0
    edge_whiteness: float = 0.0


@dataclass(frozen=True)
class PreparedImage:
    source_path: Path
    original_path: Path
    normalized_path: Path
    info: ImageInfo
    normalized: bool
    image_class: ImageClass | None = None
    route: str = ""  # human-readable description of how it was processed


# ── lazy, shared rembg sessions ─────────────────────────────────────────────────
_SESSION_LOCK = threading.Lock()
_SESSIONS: dict[str, object] = {}


def _get_session(model_name: str):
    """Return a cached rembg session, creating it once. Thread-safe."""
    with _SESSION_LOCK:
        session = _SESSIONS.get(model_name)
        if session is None:
            from rembg import new_session

            session = new_session(model_name)
            _SESSIONS[model_name] = session
        return session


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

    def _ensure_dirs(self) -> None:
        for d in (self.originals_dir, self.normalized_dir, self.downloads_dir):
            d.mkdir(parents=True, exist_ok=True)

    # ── public entry points ──────────────────────────────────────────────────

    def process_batch(
        self, items: list[tuple[str, str] | tuple[str, str, str | None]]
    ) -> dict[str, PreparedImage]:
        """
        Parallel image processing for a set of products.

        Each item is (asset_id, image_url) or (asset_id, image_url, prompt), where
        `prompt` describes the single item to isolate (e.g. "the cobalt blue ruched
        mini skirt"). The prompt comes from the curator/product description and makes
        isolation pick the exact item even from on-model or multi-item photos.

        Primary path (when a Runflow key is set):
          1. Download source → originals/.
          2. Runflow product-isolation (prompt-targeted) → clean product on off-white.
          3. rembg alpha pass → transparent → trim → normalized/.

        Fallback path (no key, or isolation failed/garbage):
          rembg cutout of the original (with transparent pass-through detection).

        Isolation submit + poll and downloads all run in parallel. Returns a dict
        asset_id -> PreparedImage; assets whose source can't be downloaded at all
        are omitted (the caller supplies a placeholder).
        """
        self._ensure_dirs()
        if not items:
            return {}

        norm = [(it[0], it[1], it[2] if len(it) > 2 else None) for it in items]
        url_by_id = {aid: url for aid, url, _ in norm}
        prompt_by_id = {aid: prompt for aid, _, prompt in norm}

        # Phase 1 — download all originals in parallel.
        originals: dict[str, Path] = {}

        def _dl(asset_id: str, url: str, _prompt: str | None) -> None:
            try:
                originals[asset_id] = self._download_original(url, asset_id)
            except Exception:
                log.warning("download failed for %s (%s)", asset_id, url[:80])

        _run_threads(_dl, norm)
        if not originals:
            return {}

        # Phase 2 — submit all isolation runs in parallel (if Runflow is available).
        run_ids: dict[str, str] = {}
        if self._runflow_api_key:
            ids = list(originals.keys())
            log.info("Submitting %d product-isolation run(s)...", len(ids))

            def _submit(asset_id: str) -> None:
                rid = _runflow_isolation_submit(
                    url_by_id[asset_id],
                    prompt=prompt_by_id.get(asset_id),
                    api_key=self._runflow_api_key,
                )
                if rid:
                    run_ids[asset_id] = rid

            _run_threads(lambda aid: _submit(aid), [(aid,) for aid in ids])

        # Phase 3 — poll all isolation runs in parallel.
        runflow_urls: dict[str, str | None] = {}
        if run_ids:

            def _poll(asset_id: str) -> None:
                runflow_urls[asset_id] = _runflow_poll(
                    run_ids[asset_id], api_key=self._runflow_api_key
                )

            _run_threads(lambda aid: _poll(aid), [(aid,) for aid in run_ids])

        # Phase 4 — finalize each asset: isolation result if good, else rembg fallback.
        results: dict[str, PreparedImage] = {}
        for asset_id, path in originals.items():
            try:
                results[asset_id] = self._finalize(
                    asset_id, path, runflow_urls.get(asset_id)
                )
            except Exception:
                log.exception("finalize failed for %s", asset_id)
        return results

    def process_from_url(
        self, image_url: str, *, asset_id: str, prompt: str | None = None
    ) -> PreparedImage:
        """Single-image convenience wrapper around process_batch."""
        results = self.process_batch([(asset_id, image_url, prompt)])
        if asset_id in results:
            return results[asset_id]
        # Total failure path: download + local cutout, or raise.
        source = self.download_image(image_url, asset_id=asset_id)
        return self.prepare_local_image(source, asset_id=asset_id)

    # ── per-image finalizers ─────────────────────────────────────────────────

    def _finalize(
        self, asset_id: str, original_path: Path, isolation_url: str | None
    ) -> PreparedImage:
        """Turn an isolation result (or the original) into a clean transparent PNG."""
        from PIL import Image, ImageOps

        # Primary: Runflow product-isolation output → rembg alpha pass.
        if isolation_url:
            try:
                raw_path = self._download_raw(
                    isolation_url, asset_id=f"{asset_id}_isolated", ext=".webp"
                )
                with Image.open(raw_path) as iso:
                    iso = ImageOps.exif_transpose(iso)
                    ok, reason = validate_runflow_result(iso)
                    if ok:
                        cutout = _rembg_cutout(iso, _CUTOUT_MODEL)
                        cut_ok, cut_reason = validate_cutout(cutout)
                        if cut_ok:
                            final = _trim_transparent(cutout)
                            route = "isolation+rembg"
                        else:
                            # Alpha pass nuked it — keep the isolation image as-is.
                            final = iso.convert("RGBA")
                            route = f"isolation-raw(alpha:{cut_reason})"
                        normalized_path = self._save_normalized(final, asset_id)
                        return self._prepared(
                            asset_id, original_path, normalized_path, route, normalized=True
                        )
                    log.info("isolation result rejected for %s (%s)", asset_id, reason)
            except Exception:
                log.warning("failed to use isolation result for %s", asset_id, exc_info=True)

        # Fallback: local rembg cutout of the original (handles pre-cut PNGs too).
        return self._finalize_local(asset_id, original_path)

    def _finalize_local(self, asset_id: str, original_path: Path) -> PreparedImage:
        """Fallback when Runflow is unavailable: rembg cutout of the source image."""
        from PIL import Image, ImageOps

        with Image.open(original_path) as raw:
            raw = ImageOps.exif_transpose(raw)
            if _transparent_fraction(raw) >= _TRANSPARENT_FRACTION:
                cutout = raw.convert("RGBA")
                route = "local-passthrough"
            else:
                cutout = _rembg_cutout(raw, _CUTOUT_MODEL)
                ok, reason = validate_cutout(cutout)
                route = "local-rembg"
                if not ok:
                    cutout = raw.convert("RGBA")
                    route = f"local-rembg-fallback({reason})"
            cutout = _trim_transparent(cutout)
            normalized_path = self._save_normalized(cutout, asset_id)
        return self._prepared(asset_id, original_path, normalized_path, route, normalized=True)

    def _prepared(
        self,
        asset_id: str,
        original_path: Path,
        normalized_path: Path,
        route: str,
        *,
        normalized: bool,
    ) -> PreparedImage:
        return PreparedImage(
            source_path=original_path,
            original_path=original_path,
            normalized_path=normalized_path,
            info=inspect_image(normalized_path),
            normalized=normalized,
            route=route,
        )

    def _save_normalized(self, img: "PIL.Image.Image", asset_id: str) -> Path:
        self.normalized_dir.mkdir(parents=True, exist_ok=True)
        dest = self.normalized_dir / f"{asset_id}.png"
        if img.mode != "RGBA":
            img = img.convert("RGBA")
        img.save(dest, format="PNG")
        return dest

    # ── downloads ────────────────────────────────────────────────────────────

    def _download_original(self, image_url: str, asset_id: str) -> Path:
        """Download a source image into originals/ with a sensible extension."""
        self.originals_dir.mkdir(parents=True, exist_ok=True)
        request = Request(image_url, headers={"User-Agent": "affiliate-outfits/0.1"})
        with urlopen(request, timeout=30) as response:
            content_type = response.headers.get("Content-Type", "")
            payload = response.read(10_000_001)
        if len(payload) > 10_000_000:
            raise ValueError(f"image download exceeded 10MB: {image_url}")
        ext = _image_extension(image_url, content_type)
        dest = self.originals_dir / f"{asset_id}{ext}"
        dest.write_bytes(payload)
        return dest

    def download_image(
        self,
        image_url: str,
        *,
        asset_id: str,
        max_bytes: int = 10_000_000,
        timeout_seconds: int = 30,
    ) -> Path:
        self.downloads_dir.mkdir(parents=True, exist_ok=True)
        request = Request(image_url, headers={"User-Agent": "affiliate-outfits/0.1"})
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

    # ── local file path (used by placeholders & tests) ───────────────────────

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


# ── classification ──────────────────────────────────────────────────────────────

def classify_image(path: Path) -> Classification:
    """Decide how an image should be routed. Local, no network calls."""
    from PIL import Image, ImageOps

    with Image.open(path) as img:
        img = ImageOps.exif_transpose(img)

        transparent_fraction = _transparent_fraction(img)
        if transparent_fraction >= _TRANSPARENT_FRACTION:
            return Classification(
                ImageClass.ALREADY_CUTOUT,
                transparent_fraction=transparent_fraction,
            )

        rgb = img.convert("RGB")
        edge_whiteness = _edge_whiteness(rgb)
        human_fraction = _human_fraction(rgb)

    if human_fraction >= _MODEL_HUMAN_FRACTION:
        image_class = ImageClass.MODEL_SHOT
    else:
        image_class = ImageClass.PRODUCT

    return Classification(
        image_class=image_class,
        human_fraction=human_fraction,
        transparent_fraction=transparent_fraction,
        edge_whiteness=edge_whiteness,
    )


def _human_fraction(rgb_image: "PIL.Image.Image") -> float:
    """Fraction of the image occupied by a human, via u2net_human_seg mask."""
    try:
        import numpy as np
        from rembg import remove
        from PIL import Image

        small = rgb_image.copy()
        small.thumbnail((_CLASSIFY_MAX_EDGE, _CLASSIFY_MAX_EDGE), Image.LANCZOS)
        mask = remove(small, session=_get_session(_HUMAN_SEG_MODEL), only_mask=True)
        arr = np.asarray(mask.convert("L"))
        if arr.size == 0:
            return 0.0
        return float((arr > 128).sum()) / float(arr.size)
    except Exception:
        log.warning("human segmentation failed — assuming no model", exc_info=True)
        return 0.0


def _transparent_fraction(img: "PIL.Image.Image") -> float:
    if "A" not in img.getbands():
        return 0.0
    try:
        import numpy as np

        alpha = np.asarray(img.convert("RGBA").getchannel("A"))
        if alpha.size == 0:
            return 0.0
        return float((alpha < 10).sum()) / float(alpha.size)
    except Exception:
        return 0.0


def _edge_whiteness(rgb_image: "PIL.Image.Image") -> float:
    """Fraction of 1px border pixels that are near-white (bg signal, for logging)."""
    try:
        import numpy as np

        arr = np.asarray(rgb_image)
        if arr.ndim != 3 or arr.shape[0] < 3 or arr.shape[1] < 3:
            return 0.0
        edges = np.concatenate([
            arr[0, :, :], arr[-1, :, :], arr[:, 0, :], arr[:, -1, :]
        ])
        near_white = np.all(edges > 230, axis=1)
        return float(near_white.sum()) / float(len(edges))
    except Exception:
        return 0.0


# ── cutout + validation ─────────────────────────────────────────────────────────

def _rembg_cutout(image: "PIL.Image.Image", model: str) -> "PIL.Image.Image":
    """Remove background with rembg, returning an RGBA image."""
    try:
        from rembg import remove

        result = remove(image.convert("RGB"), session=_get_session(model))
        return result.convert("RGBA")
    except Exception:
        log.warning("rembg cutout failed — returning source", exc_info=True)
        return image.convert("RGBA")


def validate_cutout(img: "PIL.Image.Image") -> tuple[bool, str]:
    """Reject blank, near-empty, or all-black cutouts. Returns (ok, reason)."""
    try:
        import numpy as np

        rgba = np.asarray(img.convert("RGBA"))
        alpha = rgba[:, :, 3]
        total = alpha.size
        if total == 0:
            return False, "empty"
        visible_mask = alpha > 10
        visible_fraction = visible_mask.sum() / total
        if visible_fraction < _MIN_VISIBLE_FRACTION:
            return False, "blank"
        visible_rgb = rgba[visible_mask][:, :3]
        if len(visible_rgb) and visible_rgb.mean() < _MIN_VISIBLE_BRIGHTNESS:
            return False, "black"
        return True, "ok"
    except Exception:
        return True, "unchecked"


def validate_runflow_result(img: "PIL.Image.Image") -> tuple[bool, str]:
    """Sanity-check a Runflow model-removal result before trusting it."""
    try:
        import numpy as np

        rgb = np.asarray(img.convert("RGB"))
        if rgb.size == 0:
            return False, "empty"
        if rgb.mean() < _MIN_VISIBLE_BRIGHTNESS:
            return False, "mostly-black"
        # If it came back fully transparent, model removal produced nothing usable.
        if "A" in img.getbands():
            alpha = np.asarray(img.getchannel("A"))
            if (alpha > 10).sum() / alpha.size < _MIN_VISIBLE_FRACTION:
                return False, "blank"
        return True, "ok"
    except Exception:
        return True, "unchecked"


def _trim_transparent(img: "PIL.Image.Image", pad: int = _TRIM_PADDING) -> "PIL.Image.Image":
    """Crop to the alpha bounding box with a little padding (tighter collage tiles)."""
    try:
        if img.mode != "RGBA":
            return img
        bbox = img.getchannel("A").getbbox()
        if not bbox:
            return img
        left, top, right, bottom = bbox
        left = max(0, left - pad)
        top = max(0, top - pad)
        right = min(img.width, right + pad)
        bottom = min(img.height, bottom + pad)
        return img.crop((left, top, right, bottom))
    except Exception:
        return img


# ── threading helper ─────────────────────────────────────────────────────────────

def _run_threads(fn, arg_tuples) -> None:
    """Run fn(*args) for each tuple in parallel and join. Exceptions are swallowed
    by callers' own try/except; this only manages thread lifecycle."""
    threads = [threading.Thread(target=fn, args=args) for args in arg_tuples]
    for t in threads:
        t.start()
    for t in threads:
        t.join()


# ── Runflow API ──────────────────────────────────────────────────────────────────

def _runflow_isolation_submit(
    image_url: str, *, prompt: str | None, api_key: str
) -> str | None:
    """Submit a product-isolation run; return run_id or None. Prompt is optional."""
    try:
        input_payload: dict = {
            "image_url": image_url,
            "resolution": _RUNFLOW_RESOLUTION,
            "aspect_ratio": _RUNFLOW_ASPECT_RATIO,
        }
        if prompt:
            input_payload["prompt"] = prompt
        payload = json.dumps({"input": input_payload}).encode()
        req = Request(
            _RUNFLOW_ISOLATION_URL,
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
            log.warning("Runflow isolation: no run_id in response: %s", run)
        return run_id
    except Exception:
        log.exception("Runflow isolation submit error for %s", image_url)
        return None


def _runflow_submit(image_url: str, *, api_key: str) -> str | None:
    """Submit a model-removal run and return the run_id (legacy/fallback)."""
    try:
        payload = json.dumps({
            "input": {"image_url": image_url, "config": {}},
        }).encode()
        req = Request(
            _RUNFLOW_MODEL_REMOVAL_URL,
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
        return run_id
    except Exception:
        log.exception("Runflow submit error for %s", image_url)
        return None


def _runflow_poll(run_id: str, *, api_key: str) -> str | None:
    """Poll a single run_id until done. Returns result URL or None."""
    deadline = time.time() + _RUNFLOW_TIMEOUT
    while time.time() < deadline:
        time.sleep(_RUNFLOW_POLL_INTERVAL)
        try:
            req = Request(
                f"{_RUNFLOW_POLL_URL}/{run_id}",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            with urlopen(req, timeout=15) as resp:
                run = json.loads(resp.read())
            status = run.get("status_code")
            if status == "succeeded":
                return _extract_runflow_image(run)
            if status in ("failed", "cancelled"):
                log.warning("Runflow run %s: %s", run_id, status)
                return None
        except Exception:
            log.exception("Runflow poll error for run %s", run_id)
            return None
    log.warning("Runflow run %s timed out after %ds", run_id, _RUNFLOW_TIMEOUT)
    return None


def runflow_process_batch(image_urls: list[str], *, api_key: str) -> list[str | None]:
    """Submit all images in parallel, then poll all together. Same order out."""
    run_ids: list[str | None] = [None] * len(image_urls)
    results: list[str | None] = [None] * len(image_urls)

    def submit(i: int, url: str) -> None:
        run_ids[i] = _runflow_submit(url, api_key=api_key)

    _run_threads(submit, list(enumerate(image_urls)))

    def poll(i: int, run_id: str) -> None:
        results[i] = _runflow_poll(run_id, api_key=api_key)

    _run_threads(poll, [(i, rid) for i, rid in enumerate(run_ids) if rid])
    return results


def _extract_runflow_image(run: dict) -> str | None:
    output = run.get("output") or {}
    urls = output.get("image_urls") or []
    for url in urls:
        if "final_result" in url:
            return url
    return urls[0] if urls else None


# ── legacy single-file normalize (placeholders, tests, prepare_local_image) ──────

def normalize_image(source_path: Path, destination_path: Path) -> tuple[Path, bool]:
    """Normalize + background-remove a local image with rembg, saving as PNG."""
    try:
        from PIL import Image, ImageOps
    except ImportError:
        shutil.copy2(source_path, destination_path)
        return destination_path, False

    with Image.open(source_path) as image:
        image = ImageOps.exif_transpose(image)
        if image.mode not in {"RGB", "RGBA"}:
            image = image.convert("RGBA" if "A" in image.mode else "RGB")

        cutout = _rembg_cutout(image, _CUTOUT_MODEL)
        ok, _ = validate_cutout(cutout)
        if not ok:
            cutout = image.convert("RGBA")
        cutout = _trim_transparent(cutout)
        destination_path = destination_path.with_suffix(".png")
        cutout.save(destination_path, format="PNG")

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
