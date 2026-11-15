#!/usr/bin/env python3
"""
Job worker for the admin dashboard. Polls the `jobs` table and executes
pipeline work the web app can't run directly (it's Python).

Run once (cron each minute):
  python scripts/worker.py
Run continuously:
  python scripts/worker.py --loop
"""
from __future__ import annotations

import argparse
import dataclasses
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

logging.basicConfig(level=logging.INFO, format="%(levelname)s worker: %(message)s")
log = logging.getLogger("worker")
for noisy in ("httpx", "hpack", "anthropic"):
    logging.getLogger(noisy).setLevel(logging.WARNING)


def _handle_link_check(conn, payload: dict) -> dict:
    from app.db.posts import list_posts, set_link_check
    from app.services.link_health import check_post_links

    posts = list_posts(conn)
    checked = 0
    flagged = 0
    for post in posts:
        result = check_post_links(post.metadata)
        if result["total"] == 0:
            continue
        set_link_check(conn, post.id, result)
        checked += 1
        if result["dead"]:
            flagged += 1
    return {"checked": checked, "flagged": flagged}


def _handle_run_concept(conn, payload: dict) -> dict:
    from app.config import load_settings
    from app.creative_briefs import brief_from_concept_metadata
    from app.db.concepts import get_concept
    from app.pipelines.daily_pipeline import (
        run_daily_for_brief,
        run_daily_outfit_set_for_concept,
    )
    from app.scheduler import ScheduledConcept

    concept_id = payload["concept_id"]
    batch = bool(payload.get("batch"))
    concept = get_concept(conn, concept_id)
    sc = ScheduledConcept(
        concept_id=concept.id,
        seed=concept.seed,
        brief=brief_from_concept_metadata(concept.seed, concept.metadata),
        usage_count=concept.usage_count,
        ranking_score=concept.ranking_score,
        last_posted_date_est=concept.last_posted_date_est,
    )
    settings = dataclasses.replace(load_settings(), dry_run=False)
    if batch:
        result = run_daily_outfit_set_for_concept(
            conn, sc, create_publish_records=True, settings=settings
        )
        return {"outfits": len(result.outfit_results)}
    result = run_daily_for_brief(
        conn, sc, create_publish_records=True, settings=settings
    )
    return {"outfit_id": result.outfit.id}


def _outfit_assets(conn, outfit_id: str):
    import httpx
    from app.config import load_settings
    from app.db.outfits import get_outfit
    from app.db.products import get_product

    settings = load_settings()
    outfit = get_outfit(conn, outfit_id)
    products = [get_product(conn, pid) for pid in outfit.product_ids]
    norm_dir = settings.data_dir / "images" / "normalized"
    norm_dir.mkdir(parents=True, exist_ok=True)

    paths = []
    for p in products:
        local = norm_dir / f"{p.id}.png"
        if not local.exists() and p.image_url:
            log.info("downloading product image %s from storage", p.id[:16])
            try:
                resp = httpx.get(p.image_url, timeout=30, follow_redirects=True)
                resp.raise_for_status()
                local.write_bytes(resp.content)
            except Exception as exc:
                log.warning("failed to download %s: %s", p.id[:16], exc)
        paths.append(local)
    return settings, outfit, products, paths


