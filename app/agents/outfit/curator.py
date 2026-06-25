"""
Outfit Curator — the opinionated agent that drives the full search-and-review loop.

Uses Claude Opus with extended thinking. Generates outfit specs, reviews actual search
results, rejects bad finds, refines queries, and only approves when it's genuinely happy.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.services.llm_service import ClaudeJSONService, LLMPrompt

log = logging.getLogger(__name__)

# Opus 4.8 leads on creative taste/range (what makes a broad concept diverse);
# low effort keeps deliberation + cost down — the facet system supplies structural
# diversity, so we don't need to pay for high effort.
_CURATOR_MODEL = "claude-opus-4-8"
_CURATOR_EFFORT = "low"

_STORE_KNOWLEDGE = (
    Path(__file__).parent / "store_knowledge.md"
).read_text()

_CURATOR_SYSTEM = """\
You are an editorial fashion curator with strong opinions and refined taste.
You think carefully about whether products actually work together as an outfit before approving them.
You know exactly which stores carry what and you write precise, targeted search queries.
Return only valid JSON. No markdown, no commentary outside the JSON.\
"""


# ── outfit generation ──────────────────────────────────────────────────────────

_GENERATION_PROMPT = """\
You are curating {outfit_count} outfit{plural} for the following concept.
You have access to a store knowledge base — use it to write targeted, specific search queries
that name actual retailers and specific product silhouettes.

## Curator Reference Guide
# Contains: concept vibe breakdowns, universal pairing rules, and store knowledge.
# Use as strong guidance — not rigid rules. Real style has personality.
{store_knowledge}

## Creative Brief
{brief}

## Previously Generated Outfits (do not repeat)
{history}

## Cached Product Inventory (already sourced, images ready — prefer these when they fit)
{cached_inventory}

## Per-Outfit Brief (MANDATORY — follow every field exactly)
Each outfit below specifies a STYLE DIRECTION, a GENDER PRESENTATION, and its
required ITEM TYPES. For each outfit you MUST:
- Anchor the whole outfit to its **direction** — this is a specific facet of the
  concept. Two outfits with different directions should look like different
  worlds (e.g. "tropical resort" vs "Y2K streetwear"), not minor variations.
- Make every item consistent with its **presentation** (feminine or masculine) —
  reflect it in the search queries ("women's…" / "men's…") and silhouettes.
- Contain EXACTLY the listed item types, one product per type, items[] in that order.
{composition}

Generate {outfit_count} distinct, opinionated outfit{plural}. Each must:
- Fully commit to its assigned direction and presentation above
- Tell a coherent visual story — not just random pieces thrown together
- Contain exactly the item types required for it above, in order
- Reference specific retailers and product names in search queries, not generic terms
- NOT repeat any outfit in "Previously Generated Outfits" — different items AND a
  different feel
- Prefer cached inventory items when they genuinely fit — note them with use_cached_url field

## CRITICAL: describe items as they are SOLD, never how they are STYLED
`category` and `search_query` must describe a product a retailer actually lists.
NEVER include styling or wearing instructions — those are how the outfit is worn,
not searchable attributes, and they return zero results.
- BANNED in category/search_query: "knotted at waist", "tucked in", "rolled cuffs",
  "sleeves pushed up", "draped", "belted", "layered over", "half-tucked", "cuffed",
  "french tuck", "open over", "thrown on", or any verb describing how to wear it.
- Search for the GARMENT: "graphic band tee", not "graphic tee knotted at waist".
  "high-rise straight jeans", not "jeans cuffed at the ankle".
Put the styling intent in `role` or `rationale` if you must — never in what we search for.

