# Affiliate Content Engine

Affiliate Content Engine is an autonomous content generation pipeline that creates fashion inspiration posts for TikTok and Pinterest using specialized AI agents and deterministic software pipelines.

The system is intentionally built as an engineering project rather than a no-code automation.

## Philosophy

- AI is only used for creative or subjective decisions.
- Everything else is conventional, deterministic software.
- Every stage should be independently testable and reproducible.
- The system optimizes concept performance over time using manually entered metrics.
- Components should be modular and replaceable.
- Creative concepts are rich briefs, not one-line outfit labels.
- Cultural references, personal style cues, colors, silhouettes, eras, places, and known looks should be preserved as structured context for the agents.
- The account should feel human-run: one concept per day, five outfits for that concept, one TikTok slideshow, and five spaced Pinterest posts.

## Core Pipeline

```text
Scheduler
  -> Outfit Agent
  -> Product Pipeline
  -> Collage Agent
  -> Engagement Agent
  -> Publisher
  -> Analytics
  -> Prompt Agent
```

See [docs/pipeline.md](docs/pipeline.md) for the detailed end-to-end workflow.

## Agents

### Outfit Agent

Responsible for:

- Interpreting creative briefs into nuanced outfit concepts
- Maintaining outfit diversity
- Selecting products
- Preserving important cultural, visual, and reference-specific details

### Collage Agent

Responsible for:

- Layout
- Composition
- Branding
- Visual consistency

### Engagement Agent

Responsible for:

- Captions
- Hashtags
- Music category
- Posting copy

### Prompt Agent

Responsible for:

- Generating new creative brief ideas
- Replacing retired concepts
- Maintaining the active creative brief pool

## Development Principles

- Deterministic whenever possible
- AI only for subjective decisions
- Modular architecture
- Reproducible outputs
- Easy local development
- Replaceable components
- Every module should have one responsibility, one input, one output, one test suite, and one interface
- Deterministic components should store and pass complete creative context; they should not collapse a nuanced brief into a generic outfit phrase.

## Creative Briefs

A concept in this system is a creative brief. It can start from a person, song, city, event, mood, aesthetic, trend, or shopping constraint, but it should keep the nuance needed for good outfit selection.

Example:

```json
{
  "seed": "Bad Bunny summer concert outfit",
  "subject": "Bad Bunny",
  "occasion": "summer concert",
  "context_notes": [
    "Puerto Rican cultural references are relevant",
    "Consider colors associated with Puerto Rico when tasteful",
    "Reference recognizable styling cues from recent public looks"
  ],
  "style_cues": [
    "streetwear",
    "playful proportion",
    "statement accessories",
    "warm-weather fabrics"
  ],
  "required_considerations": [
    "Do not reduce the brief to generic linen summer outfit",
    "Include at least one specific visual or cultural reference when product availability allows"
  ],
  "avoid": [
    "costume-like styling",
    "stereotypes",
    "unsupported claims about identity or meaning"
  ]
}
```

The Outfit Agent should transform that brief into structured clothing categories, search queries, and product choices. The deterministic layers should store and pass the full brief unchanged.

## Concept Scheduling

The system starts with 8 active concepts. Each concept starts with a ranking score of `50`.

Each day, the scheduler should select the single top-ranked active concept. Concepts posted today or within the previous two fixed-EST calendar days are skipped. The selected concept produces five outfits: one TikTok slideshow post and five Pinterest posts spaced through the day.

When a concept drops below `25`, it is retired and replaced through the Prompt Agent.

## Local Development

Everything should be runnable independently. Testing one part of the system should never require the entire pipeline.

Create and use the local Python environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip setuptools wheel
python -m pip install -e ".[all]"
```

Use `.[dev]` for tests only, or `.[image]` for the image/background-removal stack only.

Configure AI agents in `.env`:

```env
AI_PROVIDER=anthropic
AI_MODE=claude
ANTHROPIC_MODEL=claude-sonnet-4-6
ANTHROPIC_API_KEY=your_api_key_here
```

Configure product sourcing in `.env`:

```env
PRODUCT_SEARCH_PROVIDER=google_shopping
SERPAPI_API_KEY=your_serpapi_key_here
GOOGLE_SHOPPING_LOCATION=United States
GOOGLE_SHOPPING_GL=us
GOOGLE_SHOPPING_HL=en
AFFILIATE_PROVIDER=none
```

The first product source is Google Shopping through an API provider, not scraping. Product records store the normal product page URL and a separate nullable `affiliate_url`. The website uses `affiliate_url` when it exists and falls back to the normal `url`.

An AWIN affiliate catalog is also supported (`PRODUCT_SEARCH_PROVIDER=awin`): approved merchant feeds are synced into a local catalog that already carries affiliate URLs. See [docs/product_sourcing.md](docs/product_sourcing.md).

```env
# Optional: AWIN affiliate catalog
AWIN_PUBLISHER_ID=your_publisher_id
AWIN_OAUTH2_TOKEN=your_oauth2_token
```

Configure autoposting only after your generated collage images are available at public URLs:

```env
AUTOPOSTING_ENABLED=true
PUBLIC_ASSET_BASE_URL=https://your-public-asset-host.example
TIKTOK_ACCESS_TOKEN=your_tiktok_user_access_token
TIKTOK_POST_MODE=DIRECT_POST
TIKTOK_PRIVACY_LEVEL=SELF_ONLY
PINTEREST_ACCESS_TOKEN=your_pinterest_access_token
PINTEREST_BOARD_ID=your_board_id
```

TikTok photo posting pulls images from public URLs, so local `data/images/...` files must be hosted before direct posting can work. Pinterest pins use the same public asset URL mapping.

Example commands:

```bash
python3 scripts/seed_concepts.py
python3 scripts/run_daily.py
python3 scripts/sync_awin_feeds.py            # sync AWIN affiliate feeds (or --stats)
python3 scripts/publish_due.py
python3 scripts/backfill_metrics.py data/metrics/sample_manual_metrics.json
python3 scripts/generate_replacement_concept.py <retired_concept_id>
python3 scripts/generate_replacement_concept.py <retired_concept_id> --response-file data/llm_responses/sample_replacement_concept_response.json
python3 scripts/regenerate_collage.py /tmp/collage.png image1.png image2.png
```

## Documentation

- [Architecture](docs/architecture.md): system boundaries, data flow, and module responsibilities
- [Terminology](docs/terminology.md): distinction between concepts and LLM prompts
- [Pipeline](docs/pipeline.md): complete end-to-end execution flow
- [Creative Briefs](docs/creative_briefs.md): structured concept context for preserving nuance
- [Concept Scoring](docs/concept_scoring.md): daily selection, mirrored posting, ranking scores, and retirement
- [Product Sourcing](docs/product_sourcing.md): Google Shopping API sourcing, the AWIN affiliate catalog, retailer policy, images, and affiliate-link separation
- [Image Service](docs/image_service.md): Runflow product-isolation cutouts, fallback chain, and tuning knobs
- [Autoposting](docs/autoposting.md): TikTok/Pinterest posting setup, public asset hosting, and due-post publishing
- [AI Agents](docs/ai_agents.md): Claude-backed agent setup and saved-response debug files
- [Agent Prompts](docs/agent_prompts.md): LLM prompt purposes, constraints, versioning, and evaluation
- [Website](docs/website.md): public-facing frontend, brand direction, and Supabase data layer
- [API](docs/api.md): internal typed endpoint contracts
- [Roadmap](docs/roadmap.md): future product and platform ideas