def _handle_regenerate_collage(conn, payload: dict) -> dict:
    from types import SimpleNamespace
    from app.db.collages import list_collages_for_outfit
    from app.db.outfits import update_outfit_spec
    from app.pipelines.collage_pipeline import render_html_collage_for_images
    from app.pipelines.daily_pipeline import (
        _collage_manifest_with_products,
        _spec_with_website_layout,
        _upload_collage,
    )

    outfit_id = payload["outfit_id"]
    settings, outfit, products, paths = _outfit_assets(conn, outfit_id)
    missing = [str(p) for p in paths if not p.exists()]
    if missing:
        return {"error": f"missing normalized images after download attempt: {len(missing)}"}

    categories = [p.category for p in products]
    # Use the HTML/CSS template renderer (same as a fresh concept), with the
    # template the outfit was generated for — NOT the old PIL geometry engine.
    result = render_html_collage_for_images(
        [SimpleNamespace(normalized_path=p) for p in paths],
        output_name=f"{outfit_id}.png",
        settings=settings,
        concept_name=outfit.concept_seed,
        outfit_number=1,
        categories=categories,
        template_name=outfit.spec.get("template"),
    )
    url = _upload_collage(outfit_id, result.image_path)
    # Append cache-busting timestamp so CDN/browser fetches the fresh image
    import time as _time
    if url:
        url = f"{url}?t={int(_time.time())}"
    manifest = _collage_manifest_with_products(result.manifest, products)
    collages = list_collages_for_outfit(conn, outfit_id)
    if collages:
        conn.execute(
            "UPDATE collages SET collage_url = ? WHERE id = ?",
            (url, collages[0].id),
        )
    update_outfit_spec(
        conn, outfit_id,
        _spec_with_website_layout(outfit.spec, {"canvas": manifest["canvas"], "pieces": manifest["pieces"]}, url),
    )
    return {"collage_url": url}


def _handle_regenerate_image(conn, payload: dict) -> dict:
    from app.db.products import get_product
    from app.db.outfits import get_outfit
    from app.pipelines.image_pipeline import prepare_product_images
    from app.services.image_service import ImageService
    from app.config import load_settings

    outfit = get_outfit(conn, payload["outfit_id"])
    products = [get_product(conn, pid) for pid in outfit.product_ids]
    prepare_product_images(conn, products, image_service=ImageService(load_settings()))
    return {"reprocessed": len(products)}


def _handle_intake_product(conn, payload: dict) -> dict:
    """Manual wardrobe intake. We ALWAYS scrape the product URL for metadata
    (name, price, brand, description); a user-uploaded image only replaces the
    *visual* (and is run through the cutout since it's raw). Category and colour
    are derived from the scraped text when not given explicitly, so every field
    is filled unless it genuinely can't be determined."""
    from dataclasses import replace
    from app.collage.export import _resolve_zone
    from app.config import load_settings
    from app.pipelines.image_pipeline import prepare_product_images
    from app.pipelines.product_pipeline import _store_product_candidates
    from app.services.affiliate_service import affiliate_resolver_from_name
    from app.services.image_service import ImageService
    from app.services.product_cache import extract_color_word
    from app.services.product_search_service import (
        ProductSearchResult, scrape_product_url, _retailer_from_url,
    )

    settings = load_settings()
    url = (payload.get("url") or "").strip()
    if not url.startswith(("http://", "https://")):
        return {"error": "a valid product URL is required"}
    manual_image = payload.get("image_url")
    category = (payload.get("category") or "").strip() or None

    # Scrape for metadata regardless of whether an image was uploaded.
    scraped = None
    try:
        scraped = scrape_product_url(url, api_token=settings.apify_token or "", category=category)
    except Exception as exc:  # noqa: BLE001
        log.warning("intake scrape failed for %s: %s", url[:80], exc)

    if scraped is None and not manual_image:
        return {"error": "image could not be scraped from that URL — upload an image manually to add it"}

    if scraped is not None:
        result = replace(
            scraped,
            image_url=manual_image or scraped.image_url,
            source="manual" if manual_image else scraped.source,
        )
    else:
        result = ProductSearchResult(
            retailer=_retailer_from_url(url), name=payload.get("name") or "Wardrobe item",
            url=url, category=category, image_url=manual_image, source="manual",
        )

    # Fill category + colour from the richest text available, unless given.
    description = result.metadata.get("description") if isinstance(result.metadata, dict) else None
    text = " ".join(t for t in (result.name, description) if t)
    final_category = category or result.category or _resolve_zone(result.name)
    color = payload.get("color") or extract_color_word(text)
    result = replace(result, category=final_category)

    resolver = affiliate_resolver_from_name(settings.affiliate_provider)
    products = _store_product_candidates(
        conn, [result], tracking_id="wardrobe-intake", affiliate_resolver=resolver,
        color=color, material=payload.get("material"),
    )
    if not products:
        return {"error": "failed to store product"}
    # Uploaded images are raw → force the cutout. Scraped images process normally.
    prepared = prepare_product_images(
        conn, products, image_service=ImageService(settings), force=bool(manual_image),
    )
    if not prepared:
        return {"error": "image processing failed — upload an image manually to retry"}
    p = products[0]
    return {
        "product_id": p.id, "name": p.name, "price_cents": p.price_cents,
        "category": final_category, "color": color, "image_ready": len(prepared),
    }


