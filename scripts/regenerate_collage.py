from __future__ import annotations

try:
    from _bootstrap import add_project_root_to_path
except ModuleNotFoundError:
    from scripts._bootstrap import add_project_root_to_path

add_project_root_to_path()

import argparse
from pathlib import Path

from app.agents.collage.renderer import render_deterministic_collage
from app.utils.logging import configure_logging, get_logger


def main() -> None:
    parser = argparse.ArgumentParser(description="Render a deterministic collage from local images.")
    parser.add_argument("output", type=Path, help="Output image path.")
    parser.add_argument("images", type=Path, nargs="+", help="Input image paths.")
    args = parser.parse_args()

    configure_logging()
    logger = get_logger(__name__)
    output_path = render_deterministic_collage(args.images, args.output)
    logger.info("rendered collage: %s", output_path)


if __name__ == "__main__":
    main()
