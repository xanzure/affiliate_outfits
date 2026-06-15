from __future__ import annotations

from typing import Any

from app.agents.engagement.templates import build_engagement_prompt
from app.services.llm_service import ClaudeJSONService, JSONLLMService, LLMPrompt


def generate_engagement_with_llm(
    brief: dict[str, Any],
    outfit: dict[str, Any],
    products: list[dict[str, Any]],
    *,
    llm_service: JSONLLMService | None = None,
) -> dict[str, Any]:
    service = llm_service or ClaudeJSONService()
    prompt = LLMPrompt(
        title="Engagement Agent",
        body=build_engagement_prompt(brief, outfit, products),
        system="You are the Engagement Agent. Return only valid JSON matching the requested engagement schema.",
    )
    return service.request_json(prompt)