Return JSON:
{{
  "outfits": [
    {{
      "title": "short editorial title (max 6 words)",
      "rationale": "why these pieces together — the story this outfit tells",
      "primary_reference": "specific cultural/aesthetic anchor",
      "items": [
        {{
          "role": "what role this piece plays (e.g. statement top, foundation trouser)",
          "category": "exact product type AS SOLD (e.g. wide-leg trousers, leather mule, oversized blazer) — no styling words",
          "color": "specific color (e.g. ecru, burnt sienna, slate — never 'neutral' or 'casual')",
          "material": "specific material (e.g. linen, washed denim, suede, ribbed knit)",
          "search_query": "retailer + product + color + material, AS SOLD. Example: 'COS wide-leg linen trousers ecru'. No styling/wearing words.",
          "use_cached_url": "URL from cached inventory if reusing an existing item, otherwise null",
          "price_range": "budget | mid | elevated | luxury"
        }}
      ]
    }}
  ]
}}\
"""


# ── review loop ────────────────────────────────────────────────────────────────

_REVIEW_PROMPT = """\
You specified this outfit:
{outfit_spec}

You searched for products and found these results:
{found_products}

Review each found product critically. Ask yourself:
- Does this product actually match what I asked for (color, material, silhouette)?
- Is the quality/price point right for this concept?
- Do all the pieces still work together as a cohesive outfit?
- Would I actually put this outfit on an editorial page?

For each item index, decide: APPROVE or REJECT.
If rejecting, explain exactly why and write a better, more specific search query.

Return JSON:
{{
  "overall_verdict": "approve" | "reject",
  "rationale": "your overall assessment of whether this outfit works",
  "items": [
    {{
      "index": 0,
      "verdict": "approve" | "reject",
      "reason": "specific reason — what's wrong or right",
      "refined_query": "new search query if rejecting, null if approving"
    }}
  ]
}}\
"""


@dataclass(frozen=True)
class ReviewedProduct:
    index: int
    approved: bool
    reason: str
    refined_query: str | None


@dataclass
class CuratorReview:
    overall_approved: bool
    rationale: str
    items: list[ReviewedProduct]


def make_curator_service() -> ClaudeJSONService:
    return ClaudeJSONService(model=_CURATOR_MODEL, effort=_CURATOR_EFFORT)


def _choose_templates(outfit_count: int, brief: dict[str, Any]) -> list[str]:
    """Pick one collage template per outfit — distinct where possible, seeded by
    the brief so a given concept is reproducible."""
    import random
    from app.collage.html_export import list_templates

    names = [t.name for t in list_templates()]
    rng = random.Random(json.dumps(brief, sort_keys=True))
    rng.shuffle(names)
    if outfit_count <= len(names):
        return names[:outfit_count]
    # more outfits than templates — cycle, reshuffling each pass
    out = list(names)
    while len(out) < outfit_count:
        extra = list(names)
        rng.shuffle(extra)
        out.extend(extra)
    return out[:outfit_count]


# ── style facets (per-concept diversity engine) ─────────────────────────────────

_FACETS_PROMPT = """\
List {count} DISTINCT, specific style directions a complete outfit for this concept
could take. Each must be a different facet / mood / subculture of the concept —
different enough that outfits built from two of them look like different worlds.
Be concrete and evocative (e.g. "tropical resort luxe", "Y2K mall streetwear",
"rockstar leather", "heritage academia prep"). A tight concept yields few real
directions; a broad one (a versatile artist, a city, a decade) yields many.

Concept: {brief}

Return JSON: {{"facets": ["direction one", "direction two", ...]}}\
"""


def generate_facets(brief: dict[str, Any], count: int = 8, *, service: ClaudeJSONService | None = None) -> list[str]:
    service = service or make_curator_service()
    prompt = LLMPrompt(
        title="Concept style facets",
        body=_FACETS_PROMPT.format(count=count, brief=json.dumps(brief, indent=2)),
        system=_CURATOR_SYSTEM,
    )
    data = service.request_json(prompt)
    facets = data.get("facets", [])
    return [f.strip() for f in facets if isinstance(f, str) and f.strip()][:count]


def get_or_create_facets(
    conn: Any,
    concept_id: str,
    brief: dict[str, Any],
    *,
    service: ClaudeJSONService | None = None,
    count: int = 8,
) -> list[str]:
    """Concept's style directions, generated once and cached in concept metadata."""
    from app.db.concepts import get_concept, update_concept_metadata

    try:
        concept = get_concept(conn, concept_id)
    except Exception:
        return []
    cached = concept.metadata.get("style_facets")
    if isinstance(cached, list) and len([f for f in cached if isinstance(f, str)]) >= 3:
        return cached
    facets = generate_facets(brief, count, service=service)
    if facets:
        md = {**concept.metadata, "style_facets": facets}
        update_concept_metadata(conn, concept_id, md)
    return facets


