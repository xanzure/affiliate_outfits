from __future__ import annotations

from dataclasses import dataclass
from math import ceil


@dataclass(frozen=True)
class Canvas:
    width: int = 1080
    height: int = 1350
    background_rgb: tuple[int, int, int] = (248, 246, 240)
    padding: int = 80
    gap: int = 32


@dataclass(frozen=True)
class Placement:
    index: int
    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True)
class CollageLayout:
    canvas: Canvas
    placements: list[Placement]


def layout_to_dict(layout: CollageLayout) -> dict:
    return {
        "canvas": {
            "width": layout.canvas.width,
            "height": layout.canvas.height,
            "background_rgb": list(layout.canvas.background_rgb),
            "padding": layout.canvas.padding,
            "gap": layout.canvas.gap,
        },
        "placements": [
            {
                "index": placement.index,
                "x": placement.x,
                "y": placement.y,
                "width": placement.width,
                "height": placement.height,
            }
            for placement in layout.placements
        ],
    }


def fixed_grid_layout(item_count: int, *, canvas: Canvas | None = None) -> CollageLayout:
    if item_count < 1:
        raise ValueError("item_count must be at least 1")

    canvas = canvas or Canvas()
    columns = 1 if item_count == 1 else 2
    rows = ceil(item_count / columns)

    available_width = canvas.width - (canvas.padding * 2) - (canvas.gap * (columns - 1))
    available_height = canvas.height - (canvas.padding * 2) - (canvas.gap * (rows - 1))
    cell_width = available_width // columns
    cell_height = available_height // rows

    placements: list[Placement] = []
    for index in range(item_count):
        row = index // columns
        column = index % columns
        x = canvas.padding + column * (cell_width + canvas.gap)
        y = canvas.padding + row * (cell_height + canvas.gap)
        placements.append(
            Placement(
                index=index,
                x=x,
                y=y,
                width=cell_width,
                height=cell_height,
            )
        )

    return CollageLayout(canvas=canvas, placements=placements)
