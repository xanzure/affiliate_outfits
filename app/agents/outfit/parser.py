from __future__ import annotations

from typing import Any

from app.agents.outfit.models import OUTFIT_AGENT_SCHEMA


def normalize_outfit_agent_output(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize Outfit Agent JSON."""

    if not isinstance(payload, dict):
        raise ValueError("outfit agent response must be a JSON object")

    for field in OUTFIT_AGENT_SCHEMA.required_top_level_fields:
        if field not in payload:
            raise ValueError(f"outfit agent response missing required field '{field}'")

    interpretation = _normalize_interpretation(payload["interpretation"])
    outfit = _normalize_outfit(payload["outfit"])
    search_queries = _normalize_search_queries(payload["search_queries"])
    diversity_notes = _string_list(payload["diversity_notes"], "diversity_notes", allow_empty=True)

    result = {
        "interpretation": interpretation,
        "outfit": outfit,
        "search_queries": search_queries,
        "diversity_notes": diversity_notes,
    }
    # Preserve generator tags (collage template, style facet, gender presentation).
    for tag in ("template", "facet", "gender"):
        if payload.get(tag):
            result[tag] = payload[tag]
    return result


def normalize_outfit_agent_outputs(
    payload: dict[str, Any],
    *,
    expected_count: int,
) -> list[dict[str, Any]]:
    if expected_count < 1:
        raise ValueError("expected outfit count must be at least 1")

    if isinstance(payload, dict) and "outfits" in payload:
        items = payload["outfits"]
        if not isinstance(items, list):
            raise ValueError("outfit agent response field 'outfits' must be a list")
    else:
        items = [payload]

    if len(items) != expected_count:
        raise ValueError(
            f"outfit agent response must include exactly {expected_count} outfits; got {len(items)}"
        )

    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f"outfit agent response outfits[{index}] must be an object")
        normalized.append(normalize_outfit_agent_output(item))
    return normalized


def validate_outfit_agent_output(payload: dict[str, Any]) -> None:
    normalize_outfit_agent_output(payload)


def _normalize_interpretation(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("outfit agent field 'interpretation' must be an object")

    for field in OUTFIT_AGENT_SCHEMA.required_interpretation_fields:
        if field not in value:
            raise ValueError(f"outfit agent interpretation missing required field '{field}'")

    return {
        "primary_reference": _required_string(
            value["primary_reference"],
            "interpretation.primary_reference",
        ),
        "used_cues": _string_list(value["used_cues"], "interpretation.used_cues"),
        "discarded_cues": _string_list(
            value["discarded_cues"],
            "interpretation.discarded_cues",
            allow_empty=True,
        ),
        "rationale": _required_string(value["rationale"], "interpretation.rationale"),
    }


def _normalize_outfit(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("outfit agent field 'outfit' must be an object")

    for field in OUTFIT_AGENT_SCHEMA.required_outfit_fields:
        if field not in value:
            raise ValueError(f"outfit agent outfit missing required field '{field}'")

    return {
        "title": _required_string(value["title"], "outfit.title"),
        "categories": _string_list(value["categories"], "outfit.categories"),
        "colors": _string_list(value["colors"], "outfit.colors", allow_empty=True),
        "materials": _string_list(value["materials"], "outfit.materials", allow_empty=True),
        "accessories": _string_list(value["accessories"], "outfit.accessories", allow_empty=True),
    }


def _normalize_search_queries(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError("outfit agent field 'search_queries' must be a list")

    queries: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        field = f"search_queries[{index}]"
        if isinstance(item, str):
            queries.append({"query": _required_string(item, field), "category": None, "limit": 3})
            continue
        if not isinstance(item, dict):
            raise ValueError(f"outfit agent field '{field}' must be an object or string")

        query = _required_string(item.get("query"), f"{field}.query")
        category = item.get("category")
        if category is not None:
            category = _required_string(category, f"{field}.category")

        limit = item.get("limit", 3)
        if not isinstance(limit, int) or limit < 1 or limit > 10:
            raise ValueError(f"outfit agent field '{field}.limit' must be an integer from 1 to 10")

        queries.append({"query": query, "category": category, "limit": limit})

    if not queries:
        raise ValueError("outfit agent field 'search_queries' must include at least one query")
    return queries


def _required_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"outfit agent field '{field}' must be a non-empty string")
    return value.strip()


def _string_list(value: Any, field: str, *, allow_empty: bool = False) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"outfit agent field '{field}' must be a list of strings")

    items = [item.strip() for item in value if isinstance(item, str) and item.strip()]
    if len(items) != len(value):
        raise ValueError(f"outfit agent field '{field}' must contain only non-empty strings")
    if not allow_empty and not items:
        raise ValueError(f"outfit agent field '{field}' must include at least one string")
    return items
