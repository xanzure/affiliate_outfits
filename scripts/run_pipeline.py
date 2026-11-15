#!/usr/bin/env python3
"""
Manual pipeline runner.

Usage:
  # One outfit for a specific concept
  python scripts/run_pipeline.py "Bad Bunny concert"

  # Full batch of 5 for a concept
  python scripts/run_pipeline.py "Bad Bunny concert" --batch

  # One outfit for every concept
  python scripts/run_pipeline.py --all

  # Full batch of 5 for every concept
  python scripts/run_pipeline.py --all --batch
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("run_pipeline")

# Silence noisy sub-loggers
for noisy in ("httpx", "hpack", "anthropic"):
    logging.getLogger(noisy).setLevel(logging.WARNING)


def _make_scheduled_concept(concept):
    from app.creative_briefs import brief_from_concept_metadata
    from app.scheduler import ScheduledConcept
    return ScheduledConcept(
        concept_id=concept.id,
        seed=concept.seed,
        brief=brief_from_concept_metadata(concept.seed, concept.metadata),
        usage_count=concept.usage_count,
        ranking_score=concept.ranking_score,
        last_posted_date_est=concept.last_posted_date_est,
    )


def run_spec_only(concept, *, batch: bool = False):
    import json
    from app.agents.outfit.curator import generate_outfit_specs, make_curator_service
    from app.creative_briefs import brief_from_concept_metadata

    brief = brief_from_concept_metadata(concept.seed, concept.metadata)
    service = make_curator_service()
    count = 5 if batch else 1
    log.info("Generating %d outfit spec(s) for: %s", count, concept.seed)

    specs = generate_outfit_specs(brief, count, [], service=service)

    for i, spec in enumerate(specs, 1):
        print(f"\n{'═'*60}")
        print(f"OUTFIT {i}: {spec.get('title', '').upper()}")
        print(f"{'═'*60}")
        print(f"Rationale: {spec.get('rationale', '')}")
        print(f"Reference: {spec.get('primary_reference', '')}")
        print()
        for item in spec.get("items", []):
            print(f"  [{item.get('role','').upper()}]")
            print(f"    {item.get('category')} — {item.get('color')}, {item.get('material')}")
            print(f"    Search: {item.get('search_query')}")
            print(f"    Price:  {item.get('price_range')}")
            print()


def run_one(conn, concept, settings):
    from app.pipelines.daily_pipeline import run_daily_for_brief
    sc = _make_scheduled_concept(concept)
    log.info("Running single outfit for: %s", concept.seed)
    result = run_daily_for_brief(conn, sc, create_publish_records=False, settings=settings)
    log.info("✓ Outfit created: %s", result.outfit.id)
    log.info("  Collage: %s", result.collage_path)
    log.info("  Products: %d", len(result.products))
    return result


def run_batch(conn, concept, settings):
    from app.pipelines.daily_pipeline import run_daily_outfit_set_for_concept
    sc = _make_scheduled_concept(concept)
    log.info("Running batch of 5 outfits for: %s", concept.seed)
    result = run_daily_outfit_set_for_concept(
        conn, sc, create_publish_records=False, settings=settings
    )
    log.info("✓ %d outfits created", len(result.outfit_results))
    for i, r in enumerate(result.outfit_results, 1):
        log.info("  [%d] %s → %s", i, r.outfit.id[:20], r.collage_path.name)
    return result


def main():
    parser = argparse.ArgumentParser(description="Run the outfit pipeline manually")
    parser.add_argument("concept", nargs="?", help="Concept seed name (partial match ok)")
    parser.add_argument("--batch", action="store_true", help="Run full batch of 5 instead of 1")
    parser.add_argument("--all", dest="all_concepts", action="store_true", help="Run for all active concepts")
    parser.add_argument("--spec-only", action="store_true", help="Print outfit spec from curator only — no search, no images")
    args = parser.parse_args()

    if not args.concept and not args.all_concepts:
        parser.error("Provide a concept name or --all")

    from app.config import load_settings
    from app.db.concepts import list_active_concepts
    from app.db.pg_connection import connect_postgres

    settings = load_settings()
    # Override DRY_RUN so the pipeline actually writes
    import dataclasses
    settings = dataclasses.replace(settings, dry_run=False)

    conn = connect_postgres("")
    all_concepts = list_active_concepts(conn)

    if args.all_concepts:
        targets = all_concepts
    else:
        query = args.concept.lower()
        targets = [c for c in all_concepts if query in c.seed.lower()]
        if not targets:
            log.error("No concept matching %r. Active concepts:", args.concept)
            for c in all_concepts:
                log.error("  %s", c.seed)
            sys.exit(1)
        if len(targets) > 1:
            log.warning("Multiple matches — using first: %s", targets[0].seed)
            targets = targets[:1]

    for concept in targets:
        try:
            if args.spec_only:
                run_spec_only(concept, batch=args.batch)
            elif args.batch:
                run_batch(conn, concept, settings)
            else:
                run_one(conn, concept, settings)
        except Exception:
            log.exception("Failed for concept: %s", concept.seed)
            if not args.all_concepts:
                sys.exit(1)


if __name__ == "__main__":
    main()
