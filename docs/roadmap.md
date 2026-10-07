# Roadmap

This document collects future ideas from the README and architecture notes so they are easy to prioritize later.

## Product Ideas

- Dashboard
- A/B testing
- Image style versioning
- Multi-account support
- Multi-language support

## Platform And Affiliate Ideas

- Affiliate network abstraction
- Multiple affiliate networks
- Multiple posting schedules

## System Expansion Ideas

- Multiple brands
- Multiple image styles
- Multiple agent models

## Infrastructure / Learning Ideas

Both are deterministic-infra additions (no AI), consistent with the "AI only for
creative decisions" philosophy. Design detail: architecture.md → *Caching* and
*Deployment & Containerization*. Suggested order: Redis first (self-contained,
directly hits the cost goal, testable against a throwaway `docker run redis`),
then compose (which folds Redis in as a service and adds the web image).

### Redis product-search cache — learning target: Redis

Caches the normalized results of *paid* provider searches (Apify / SerpApi) so an
identical repeat query skips the network. Cuts repeat-query cost (~$25/1000) and
latency — the current Apify provider runs synchronously with a 300s timeout, so a
cache hit also saves minutes, not just dollars. This is a **third** reuse layer,
distinct from the two that already exist (explicit LLM URL reuse + the
`find_cached_match` near-match gate, which reuse *products*, not *searches*).

1. Add `redis` dep + `REDIS_URL`, `PRODUCT_SEARCH_CACHE_TTL_SECONDS` (default
   86400), `PRODUCT_SEARCH_CACHE_ENABLED` config.
2. Build a `CachedProductSearchProvider` decorator implementing the
   `ProductSearchProvider` Protocol. Cache the returned `list[ProductSearchResult]`
   as JSON, key `psearch:v1:{provider}:{gl}:{normalized_query}:{category}`,
   fetch-wide/slice-narrow, **graceful fall-through on any Redis error**.
3. Wrap only providers flagged `is_paid_external` (Apify/SerpApi/Tavily) inside
   `product_search_provider_from_settings`; never AWIN (free local FTS5) or
   fixtures.
4. Cache errors not at all; cache empties on a short TTL only.
5. Instrument hit/miss to the activity log / metrics so the saving is visible.
6. Confirm the active provider's ToS permits caching for the chosen TTL.

### Finish Docker containerization — learning target: Docker

The worker image already runs the pipeline on Railway; the remaining work is
one-command local reproducibility of the *whole* stack.

1. Add `web/Dockerfile` (multi-stage, Next.js `output: "standalone"`).
2. Add root `docker-compose.yml`: `worker` (existing Dockerfile) + `redis` +
   `web`; env via `env_file`; Supabase stays hosted (no local DB container).
3. Verify/extend `.dockerignore` (`web/node_modules`, `web/.next`, `data/`,
   `.venv`) so the worker's `COPY . .` image stays slim.
4. Document the one-shot pipeline run in-container
   (`docker compose run worker python -m app.pipelines.daily_pipeline --concept <id>`).