def _handle_reprocess_product(conn, payload: dict) -> dict:
    """Re-run the cutout for one product, optionally with a freshly-uploaded image."""
    from app.config import load_settings
    from app.db.products import get_product, update_product_image_url
    from app.pipelines.image_pipeline import prepare_product_images
    from app.services.image_service import ImageService

    pid = payload["product_id"]
    has_upload = bool(payload.get("image_url"))
    if has_upload:  # re-upload forces a real reprocess
        update_product_image_url(conn, pid, payload["image_url"])
    product = get_product(conn, pid)
    # A fresh upload is raw → force the cutout instead of treating the storage
    # URL as already-processed.
    prepared = prepare_product_images(
        conn, [product], image_service=ImageService(load_settings()), force=has_upload,
    )
    return {"reprocessed": len(prepared)}


def _handle_generate_posts_for_outfit(conn, payload: dict) -> dict:
    """Generate TikTok + Pinterest draft posts for an existing outfit that has
    none (e.g. the originals were deleted). Reuses the exact engagement +
    publish-record path the daily pipeline uses. Lands as drafts (Needs
    Approval) — no autopublish, same as a freshly generated outfit."""
    from app.agents.engagement.agent import generate_engagement_with_llm
    from app.db.collages import list_collages_for_outfit
    from app.db.outfits import get_outfit
    from app.db.products import get_product
    from app.pipelines.daily_pipeline import _product_payload
    from app.pipelines.publish_pipeline import create_local_publish_records

    outfit_id = payload.get("outfit_id")
    if not outfit_id:
        return {"error": "outfit_id is required"}

    outfit = get_outfit(conn, outfit_id)
    products = [get_product(conn, pid) for pid in outfit.product_ids]
    collages = list_collages_for_outfit(conn, outfit_id)
    if not collages:
        return {"error": "outfit has no collage — regenerate the collage first"}
    collage = collages[0]

    brief = outfit.metadata.get("brief")
    if not isinstance(brief, dict):
        return {"error": "outfit is missing its original brief — can't regenerate captions"}

    engagement_output = generate_engagement_with_llm(
        brief, outfit.spec, [_product_payload(p) for p in products],
    )
    publish_result = create_local_publish_records(
        conn,
        concept_id=outfit.concept_id,
        outfit=outfit,
        products=products,
        collage_path=collage.collage_url or collage.image_path,
        engagement_output=engagement_output,
    )
    return {"post_ids": [p.id for p in publish_result.posts], "outfit_id": outfit_id}


def _handle_retry_post(conn, payload: dict) -> dict:
    """Re-attempt a live platform post for a single post row (e.g. after a
    failed publish). Reuses the same autopublish path the daily pipeline uses,
    so a fixed token / fixed scope / fixed logging bug takes effect."""
    from app.config import load_settings
    from app.db.posts import get_post
    from app.pipelines.publish_pipeline import autopublish_posts

    post_id = payload.get("post_id")
    if not post_id:
        return {"error": "post_id is required"}

    settings = load_settings()
    post = get_post(conn, post_id)
    result = autopublish_posts(conn, [post], settings=settings)
    if result.published:
        return {"status": "published", "post_id": post_id}
    if result.failed:
        failed_post = result.failed[0]
        error = failed_post.metadata.get("api_error") if failed_post.metadata else None
        return {"error": error or "publish failed", "post_id": post_id}
    return {"status": "skipped", "post_id": post_id}


