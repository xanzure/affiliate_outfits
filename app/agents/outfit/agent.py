from __future__ import annotations

from typing import Any

from app.agents.outfit.parser import normalize_outfit_agent_output, normalize_outfit_agent_outputs
from app.agents.outfit.prompt_builder import build_outfit_prompt
from app.services.llm_service import ClaudeJSONService, JSONLLMService, LLMPrompt


def generate_outfit_with_llm(
    brief: dict[str, Any],
    history: list[dict[str, Any]] | None = None,
    *,
    llm_service: JSONLLMService | None = None,
) -> dict[str, Any]:
    service = llm_service or ClaudeJSONService()
    prompt = LLMPrompt(
        title="Outfit Agent",
        body=build_outfit_prompt(brief, history or []),
        system="You are the Outfit Agent. Return only valid JSON matching the requested outfit schema.",
    )
    return normalize_outfit_agent_output(service.request_json(prompt))


def generate_outfit_batch_with_llm(
    brief: dict[str, Any],
    history: list[dict[str, Any]] | None = None,
    *,
    outfit_count: int,
    llm_service: JSONLLMService | None = None,
) -> list[dict[str, Any]]:
    service = llm_service or ClaudeJSONService()
    prompt = LLMPrompt(
        title=f"Outfit Agent: {outfit_count} Outfit Batch",
        body=build_outfit_prompt(brief, history or [], outfit_count=outfit_count),
        system=(
            "You are the Outfit Agent. Return only valid JSON with an 'outfits' array "
            f"containing exactly {outfit_count} objects matching the requested outfit schema."
        ),
    )
    return normalize_outfit_agent_outputs(service.request_json(prompt), expected_count=outfit_count)