def _assign_genders(outfit_count: int, brief: dict[str, Any]) -> list[str]:
    """Deterministic ~70% feminine / 30% masculine per batch, seeded for repeatability."""
    import random
    feminine = round(outfit_count * 0.7)
    genders = ["feminine"] * feminine + ["masculine"] * (outfit_count - feminine)
    random.Random("gender:" + json.dumps(brief, sort_keys=True)).shuffle(genders)
    return genders


def _sample_facets(
    facets: list[str], outfit_count: int, history: list[dict[str, Any]], brief: dict[str, Any]
) -> list[str | None]:
    """Pick distinct facets for this batch, preferring ones not used recently.
    Seeded by history length so each run of a concept explores fresh directions."""
    import random
    if not facets:
        return [None] * outfit_count
    used = [h.get("facet") for h in (history or []) if isinstance(h, dict) and h.get("facet")]
    recent = set(used[-(outfit_count * 2):])
    pool = [f for f in facets if f not in recent] or list(facets)
    rng = random.Random(f"facet:{json.dumps(brief, sort_keys=True)}:{len(history or [])}")
    rng.shuffle(pool)
    out: list[str | None] = pool[:outfit_count]
    while len(out) < outfit_count:
        out.append(rng.choice(facets))
    return out


def generate_outfit_specs(
    brief: dict[str, Any],
    outfit_count: int,
    history: list[dict[str, Any]],
    *,
    service: ClaudeJSONService | None = None,
    cached_products: list[dict[str, Any]] | None = None,
    facets: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Generate outfit specs: each forced into a template, anchored to a distinct
    style facet, assigned a gender presentation, and de-duped against history."""
    from app.collage.html_export import template_requirement_labels

    service = service or make_curator_service()
    plural = "s" if outfit_count != 1 else ""

    chosen_templates = _choose_templates(outfit_count, brief)
    sampled_facets = _sample_facets(facets or [], outfit_count, history, brief)
    genders = _assign_genders(outfit_count, brief)

    composition_lines = []
    for idx, (tname, facet, gender) in enumerate(
        zip(chosen_templates, sampled_facets, genders), start=1
    ):
        items = ", ".join(template_requirement_labels(tname))
        direction = facet or "the concept's core aesthetic"
        composition_lines.append(
            f"Outfit {idx} — direction: {direction} | presentation: {gender} | items: {items}"
        )
    composition = "\n".join(composition_lines)

    if cached_products:
        inventory_lines = []
        for p in cached_products:
            price = f"${p['price_cents']/100:.0f}" if p.get("price_cents") else "?"
            inventory_lines.append(
                f"- [{p.get('category','?')}] {p.get('name','')} | {p.get('retailer','')} | {price} | {p.get('url','')}"
            )
        cached_inventory = "\n".join(inventory_lines)
    else:
        cached_inventory = "None yet."

    prompt = LLMPrompt(
        title=f"Outfit Curator: Generate {outfit_count} Outfit{plural}",
        body=_GENERATION_PROMPT.format(
            outfit_count=outfit_count,
            plural=plural,
            store_knowledge=_STORE_KNOWLEDGE,
            brief=json.dumps(brief, indent=2),
            history=json.dumps(history, indent=2) if history else "[]",
            cached_inventory=cached_inventory,
            composition=composition,
        ),
        system=_CURATOR_SYSTEM,
    )
    data = service.request_json(prompt)
    outfits = data.get("outfits", [])
    if not isinstance(outfits, list) or not outfits:
        raise ValueError(f"Curator returned no outfits: {data}")
    # Tag each spec with its template (so the collage renders the matching layout),
    # its facet (so history avoids repeating directions), and gender presentation.
    for spec, tname, facet, gender in zip(outfits, chosen_templates, sampled_facets, genders):
        if isinstance(spec, dict):
            spec["template"] = tname
            spec["facet"] = facet
            spec["gender"] = gender
    log.info("Curator generated %d outfit spec(s)", len(outfits))
    return outfits


def review_found_products(
    outfit_spec: dict[str, Any],
    found_products: list[dict[str, Any]],
    *,
    service: ClaudeJSONService | None = None,
) -> CuratorReview:
    """Have the curator review actual search results and decide approve/reject per item."""
    service = service or make_curator_service()

    products_text = json.dumps(
        [
            {
                "index": i,
                "name": p.get("name"),
                "retailer": p.get("retailer"),
                "price": f"${p['price_cents']/100:.2f}" if p.get("price_cents") else "?",
                "category": p.get("category"),
                "url": p.get("url", "")[:80],
            }
            for i, p in enumerate(found_products)
        ],
        indent=2,
    )

    prompt = LLMPrompt(
        title="Outfit Curator: Review Found Products",
        body=_REVIEW_PROMPT.format(
            outfit_spec=json.dumps(outfit_spec, indent=2),
            found_products=products_text,
        ),
        system=_CURATOR_SYSTEM,
    )
    data = service.request_json(prompt)

    items = []
    for item in data.get("items", []):
        items.append(ReviewedProduct(
            index=item.get("index", 0),
            approved=item.get("verdict", "reject") == "approve",
            reason=item.get("reason", ""),
            refined_query=item.get("refined_query"),
        ))

    overall = data.get("overall_verdict", "reject") == "approve"
    log.info(
        "Curator review: %s — %d/%d items approved",
        "APPROVED" if overall else "REJECTED",
        sum(1 for i in items if i.approved),
        len(items),
    )
    for item in items:
        if not item.approved:
            log.info("  [%d] REJECT: %s → %s", item.index, item.reason[:80], item.refined_query)

    return CuratorReview(
        overall_approved=overall,
        rationale=data.get("rationale", ""),
        items=items,
    )


def outfit_spec_to_search_queries(outfit_spec: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert a curator or normalized pipeline spec to search_queries list.

    Carries colour/material so the near-match cache can reuse close products.
    """
    if outfit_spec.get("items"):
        return [
            {
                "query": item.get("search_query", ""),
                "category": item.get("category"),
                "color": item.get("color"),
                "material": item.get("material"),
                "limit": 5,
                "use_cached_url": item.get("use_cached_url") or None,
            }
            for item in outfit_spec["items"]
        ]
    # pipeline format: colours/materials live in parallel arrays under "outfit"
    outfit = outfit_spec.get("outfit", {}) if isinstance(outfit_spec.get("outfit"), dict) else {}
    colors = outfit.get("colors", []) or []
    materials = outfit.get("materials", []) or []
    out = []
    for i, q in enumerate(outfit_spec.get("search_queries", [])):
        if not isinstance(q, dict):
            continue
        out.append({
            "query": q.get("query", ""),
            "category": q.get("category"),
            "color": q.get("color") or (colors[i] if i < len(colors) else None),
            "material": q.get("material") or (materials[i] if i < len(materials) else None),
            "limit": q.get("limit", 5),
            "use_cached_url": q.get("use_cached_url") or None,
        })
    return out


def outfit_spec_to_pipeline_format(outfit_spec: dict[str, Any]) -> dict[str, Any]:
    """Convert curator format → existing pipeline's agent output format."""
    items = outfit_spec.get("items", [])
    return {
        "interpretation": {
            "primary_reference": outfit_spec.get("primary_reference", "concept brief"),
            "rationale": outfit_spec.get("rationale", ""),
            "used_cues": [outfit_spec.get("primary_reference", "concept brief")],
            "discarded_cues": [],
        },
        "outfit": {
            "title": outfit_spec.get("title", ""),
            "categories": [i.get("category") for i in items],
            "colors": [i.get("color") for i in items],
            "materials": [i.get("material") for i in items],
            "accessories": [],
        },
        "search_queries": outfit_spec_to_search_queries(outfit_spec),
        "diversity_notes": [],
        "template": outfit_spec.get("template"),
        "facet": outfit_spec.get("facet"),
        "gender": outfit_spec.get("gender"),
    }