HANDLERS = {
    "link_check": _handle_link_check,
    "run_concept": _handle_run_concept,
    "regenerate_collage": _handle_regenerate_collage,
    "regenerate_image": _handle_regenerate_image,
    "intake_product": _handle_intake_product,
    "reprocess_product": _handle_reprocess_product,
    "retry_post": _handle_retry_post,
    "generate_posts_for_outfit": _handle_generate_posts_for_outfit,
}


def _log_action(conn, action: str, job_id: str) -> None:
    from app.db._helpers import new_id, utc_now
    try:
        conn.execute(
            "INSERT INTO admin_actions (id, action, target_id, detail_json, created_at) VALUES (?, ?, ?, '{}', ?)",
            (new_id("act"), action, job_id, utc_now()),
        )
    except Exception:  # noqa: BLE001
        pass  # never let logging break the worker


def run_queue_tick() -> None:
    """Publish the head of each platform's queue if its 24h cooldown elapsed.
    Own connection so it's independent of the job-queue drain."""
    from app.config import load_settings
    from app.db.pg_connection import connect_postgres
    from app.pipelines.publish_pipeline import process_queue_tick

    conn = connect_postgres("")
    try:
        result = process_queue_tick(conn, settings=load_settings())
        for post in result.published:
            log.info("queue autopost published %s (%s)", post.id[:16], post.platform)
            _log_action(conn, f"queue_autopost_done:{post.platform}", post.id)
        for post in result.failed:
            log.warning("queue autopost failed %s (%s)", post.id[:16], post.platform)
            _log_action(conn, f"queue_autopost_failed:{post.platform}", post.id)
    except Exception:  # noqa: BLE001
        log.exception("queue tick error")
    finally:
        conn.close()


def process_once() -> int:
    from app.db.jobs import claim_next_job, finish_job
    from app.db.pg_connection import connect_postgres

    conn = connect_postgres("")
    count = 0
    while True:
        job = claim_next_job(conn)
        if not job:
            break
        count += 1
        handler = HANDLERS.get(job["type"])
        log.info("running job %s (%s)", job["id"][:16], job["type"])
        _log_action(conn, f"job_started:{job['type']}", job["id"])
        if not handler:
            finish_job(conn, job["id"], ok=False, result={"error": "unknown job type"})
            _log_action(conn, f"job_failed:{job['type']}", job["id"])
            continue
        try:
            result = handler(conn, job["payload"])
            ok = "error" not in result
            finish_job(conn, job["id"], ok=ok, result=result)
            _log_action(conn, f"job_{'done' if ok else 'failed'}:{job['type']}", job["id"])
            log.info("  done: %s", result)
        except Exception as exc:  # noqa: BLE001
            log.exception("  failed")
            finish_job(conn, job["id"], ok=False, result={"error": str(exc)})
            _log_action(conn, f"job_failed:{job['type']}", job["id"])
    conn.close()
    return count


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--loop", action="store_true", help="poll continuously")
    parser.add_argument("--interval", type=int, default=10, help="loop poll seconds")
    args = parser.parse_args()

    if not args.loop:
        n = process_once()
        log.info("processed %d job(s)", n)
        run_queue_tick()
        return
    log.info("worker loop started (interval=%ss)", args.interval)
    queue_tick_seconds = 60  # check the publish cooldown at most once a minute
    last_queue_tick = 0.0
    while True:
        try:
            process_once()
        except Exception:  # noqa: BLE001
            log.exception("poll error")
        if time.time() - last_queue_tick >= queue_tick_seconds:
            run_queue_tick()
            last_queue_tick = time.time()
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
