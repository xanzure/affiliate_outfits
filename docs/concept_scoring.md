# Concept Selection And Scoring

The system should feel like a human-run affiliate account, not a content farm.

The operating target is:

- 8 active concepts at a time
- 1 concept selected per day
- 5 outfits generated from that concept
- 1 TikTok slideshow post containing all 5 outfits
- 5 Pinterest posts, one per outfit
- Posts go out through an approval queue, at most one per platform per cooldown window (default 24h)
- A concept should not be posted on the same EST calendar day or within the previous 2 EST calendar days
- New concepts start with a ranking score of `50`
- Concepts are retired when their ranking score drops below `25`
- Retired concepts are replaced through the Prompt Agent

## Concepts

A concept is a tracked creative brief. Examples:

- Bad Bunny summer concert outfit
- Dark academia rainy campus outfit
- Coastal grandmother workday outfit
- Black boots fall capsule outfit under 150

The concept score belongs to the creative brief, not to a single platform post.

## Daily Selection

Each daily run should:

1. Load active concepts.
2. Exclude concepts posted today, yesterday, or the day before yesterday in fixed EST.
3. Sort remaining concepts by ranking score, highest first.
4. Select the single top-ranked eligible concept.
5. Generate 5 outfits and 5 collages for that concept.
6. Create one local TikTok slideshow record containing all 5 outfits.
7. Create 5 local Pinterest records, one per outfit.

All records start as drafts awaiting approval; see [autoposting.md](autoposting.md)
for how approved posts are queued and published.

If no eligible concept exists, the system should report the shortage and skip the daily run.

Concept-eligibility dates use fixed EST (`UTC-05:00`) rather than local machine
time, so "posted today" means the same thing on a laptop and on a cloud worker.

## Platform Posting Shape

TikTok and Pinterest should share the same daily concept, outfit set, products, collage assets, and affiliate links.

TikTok should create:

- 1 local slideshow-style post
- metadata listing all 5 outfit IDs
- metadata listing all 5 collage image paths

Pinterest should create:

- 5 local draft posts
- 1 outfit/collage per post

This means 1 daily concept produces 6 platform records: 1 TikTok record and 5 Pinterest records.

## Ranking Score

Each new concept starts at:

```text
ranking_score = 50
```

Manual metrics should adjust the score after posts collect enough data.

The first implementation should use a deterministic score adjustment, not a decline-counter system.

Suggested initial behavior:

- great performance increases score by `+10`
- good performance increases score by `+5`
- average performance leaves score unchanged
- weak performance decreases score by `-5`
- bad performance decreases score by `-10`
- score should be clamped between `0` and `100`
- retire when score is below `25`

The first scoring formula derives a weighted engagement rate from mirrored TikTok and Pinterest metrics:

```text
weighted_actions = likes + comments*3 + shares*4 + saves*5 + clicks*8
weighted_engagement_rate = weighted_actions / views * 100
```

Bands:

- `great`: weighted engagement rate >= 12
- `good`: weighted engagement rate >= 6
- `average`: weighted engagement rate >= 2
- `weak`: weighted engagement rate >= 0.75
- `bad`: weighted engagement rate < 0.75

Manual metrics can also include an explicit `performance_band` override when the user wants to classify performance directly.

## Manual Metrics Input

Manual metrics are imported from JSON:

```json
{
  "concept_id": "concept_123",
  "collection_window": "manual",
  "metrics": [
    {
      "post_id": "post_tiktok",
      "views": 1000,
      "likes": 70,
      "comments": 6,
      "shares": 8,
      "saves": 12,
      "clicks": 10
    },
    {
      "post_id": "post_pinterest",
      "views": 800,
      "likes": 20,
      "comments": 2,
      "shares": 6,
      "saves": 30,
      "clicks": 18
    }
  ]
}
```

Run:

```bash
python3 scripts/backfill_metrics.py path/to/metrics.json
```

Each platform post gets its own metric record. The concept receives one combined score adjustment.

## Retirement

A concept retires when:

```text
ranking_score < 25
```

Retirement means:

- the concept is no longer eligible for daily posting
- its history remains stored
- the Prompt Agent can generate a replacement concept

Replacement concepts should start at `50`, but enter `needs_review` until approved.

Run the replacement workflow after a concept retires:

```bash
python3 scripts/generate_replacement_concept.py <retired_concept_id>
```

For testing without an API call, pass a saved JSON response:

```bash
python3 scripts/generate_replacement_concept.py <retired_concept_id> --response-file data/llm_responses/sample_replacement_concept_response.json
```

## What This Replaces

This replaces the earlier decline-counter idea.

The system should not require daily metrics for every concept. Instead, each concept carries a persistent ranking score that moves up or down whenever new post metrics are entered.
