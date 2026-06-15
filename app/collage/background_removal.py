from __future__ import annotations

import shutil
from pathlib import Path


def remove_background(
    source_path: Path,
    destination_path: Path,
    *,
    use_rembg: bool = True,
) -> tuple[Path, bool]:
    """Remove image background when a local remover is installed.

    The first implementation intentionally avoids paid APIs. If `rembg` is
    installed locally later, this function will use it. Until then it copies the
    source image unchanged and reports `False`.
    """

    if not use_rembg:
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination_path)
        return destination_path, False

    try:
        from rembg import remove
    except ImportError:
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination_path)
        return destination_path, False

    destination_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        output = remove(source_path.read_bytes())
    except Exception:
        shutil.copy2(source_path, destination_path)
        return destination_path, False

    if not output:
        shutil.copy2(source_path, destination_path)
        return destination_path, False

    destination_path.write_bytes(output)
    return destination_path, True
