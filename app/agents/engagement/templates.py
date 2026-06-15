from __future__ import annotations

import json
from typing import Any


def build_engagement_prompt(
    brief: dict[str, Any],
    outfit: dict[str, Any],
    products: list[dict[str, Any]],
) -> str:
    is_batch = isinstance(outfit.get("outfits"), list)
    pinterest_shape = (
        '"pinterest_posts": [\n'
        '    {"title": "...", "description": "...", "hashtags": []}\n'
        "  ],"
        if is_batch
        else '"pinterest": {\n'
        '    "title": "...",\n'
        '    "description": "...",\n'
        '    "hashtags": []\n'
        "  },"
    )
    batch_note = (
        "\nThis is a five-outfit daily set. Write one TikTok caption for the full slideshow and "
        "one Pinterest title/description/hashtag set for each outfit, in outfit order.\n"
        if is_batch
        else ""
    )
    return f"""
You are helping create platform copy for an affiliate fashion content pipeline.

Write concise, natural engagement copy. Preserve the nuance of the creative
brief without overexplaining it. Avoid forced cultural references, stereotypes,
or unsupported claims.
{batch_note}

Creative brief:
{json.dumps(brief, indent=2, sort_keys=True)}

Outfit:
{json.dumps(outfit, indent=2, sort_keys=True)}

Products:
{json.dumps(products, indent=2, sort_keys=True)}

Return only valid JSON with this shape:
{{
  "tiktok": {{
    "caption": "...",
    "hashtags": [],
    "music_category": "..."
  }},
  {pinterest_shape}
  "notes": []
}}
""".strip()
