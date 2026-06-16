from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from typing import Any

from app.services.llm_service import ClaudeJSONService, LLMPrompt


@dataclass(frozen=True)
class BatchVisualStyle:
    background_hex: str
    accent_hex: str
    font_style: str  # "sans" | "serif"
    palette_name: str = ""


_STYLE_SYSTEM = (
    "You are an editorial fashion art director with refined, restrained taste. "
    "Return only valid JSON. No markdown, no commentary."
)

_STYLE_PROMPT = """
Choose a visual style for a fashion collage. The palette must feel editorial — like a magazine
spread or a high-end lookbook, not a social media graphic or a rave flyer.

Concept: "{concept_seed}"
Today: {date} — use this for natural day-to-day variation across batches.

## Design Rules (non-negotiable)
- Backgrounds must be MUTED and WARM or NEUTRAL. Think cream, linen, sand, warm white,
  dusty rose, soft sage, warm charcoal, deep ink. Never electric, neon, or saturated.
- Accents must be TASTEFUL and HIGH-CONTRAST against the background but still editorial.
  Think navy, warm red, deep forest, rust, stone, near-black, deep burgundy.
  Never cyan, never lime, never hot pink, never electric purple.
- Do not use pure white (#ffffff) or pure black (#000000) as background.
- The palette should feel like it belongs in a printed fashion magazine, not on a concert poster.
- font_style: "serif" for anything classic, dark, formal, old money, academic.
  "sans" for modern, streetwear, resort, clean, Y2K.

## Concept-to-Palette Reference
These are starting points — vary slightly by date for freshness, but stay in the same family.
Think about what the concept actually LOOKS and FEELS like before choosing colors.

Bad Bunny concert
  → His aesthetic: Caribbean heat, Latin trap, Un Verano Sin Ti era — warm, tropical, intimate
  → NOT neon, NOT electric. Think open-air festival at golden hour, not a rave.
  → warm sand (#EDE0CA) + deep warm terracotta-red (#9B3A2A), sans
  → variation: dusty warm peach (#E8D5BA) + deep espresso brown (#2C1A0E), sans

Dark Academia
  → libraries, Oxford courtyards, candle smoke, worn leather — hushed and warm
  → deep warm ink (#1A1814) + aged parchment (#C8B89A), serif
  → variation: dark tobacco brown (#1E1610) + worn ivory (#D4C9A8), serif

Old Money
  → Nantucket docks, cashmere, WASP restraint — nothing loud, nothing trying
  → soft ecru (#EDE9E0) + deep navy (#1A2744), serif
  → variation: warm oat (#E8E2D5) + deep bottle green (#1A3028), serif

Euro Summer
  → Amalfi cliffs, terracotta rooftops, linen in the afternoon heat — warm and sun-faded
  → warm linen (#E6D9C4) + deep terracotta (#7A3E28), sans
  → variation: dusty warm white (#EDE5D5) + deep olive (#3A3A1A), sans

Coastal / Nantucket
  → salt air, bleached wood, navy and white stripes seen from a distance — clean and quiet
  → bleached warm linen (#EBE6DA) + deep ocean navy (#1B3A52), serif
  → variation: pale driftwood (#E4DECE) + deep slate blue (#243B4A), serif

SoHo Summer
  → art galleries, cobblestone, iced coffee, expensive basics — clean but with edge
  → warm off-white (#F0EBE3) + warm near-black (#1E1C1A), sans
  → variation: soft warm grey (#E2DDD6) + deep warm charcoal (#2A2520), sans

Ibiza Beach Club
  → white villas, Mediterranean blue, warm stone, late afternoon gold — minimal and warm
  → warm stone white (#EDE5D5) + deep Mediterranean navy (#1A2E42), sans
  → variation: bleached warm sand (#E8DFC8) + deep muted cobalt (#1E3050), sans

Morgan Wallen Concert
  → Nashville, bourbon, stadium lights on denim, warm and American — gritty but romantic
  → aged warm cream (#EDE0C8) + deep bourbon brown (#3A2010), serif
  → variation: warm off-white (#EAE0CE) + deep denim indigo (#1C2A3A), serif

Return JSON:
{{
  "background_hex": "#RRGGBB",
  "accent_hex": "#RRGGBB",
  "font_style": "sans" | "serif",
  "palette_name": "short descriptive name (e.g. 'aged parchment', 'warm linen navy')"
}}
""".strip()


def generate_batch_visual_style(
    concept_seed: str,
    *,
    llm_service: ClaudeJSONService | None = None,
) -> BatchVisualStyle:
    service = llm_service or ClaudeJSONService()
    prompt = LLMPrompt(
        title="Collage Style Agent",
        body=_STYLE_PROMPT.format(
            concept_seed=concept_seed,
            date=date.today().isoformat(),
        ),
        system=_STYLE_SYSTEM,
    )
    data = service.request_json(prompt)
    return BatchVisualStyle(
        background_hex=_valid_hex(data.get("background_hex", "#1C1B18")),
        accent_hex=_valid_hex(data.get("accent_hex", "#D4C4A8")),
        font_style=data.get("font_style", "sans") if data.get("font_style") in {"sans", "serif"} else "sans",
        palette_name=str(data.get("palette_name", "")),
    )


def _valid_hex(value: Any) -> str:
    if isinstance(value, str) and value.startswith("#") and len(value) == 7:
        return value
    return "#1C1B18"
