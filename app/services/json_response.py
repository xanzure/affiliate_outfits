from __future__ import annotations

import json
from typing import Any


def parse_json_response(response: str) -> dict[str, Any]:
    text = response.strip()
    if not text:
        raise ValueError("LLM response was empty")

    if text.startswith("```"):
        text = _strip_fenced_code_block(text)

    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM response was not valid JSON: {exc}") from exc

    if not isinstance(value, dict):
        raise ValueError("LLM response JSON must be an object")

    return value


def _strip_fenced_code_block(text: str) -> str:
    lines = text.splitlines()
    if not lines:
        return text

    first = lines[0].strip()
    last = lines[-1].strip()
    if first.startswith("```") and last == "```":
        return "\n".join(lines[1:-1]).strip()

    return text
