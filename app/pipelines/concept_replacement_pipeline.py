from __future__ import annotations

import sqlite3
from typing import Any

from app.agents.prompt.agent import generate_replacement_concept_with_llm
from app.db.concepts import create_concept, get_concept, list_active_concepts
from app.db.models import Concept
from app.services.llm_service import JSONLLMService


REQUIRED_REPLACEMENT_FIELDS = (
    "seed",
    "subject",
    "occasion",
    "context_notes",
    "style_cues",
    "required_considerations",
    "avoid",
)


def create_replacement_concept(
    conn: sqlite3.Connection,
    *,
    retired_concept_id: str,
    replacement_brief: dict[str, Any] | None = None,
    user_notes: str | None = None,
    llm_service: JSONLLMService | None = None,
) -> Concept:
    retired_concept = get_concept(conn, retired_concept_id)
    if retired_concept.status != "retired":
        raise ValueError(f"concept {retired_concept_id} must be retired before replacement")

    active_concepts = list_active_concepts(conn)
    brief = replacement_brief
    if brief is None:
        brief = generate_replacement_concept_with_llm(
            retired_concept=retired_concept,
            active_concepts=active_concepts,
            user_notes=user_notes,
            llm_service=llm_service,
        )

    normalized_brief = normalize_replacement_brief(brief)
    return create_concept(
        conn,
        normalized_brief["seed"],
        source="replacement",
        status="needs_review",
        ranking_score=50,
        metadata={
            "brief_schema_version": 1,
            "brief": normalized_brief,
            "replaces_concept_id": retired_concept.id,
            "replacement_source": "prompt_agent",
        },
    )


def normalize_replacement_brief(brief: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(brief, dict):
        raise ValueError("replacement concept response must be a JSON object")

    normalized: dict[str, Any] = {}
    for field in REQUIRED_REPLACEMENT_FIELDS:
        value = brief.get(field)
        if field in {"seed", "subject", "occasion"}:
            normalized[field] = _require_string(value, field)
        elif field in {"context_notes", "style_cues", "required_considerations", "avoid"}:
            normalized[field] = _require_string_list(value, field)

    color_cues = brief.get("color_cues", [])
    normalized["color_cues"] = _require_string_list(color_cues, "color_cues", allow_empty=True)
    return normalized


def _require_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"replacement concept field '{field}' must be a non-empty string")
    return value.strip()


def _require_string_list(value: Any, field: str, *, allow_empty: bool = False) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"replacement concept field '{field}' must be a list of strings")

    items = [item.strip() for item in value if isinstance(item, str) and item.strip()]
    if not allow_empty and not items:
        raise ValueError(f"replacement concept field '{field}' must include at least one string")
    if len(items) != len(value):
        raise ValueError(f"replacement concept field '{field}' must only contain non-empty strings")
    return items
