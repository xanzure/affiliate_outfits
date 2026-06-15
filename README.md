# Affiliate Content Engine

Affiliate Content Engine is an autonomous content generation pipeline that creates fashion inspiration posts for TikTok and Pinterest using specialized AI agents and deterministic software pipelines.

The system is intentionally built as an engineering project rather than a no-code automation.

## Philosophy

- AI is only used for creative or subjective decisions.
- Everything else is conventional, deterministic software.
- Every stage should be independently testable and reproducible.
- The system optimizes prompt performance over time using engagement metrics.
- Components should be modular and replaceable.

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

- Generating outfit ideas
- Maintaining outfit diversity
- Selecting products

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

- Generating new prompt ideas
- Replacing retired prompts
- Maintaining the active prompt pool

## Development Principles

- Deterministic whenever possible
- AI only for subjective decisions
- Modular architecture
- Reproducible outputs
- Easy local development
- Replaceable components
- Every module should have one responsibility, one input, one output, one test suite, and one interface

## Local Development

Everything should be runnable independently. Testing one part of the system should never require the entire pipeline.

Example commands:

```bash
python run_outfit.py
python run_collage.py
python regenerate_post.py --id 123
python update_metrics.py
```

## Documentation

- [Architecture](docs/architecture.md): system boundaries, data flow, and module responsibilities
- [Pipeline](docs/pipeline.md): complete end-to-end execution flow
- [Prompts](docs/prompts.md): agent prompt purposes, constraints, versioning, and evaluation
- [API](docs/api.md): internal typed endpoint contracts
- [Roadmap](docs/roadmap.md): future product and platform ideas

## Future Ideas

- Multi-account support
- Multi-language support
- Affiliate network abstraction
- Dashboard
- A/B testing
- Image style versioning
- Multiple brands
- Multiple affiliate networks
- Multiple posting schedules
- Multiple image styles
- Multiple agent models
