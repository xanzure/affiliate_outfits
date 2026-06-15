# AI Agents

AI agents are API-backed by default.

The current provider is Anthropic Claude through the Messages API. Agents request JSON output, then deterministic validators check the response shape before the pipeline continues.

## Required Environment

Add these values to `.env`:

```env
AI_PROVIDER=anthropic
AI_MODE=claude
ANTHROPIC_MODEL=claude-haiku-4-5
ANTHROPIC_API_KEY=your_api_key_here
```

`ANTHROPIC_API_KEY` is the only required secret for the current agent layer.

## Agents

- Outfit Agent: generates five distinct outfits for the selected concept.
- Engagement Agent: generates one TikTok slideshow caption and five Pinterest entries.
- Prompt Agent: generates replacement concepts when a concept retires.

The collage layer is deterministic for now. It renders the image and stores a structured layout manifest in the database for website recreation.

## Saved Responses

The scripts still accept saved JSON response files for tests and debugging:

```bash
python3 scripts/run_daily.py --outfit-response-file data/llm_responses/sample_outfit_response.json --engagement-response-file data/llm_responses/sample_engagement_response.json
```

Saved files bypass API calls, but normal runs use the configured Claude model.
