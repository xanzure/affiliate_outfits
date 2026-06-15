from __future__ import annotations

import json
from typing import Any

from app.agents.prompt.history import replacement_history_payload
from app.db.models import Concept
from app.services.llm_service import ClaudeJSONService, JSONLLMService, LLMPrompt


REPLACEMENT_CONCEPT_SCHEMA = {
    "seed": "short human-readable concept name",
    "subject": "person, mood, event, place, or trend the concept is built around",
    "occasion": "posting/use context",
    "context_notes": ["specific references, cultural context, outfit-relevant nuance"],
    "style_cues": ["silhouettes, eras, fabrics, accessories, styling direction"],
    "color_cues": ["palette notes if relevant"],
    "required_considerations": ["must-preserve requirements for outfit generation"],
    "avoid": ["things the system should not do"],
}


def build_replacement_concept_prompt(
    *,
    retired_concept: Concept,
    active_concepts: list[Concept],
    user_notes: str | None = None,
) -> str:
    history = replacement_history_payload(
        retired_concept=retired_concept,
        active_concepts=active_concepts,
    )
    notes = user_notes.strip() if user_notes else "None."
    return f"""
You are the Prompt Agent for a deterministic-first affiliate fashion content engine.

Your job is to propose exactly one replacement content concept because one concept was retired.
A concept is a rich creative brief for future outfit generation. It is not an LLM prompt and it
must not collapse a nuanced idea into a generic outfit phrase.

The replacement should:
- Be distinct from active concepts.
- Have strong outfit potential for TikTok and Pinterest.
- Preserve useful nuance: visual references, cultural context where appropriate, colors,
  silhouettes, accessories, settings, eras, and styling constraints.
- Avoid stereotypes, costume-like styling, unsupported claims, or generic trend sludge.
- Be specific enough that the Outfit Agent can make product and styling decisions later.

User notes:
{notes}

Concept history:
{json.dumps(history, indent=2, sort_keys=True)}

Return one JSON object matching this schema:
{json.dumps(REPLACEMENT_CONCEPT_SCHEMA, indent=2, sort_keys=True)}
""".strip()


def generate_replacement_concept_with_llm(
    *,
    retired_concept: Concept,
    active_concepts: list[Concept],
    user_notes: str | None = None,
    llm_service: JSONLLMService | None = None,
) -> dict[str, Any]:
    service = llm_service or ClaudeJSONService()
    prompt = LLMPrompt(
        title="Prompt Agent: Replacement Concept",
        body=build_replacement_concept_prompt(
            retired_concept=retired_concept,
            active_concepts=active_concepts,
            user_notes=user_notes,
        ),
        system="You are the Prompt Agent. Return only valid JSON matching the replacement concept schema.",
    )
    return service.request_json(prompt)
