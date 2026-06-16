from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.config import Settings, load_settings
from app.services.json_response import parse_json_response


class JSONLLMService(Protocol):
    def request_json(self, prompt: "LLMPrompt") -> dict:
        ...


@dataclass(frozen=True)
class LLMPrompt:
    title: str
    body: str
    system: str = "You are a careful fashion content agent. Return only valid JSON."


class ClaudeJSONService:
    def __init__(
        self,
        settings: Settings | None = None,
        *,
        model: str | None = None,
        thinking_budget: int | None = None,
    ) -> None:
        self.settings = settings or load_settings()
        if not self.settings.anthropic_api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY is required for AI agents. Add it to affiliate_outfits/.env."
            )
        self._model = model or self.settings.anthropic_model
        self._thinking_budget = thinking_budget

    def request_json(self, prompt: LLMPrompt) -> dict:
        try:
            from anthropic import Anthropic
        except ImportError as exc:
            raise RuntimeError(
                "The anthropic package is not installed. Run: python -m pip install -e '.[all]'"
            ) from exc

        client = Anthropic(api_key=self.settings.anthropic_api_key)

        kwargs: dict = dict(
            model=self._model,
            max_tokens=16000 if self._thinking_budget else 4096,
            system=prompt.system,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"{prompt.body}\n\n"
                        "Return only a valid JSON object. Do not include markdown fences, "
                        "commentary, or explanatory text outside the JSON."
                    ),
                }
            ],
        )
        if self._thinking_budget:
            kwargs["thinking"] = {"type": "enabled", "budget_tokens": self._thinking_budget}

        response = client.messages.create(**kwargs)

        stop_reason = getattr(response, "stop_reason", None)
        if stop_reason == "max_tokens":
            raise RuntimeError("Claude response hit max_tokens before completing JSON")

        output_text = _message_text(response)
        return parse_json_response(output_text)


def _message_text(response: object) -> str:
    blocks = getattr(response, "content", [])
    texts: list[str] = []
    for block in blocks:
        if getattr(block, "type", None) == "text":
            texts.append(getattr(block, "text", ""))
    return "\n".join(texts).strip()
