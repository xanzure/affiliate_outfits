# System Architecture

## Philosophy

Use AI for creativity. Use software engineering for everything else.

The system treats concepts as structured creative briefs. A brief can include a seed idea, context, cultural references, inspiration images or known looks, color cues, occasion, budget, required details, and avoid rules. Deterministic modules must preserve that context instead of flattening it into a generic outfit category.

Initial AI behavior is API-backed. Agent modules call the configured LLM provider, request structured JSON, and pass responses through deterministic validators before the pipeline continues.

Scheduling is concept-score based. The system begins with 8 active creative brief concepts, each starting at score `50`. A daily run selects the single top-ranked eligible concept, generates 5 outfits from that concept, creates 1 TikTok slideshow post, and creates 5 Pinterest posts spaced through the day. Concepts used today or within the previous 2 fixed-EST calendar days are ineligible. Concepts below score `25` are retired and replaced.

Every module should have:

- One responsibility
- One input
- One output
- One test suite
- One interface

---

## Pipeline

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

---

## Stage Interfaces

### Outfit Agent

Input:

- creative brief
- outfit history

Output:

- structured outfit concept
- selected products
- search strategy

The Outfit Agent is responsible for interpreting nuance. For example, a brief like "Bad Bunny summer concert outfit" should not simply become "linen summer outfit." It may produce product search intent around Puerto Rican color references, statement accessories, streetwear silhouettes, warm-weather comfort, or specific public styling references when available and appropriate.

---

### Product Pipeline

Input:

- outfit search strategy

Output:

- selected product records
- stored product candidates
- normal product URLs
- nullable affiliate URLs
- downloaded images
- metadata

The initial product source is Google Shopping through an API provider. The project must not scrape product pages or search results. Provider-specific result fields are normalized before storage so the system can later switch to affiliate catalog providers such as ShopMy, Skimlinks, or other networks without changing outfit generation, collage rendering, or the website.

Product records store `url` and `affiliate_url` separately. `url` is the standard product page used by the website today. `affiliate_url` remains null until a configured affiliate resolver can produce a tracked link.

---

### Collage Agent

Input:

- products
- images

Output:

- finished collage
- stored layout manifest with canvas and per-piece coordinates

The initial collage layer is deterministic rather than AI-backed. It stores each product image's position, size, and product ID in the database so a website can recreate the collage without reverse-engineering the final PNG.

---

### Engagement Agent

Input:

- creative brief
- outfit

Output:

- captions
- hashtags
- music category

---

### Publisher

Input:

- collage
- caption
- links

Output:

- local publish record
- optional platform identifiers when manually supplied

The publishing layer always creates local post records first. When `AUTOPOSTING_ENABLED=true`, it can publish due records through the TikTok and Pinterest APIs. TikTok photo posts and Pinterest pins require publicly reachable image URLs, so `PUBLIC_ASSET_BASE_URL` must point at wherever `data/images/...` assets are hosted.

TikTok is configured for photo slideshow posting. Pinterest posts remain scheduled locally until their due time; run `scripts/publish_due.py` from cron or another scheduler to publish due pins throughout the day.

---

### Analytics

Input:

- post ids

Output:

- metrics
- post score adjustment
- updated concept ranking score

---

### Prompt Agent

Input:

- engagement history

Output:

- replacement creative brief

---

## Data Flow

```text
Creative Brief
  -> Outfit Concept
  -> Products
  -> Images
  -> Collage
  -> Caption
  -> Publish
  -> Metrics
  -> Optimization
```

---

## Future Support

Support:

- Multiple brands
- Multiple affiliate networks
- Multiple posting schedules
- Multiple image styles
- Multiple agent models
