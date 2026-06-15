# Internal API

Everything communicates through typed interfaces.

No agent should directly call another agent.

Creative brief payloads should be passed as structured JSON. A brief can include a display seed, but services should preserve all context fields.

AI endpoints are API-backed agents that return structured JSON. Request and response schemas still matter because deterministic validators use them before the pipeline continues.

---

## Outfit

Method:

`POST /outfit/generate`

Input:

```json
{
  "brief": {
    "seed": "Bad Bunny summer concert outfit",
    "subject": "Bad Bunny",
    "occasion": "summer concert",
    "context_notes": [
      "Puerto Rican cultural references are relevant"
    ],
    "style_cues": [
      "streetwear",
      "statement accessories"
    ],
    "required_considerations": [
      "Do not reduce this to a generic summer outfit"
    ],
    "avoid": [
      "costume styling",
      "cultural stereotypes"
    ]
  },
  "history": []
}
```

Output:

```json
{
  "outfit": {},
  "products": [],
  "interpretation": {},
  "search_queries": []
}
```

---

## Collage

Method:

`POST /collage/generate`

Input:

```json
{
  "products": []
}
```

Output:

```json
{
  "image_path": "...",
  "layout": {
    "canvas": {
      "width": 1080,
      "height": 1350
    },
    "pieces": [
      {
        "index": 0,
        "product_id": "product_123",
        "image_path": "data/images/normalized/product_123.png",
        "x": 80,
        "y": 80,
        "width": 444,
        "height": 585
      }
    ]
  }
}
```

---

## Product Search

Method:

`POST /products/search`

Input:

```json
{
  "queries": [
    {
      "query": "Puerto Rico color canvas cap concert outfit",
      "category": "hat",
      "limit": 5
    }
  ]
}
```

Output:

```json
{
  "selected_products": [
    {
      "id": "product_123",
      "retailer": "Example Retailer",
      "name": "Canvas Cap",
      "category": "hat",
      "url": "https://example.com/product",
      "affiliate_url": null,
      "image_url": "https://example.com/image.jpg",
      "local_image_path": "data/images/normalized/product_123.jpg",
      "price_cents": 2400,
      "currency": "USD"
    }
  ],
  "stored_candidates": 5
}
```

Rules:

- Use API-backed product search only; do not scrape.
- Store the normal product URL and affiliate URL separately.
- Prefer `affiliate_url` when present and fall back to `url`.
- Download product images locally before collage rendering.

---

## Engagement

Method:

`POST /engagement/generate`

Input:

```json
{
  "brief": {},
  "outfit": {}
}
```

Output:

```json
{
  "caption": "...",
  "hashtags": [],
  "music_category": "..."
}
```

---

## Concept Replacement

Method:

`POST /concept/generate`

Input:

```json
{
  "engagement_history": []
}
```

Output:

```json
{
  "new_brief": {
    "seed": "...",
    "context_notes": [],
    "style_cues": [],
    "required_considerations": [],
    "avoid": []
  }
}
```

---

## Publisher

Method:

`POST /publish`

Input:

```json
{
  "image": "...",
  "caption": "...",
  "links": []
}
```

Output:

```json
{
  "platform_ids": {}
}
```

When autoposting is enabled, the publisher maps local image paths to public URLs using `PUBLIC_ASSET_BASE_URL`, posts due TikTok/Pinterest records through platform APIs, and stores platform IDs on the post records.

TikTok slideshow posts require public photo URLs. Pinterest scheduled posts are scheduled locally; the due-post publisher sends each pin to Pinterest when its scheduled time arrives.

---

## Analytics

Method:

`GET /analytics/{post_id}`

Output:

```json
{
  "views": 0,
  "likes": 0,
  "comments": 0,
  "shares": 0,
  "saves": 0,
  "clicks": 0,
  "score": 0
}
```

---

## Scheduler

Method:

`POST /run_daily`

Runs:

- outfit generation
- collage generation
- engagement generation
- publishing

---

## Design Rules

Every endpoint should:

- Be idempotent
- Return structured json
- Never return natural language unless it is the final content
- Be independently testable
- Be independently deployable
