from __future__ import annotations

import json
from typing import Any


def build_outfit_prompt(
    brief: dict[str, Any],
    history: list[dict[str, Any]],
    *,
    outfit_count: int = 1,
) -> str:
    schema_intro = (
        f'Return only valid JSON with an "outfits" array containing exactly {outfit_count} outfit objects. '
        "Each outfit object must use this shape:"
        if outfit_count > 1
        else "Return only valid JSON with this shape:"
    )
    wrapper_note = (
        f'\nWrap the outfit objects like this: {{"outfits": [ ... {outfit_count} total ... ]}}\n'
        if outfit_count > 1
        else ""
    )
    return f"""
You are helping generate a fashion outfit concept for an affiliate content pipeline.

Interpret the creative brief with nuance. Do not collapse people, places, songs,
artists, events, or cultural references into generic outfit labels.
Generate {outfit_count} distinct outfit{"s" if outfit_count != 1 else ""} for this one concept.

Creative brief:
{json.dumps(brief, indent=2, sort_keys=True)}

Previous related outfits:
{json.dumps(history, indent=2, sort_keys=True)}

{schema_intro}
{{
  "interpretation": {{
    "primary_reference": "non-empty brief reference being interpreted",
    "used_cues": ["non-empty cue strings used in the outfit"],
    "discarded_cues": ["cue strings intentionally not used, or []"],
    "rationale": "non-empty explanation of how the brief shaped the outfit"
  }},
  "outfit": {{
    "title": "non-empty outfit title",
    "categories": ["non-empty product categories such as top, bottom, shoe, accessory"],
    "colors": ["color strings, or []"],
    "materials": ["material strings, or []"],
    "accessories": ["accessory strings, or []"]
  }},
  "search_queries": [
    {{
      "query": "non-empty retailer search phrase that preserves brief nuance",
      "category": "optional category string",
      "limit": 1
    }}
  ],
  "diversity_notes": ["strings, or []"]
}}

Rules:
- Include at least one search query.
- Use query objects, not just labels, so deterministic product matching can continue.
- Keep each query product-searchable; do not write abstract descriptions only.
- Preserve brief-specific nuance in at least one search query or cue.
- The outfits must be meaningfully different from each other while still matching the same concept.
{wrapper_note}
""".strip()
