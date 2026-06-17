import unittest

from app.agents.outfit.agent import generate_outfit_with_llm
from app.agents.outfit.prompt_builder import build_outfit_prompt
from app.services.json_response import parse_json_response


class FakeLLMService:
    def __init__(self, response: dict) -> None:
        self.response = response
        self.prompts = []

    def request_json(self, prompt):
        self.prompts.append(prompt)
        return self.response


class JsonLLMAgentTests(unittest.TestCase):
    def test_parse_json_response_accepts_raw_json_object(self) -> None:
        response = parse_json_response('{"outfit": {"title": "Concert look"}}')

        self.assertEqual(response["outfit"]["title"], "Concert look")

    def test_parse_json_response_accepts_fenced_json_object(self) -> None:
        response = parse_json_response(
            """
```json
{"outfit": {"title": "Concert look"}}
```
""".strip()
        )

        self.assertEqual(response["outfit"]["title"], "Concert look")

    def test_parse_json_response_rejects_arrays(self) -> None:
        with self.assertRaises(ValueError):
            parse_json_response("[]")

    def test_parse_json_response_rejects_invalid_json(self) -> None:
        with self.assertRaises(ValueError):
            parse_json_response("outfit: concert look")

    def test_outfit_prompt_preserves_brief_context(self) -> None:
        prompt = build_outfit_prompt(
            {
                "seed": "Bad Bunny summer concert outfit",
                "context_notes": ["Puerto Rican cultural references are relevant"],
            },
            [],
        )

        self.assertIn("Bad Bunny summer concert outfit", prompt)
        self.assertIn("Puerto Rican cultural references are relevant", prompt)
        self.assertIn("not a mood board dump", prompt)

    def test_outfit_agent_uses_llm_service(self) -> None:
        # Curator returns an `outfits` array; each outfit carries items + metadata.
        service = FakeLLMService(
            {
                "outfits": [
                    {
                        "title": "Summer concert streetwear",
                        "rationale": "Uses the artist and concert context.",
                        "primary_reference": "Bad Bunny",
                        "items": [
                            {
                                "role": "statement top",
                                "category": "top",
                                "color": "white",
                                "material": "cotton",
                                "search_query": "white concert streetwear top",
                                "use_cached_url": None,
                                "price_range": "mid",
                            }
                        ],
                    }
                ]
            }
        )

        result = generate_outfit_with_llm(
            {"seed": "Bad Bunny summer concert outfit"},
            llm_service=service,
        )

        self.assertEqual(result["interpretation"]["primary_reference"], "Bad Bunny")
        self.assertIn("Outfit Curator", service.prompts[0].title)


if __name__ == "__main__":
    unittest.main()
