import unittest

from app.agents.prompt.agent import (
    build_replacement_concept_prompt,
    generate_replacement_concept_with_llm,
)
from app.db.models import Concept


class FakeLLMService:
    def __init__(self, response: dict) -> None:
        self.response = response
        self.prompts = []

    def request_json(self, prompt):
        self.prompts.append(prompt)
        return self.response


def make_concept(concept_id: str, seed: str, status: str = "active") -> Concept:
    return Concept(
        id=concept_id,
        seed=seed,
        status=status,
        source="seed",
        usage_count=0,
        ranking_score=50,
        last_posted_date_est=None,
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
        metadata={"brief": {"seed": seed}},
    )


class PromptAgentTests(unittest.TestCase):
    def test_replacement_prompt_distinguishes_concepts_from_prompts(self) -> None:
        retired = make_concept("concept_retired", "Dark academia campus outfit", "retired")
        active = [make_concept("concept_active", "Bad Bunny summer concert outfit")]

        prompt = build_replacement_concept_prompt(
            retired_concept=retired,
            active_concepts=active,
            user_notes="lean into spring ideas",
        )

        self.assertIn("A concept is a rich creative brief", prompt)
        self.assertIn("It is not an LLM prompt", prompt)
        self.assertIn("Dark academia campus outfit", prompt)
        self.assertIn("Bad Bunny summer concert outfit", prompt)
        self.assertIn("lean into spring ideas", prompt)

    def test_generation_returns_json(self) -> None:
        retired = make_concept("concept_retired", "Dark academia campus outfit", "retired")
        service = FakeLLMService({"seed": "Rainy gallery outfit"})

        result = generate_replacement_concept_with_llm(
            retired_concept=retired,
            active_concepts=[],
            llm_service=service,
        )

        self.assertEqual(result["seed"], "Rainy gallery outfit")
        self.assertIn("Prompt Agent: Replacement Concept", service.prompts[0].title)


if __name__ == "__main__":
    unittest.main()
