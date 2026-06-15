from __future__ import annotations

from dataclasses import dataclass
from typing import Any


REQUIRED_BRIEF_FIELDS = ("seed",)
LIST_BRIEF_FIELDS = (
    "context_notes",
    "style_cues",
    "color_cues",
    "required_considerations",
    "avoid",
)


@dataclass(frozen=True)
class CreativeBrief:
    seed: str
    payload: dict[str, Any]


def validate_brief(brief: dict[str, Any]) -> None:
    if not isinstance(brief, dict):
        raise ValueError("creative brief must be a JSON object")

    for field in REQUIRED_BRIEF_FIELDS:
        value = brief.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"creative brief field '{field}' must be a non-empty string")

    for field in LIST_BRIEF_FIELDS:
        value = brief.get(field, [])
        if not isinstance(value, list):
            raise ValueError(f"creative brief field '{field}' must be a list")
        if not all(isinstance(item, str) for item in value):
            raise ValueError(f"creative brief field '{field}' must contain only strings")


def normalize_brief(brief: dict[str, Any]) -> CreativeBrief:
    validate_brief(brief)
    normalized = dict(brief)
    normalized["seed"] = normalized["seed"].strip()

    for field in LIST_BRIEF_FIELDS:
        normalized[field] = [item.strip() for item in normalized.get(field, []) if item.strip()]

    return CreativeBrief(seed=normalized["seed"], payload=normalized)


def brief_from_concept_metadata(seed: str, metadata: dict[str, Any]) -> dict[str, Any]:
    brief = metadata.get("brief")
    if isinstance(brief, dict):
        return brief
    return {"seed": seed}
