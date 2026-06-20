from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass
from pathlib import Path


SUPPORTED_IMAGE_TYPES = {"png", "jpeg", "gif", "webp"}


@dataclass(frozen=True)
class ImageInfo:
    path: Path
    image_type: str
    width: int
    height: int
    size_bytes: int


def _sniff_image_type(data: bytes) -> str | None:
    """Detect image type from magic bytes (replaces removed imghdr module)."""
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:2] == b"\xff\xd8":
        return "jpeg"
    if data[:6] in {b"GIF87a", b"GIF89a"}:
        return "gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def inspect_image(path: Path) -> ImageInfo:
    if not path.exists():
        raise FileNotFoundError(path)
    if not path.is_file():
        raise ValueError(f"image path is not a file: {path}")

    data = path.read_bytes()
    image_type = _sniff_image_type(data)
    if image_type not in SUPPORTED_IMAGE_TYPES:
        raise ValueError(f"unsupported image type for {path}: {image_type}")

    width, height = _dimensions_from_bytes(data, image_type)
    if width < 1 or height < 1:
        raise ValueError(f"invalid image dimensions for {path}: {width}x{height}")

    return ImageInfo(
        path=path,
        image_type=image_type,
        width=width,
        height=height,
        size_bytes=path.stat().st_size,
    )


def read_image_dimensions(path: Path, image_type: str | None = None) -> tuple[int, int]:
    data = path.read_bytes()
    image_type = image_type or _sniff_image_type(data)
    if image_type == "jpg":
        image_type = "jpeg"
    return _dimensions_from_bytes(data, image_type)


def _dimensions_from_bytes(data: bytes, image_type: str | None) -> tuple[int, int]:
    if image_type == "png":
        return _png_dimensions(data)
    if image_type == "jpeg":
        return _jpeg_dimensions(data)
    if image_type == "gif":
        return _gif_dimensions(data)
    if image_type == "webp":
        return _webp_dimensions(data)

    raise ValueError(f"cannot read dimensions for image type: {image_type}")


def ensure_min_dimensions(info: ImageInfo, *, min_width: int, min_height: int) -> None:
    if info.width < min_width or info.height < min_height:
        raise ValueError(
            f"image too small: {info.path} is {info.width}x{info.height}, "
            f"expected at least {min_width}x{min_height}"
        )


def safe_image_filename(source: Path, *, suffix: str = "") -> str:
    stem = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in source.stem)
    stem = "-".join(part for part in stem.split("-") if part)
    extension = source.suffix.lower() or ".img"
    return f"{stem}{suffix}{extension}"


def write_solid_png(path: Path, *, width: int, height: int, rgb: tuple[int, int, int]) -> Path:
    if width < 1 or height < 1:
        raise ValueError("PNG width and height must be positive")
    if any(channel < 0 or channel > 255 for channel in rgb):
        raise ValueError("PNG RGB channels must be between 0 and 255")

    path.parent.mkdir(parents=True, exist_ok=True)
    raw_rows = b"".join(b"\x00" + bytes(rgb) * width for _ in range(height))
    compressed = zlib.compress(raw_rows)
    png = (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + _png_chunk(b"IDAT", compressed)
        + _png_chunk(b"IEND", b"")
    )
    path.write_bytes(png)
    return path


def _png_dimensions(data: bytes) -> tuple[int, int]:
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("invalid PNG data")
    return struct.unpack(">II", data[16:24])


def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    checksum = zlib.crc32(chunk_type + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", checksum)


def _gif_dimensions(data: bytes) -> tuple[int, int]:
    if len(data) < 10 or data[:6] not in {b"GIF87a", b"GIF89a"}:
        raise ValueError("invalid GIF data")
    return struct.unpack("<HH", data[6:10])


def _jpeg_dimensions(data: bytes) -> tuple[int, int]:
    if len(data) < 4 or data[:2] != b"\xff\xd8":
        raise ValueError("invalid JPEG data")

    index = 2
    while index < len(data):
        while index < len(data) and data[index] == 0xFF:
            index += 1
        if index >= len(data):
            break

        marker = data[index]
        index += 1
        if marker in {0xD8, 0xD9}:
            continue
        if index + 2 > len(data):
            break

        segment_length = struct.unpack(">H", data[index : index + 2])[0]
        if segment_length < 2:
            raise ValueError("invalid JPEG segment")

        if marker in {
            0xC0,
            0xC1,
            0xC2,
            0xC3,
            0xC5,
            0xC6,
            0xC7,
            0xC9,
            0xCA,
            0xCB,
            0xCD,
            0xCE,
            0xCF,
        }:
            start = index + 2
            if start + 5 > len(data):
                break
            height, width = struct.unpack(">HH", data[start + 1 : start + 5])
            return width, height

        index += segment_length

    raise ValueError("could not find JPEG dimensions")


def _webp_dimensions(data: bytes) -> tuple[int, int]:
    if len(data) < 30 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        raise ValueError("invalid WebP data")

    chunk_type = data[12:16]
    if chunk_type == b"VP8X":
        width = 1 + int.from_bytes(data[24:27], "little")
        height = 1 + int.from_bytes(data[27:30], "little")
        return width, height

    if chunk_type == b"VP8 ":
        if len(data) < 30:
            raise ValueError("invalid VP8 WebP data")
        width = struct.unpack("<H", data[26:28])[0] & 0x3FFF
        height = struct.unpack("<H", data[28:30])[0] & 0x3FFF
        return width, height

    if chunk_type == b"VP8L":
        if len(data) < 25:
            raise ValueError("invalid VP8L WebP data")
        bits = int.from_bytes(data[21:25], "little")
        width = (bits & 0x3FFF) + 1
        height = ((bits >> 14) & 0x3FFF) + 1
        return width, height

    raise ValueError(f"unsupported WebP chunk type: {chunk_type!r}")
