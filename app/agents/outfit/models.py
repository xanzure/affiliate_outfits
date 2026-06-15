from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OutfitSearchQuery:
    query: str
    category: str | None = None
    limit: int = 3


@dataclass(frozen=True)
class OutfitAgentSchema:
    required_top_level_fields: tuple[str, ...] = (
        "interpretation",
        "outfit",
        "search_queries",
        "diversity_notes",
    )
    required_interpretation_fields: tuple[str, ...] = (
        "primary_reference",
        "used_cues",
        "discarded_cues",
        "rationale",
    )
    required_outfit_fields: tuple[str, ...] = (
        "title",
        "categories",
        "colors",
        "materials",
        "accessories",
    )


OUTFIT_AGENT_SCHEMA = OutfitAgentSchema()
