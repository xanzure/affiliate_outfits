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
You are an editorial fashion stylist curating affiliate content for a luxury fashion archive.

Your job: interpret the creative brief with precision and taste, then select a cohesive,
aesthetically sharp outfit. Think like a stylist at Acne Studios or Bottega Veneta —
quiet confidence, intentional choices, nothing generic.

Generate {outfit_count} distinct outfit{"s" if outfit_count != 1 else ""} for this concept.
Each must feel like a real editorial choice — not a mood board dump.

Creative brief:
{json.dumps(brief, indent=2, sort_keys=True)}

Previous outfits for this concept (do not repeat):
{json.dumps(history, indent=2, sort_keys=True)}

{schema_intro}
{{
  "interpretation": {{
    "primary_reference": "the specific cultural/aesthetic anchor you are styling around",
    "used_cues": ["specific cues from the brief that shaped this outfit"],
    "discarded_cues": ["cues intentionally skipped, or []"],
    "rationale": "why these pieces together — the story the outfit tells"
  }},
  "outfit": {{
    "title": "short editorial outfit title (max 6 words)",
    "categories": ["exact product types: e.g. wide-leg trousers, leather mule, oversized blazer"],
    "colors": ["specific color names: e.g. ecru, burnt sienna, slate, ivory"],
    "materials": ["material descriptors: e.g. linen, washed denim, suede, ribbed knit"],
    "accessories": ["specific accessories, or []"]
  }},
  "search_queries": [
    {{
      "query": "specific product search term — include material, color, silhouette, and retailer name where possible.",
      "category": "exact category string matching outfit.categories",
      "limit": 1
    }}
  ],
  "diversity_notes": ["how this outfit differs from the others in the batch, or []"]
}}

Rules:
- Every outfit must be COMPLETE: at minimum top + bottom + shoe. Accessories are optional but encouraged.
- Each search query must be highly specific. Bad: "black coat". Good: "oversized black wool coat women ASOS".
- Colors and materials must be specific — avoid "neutral" or "casual" as descriptors.
- The outfits must differ meaningfully in silhouette, color story, or mood — not just swap one piece.
- Do NOT choose generic items. Every piece should feel intentionally chosen for this specific concept.
{wrapper_note}
""".strip()
