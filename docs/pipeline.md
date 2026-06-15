# Affiliate Content Engine Pipeline

This document defines the complete end-to-end pipeline for the system.

Every stage must have a single responsibility.

AI should only be used where subjective or creative decisions are required.

Everything else should be implemented deterministically.

The scheduler and storage layers operate on creative briefs, not generic outfit labels. A creative brief may include a simple display phrase, but it must also preserve contextual fields that the Outfit Agent can interpret later.

AI stages run through the configured LLM provider. The current provider is Anthropic Claude. Each agent requests structured JSON, and deterministic validators check the response before the pipeline continues.

Daily volume should feel human-run. The system should maintain 8 active scored concepts, select 1 top-ranked eligible concept per day, generate 5 outfits from that concept, create 1 TikTok slideshow post, create 5 Pinterest posts spaced through the day, and avoid concepts used today or within the previous 2 fixed-EST calendar days.

---

## Pipeline

### Scheduler (Deterministic)

1. Load active creative brief concepts
2. Exclude concepts posted today, yesterday, or the day before yesterday in fixed EST
3. Sort eligible concepts by ranking score, highest first
4. Select the single top-ranked eligible concept for the day
5. Pass the full brief payload forward without reducing it to a one-line phrase

---

### Outfit Agent (AI)

Implementation: Claude-backed JSON agent.

Input:

- Creative brief
- Outfit history

Responsibilities:

5. Check outfit history for that brief and related references
6. Interpret subject, occasion, cultural context, known looks, color cues, silhouettes, and avoid rules
7. Generate 5 distinct outfit specifications for the selected concept
8. Validate diversity constraints
9. Regenerate if diversity check fails
10. Normalize into structured clothing categories
11. Generate product search queries that preserve important brief cues
12. Pass search queries to the deterministic product pipeline

Output:

- Five structured outfit concepts
- Search strategy
- Interpretation rationale
- Search strategy

---

### Product Pipeline (Deterministic)

15. Search Google Shopping through an API provider, never scraping
16. Normalize result fields into internal product candidates
17. Block suspicious retailers and allow conditional cheap/accessory retailers only for low-stakes categories
18. Prefer cheaper safe items while preserving the API-backed candidate set
19. Store accepted candidates, including price, retailer, normal URL, image URL, source metadata, and candidate rank
20. Select one product per outfit search slot for the actual outfit
21. Resolve affiliate URL only when a configured affiliate resolver is available
22. Download product image
23. Verify image quality
24. Remove background
25. Normalize image size/orientation

Output:

- Clean product assets

---

### Collage Renderer (Deterministic)

Initial implementation: deterministic collage rendering. A subjective layout agent can be added later if needed.

Input:

- Product images
- Product metadata

Responsibilities:

26. Generate collage layout
27. Place products into layout
28. Add text / branding / numbering
29. Store canvas and per-piece placement data for website recreation

Output:

- Final collage design
- Collage layout manifest with canvas dimensions, product IDs, image paths, and x/y/width/height for each piece

---

### Image Export (Deterministic)

30. Export final image

Output:

- Publishable image asset

---

### Engagement Agent (AI)

Implementation: Claude-backed JSON agent.

Input:

- Creative brief
- Outfit set

Responsibilities:

31. Generate one TikTok slideshow caption
32. Generate five Pinterest titles/descriptions
33. Generate hashtags
34. Select music category
35. Select trending sound from internal library

Output:

- Platform copy
- Hashtags
- Audio selection

---

### Publishing (Deterministic)

36. Generate landing page (optional)
37. Attach affiliate links when links are available, otherwise attach normal product URLs
38. Create one local TikTok slideshow record and five scheduled Pinterest records
39. If autoposting is disabled, keep local draft/scheduled records only
40. If autoposting is enabled, publish due TikTok/Pinterest records through platform APIs
41. Store platform identifiers and API responses when posting succeeds
42. Mark failed posts with API error metadata for retry/debugging

Output:

- Mirrored local draft records
- Platform identifiers

---

### Analytics (Deterministic)

43. Wait for collection window
44. Accept manually supplied views
45. Accept manually supplied likes
46. Accept manually supplied comments
47. Accept manually supplied shares
48. Accept manually supplied saves
49. Accept manually supplied affiliate clicks
50. Compute engagement score
51. Convert post performance into a concept score adjustment
52. Update the concept ranking score
53. Clamp concept score between 0 and 100
54. Retire concepts below 25

Output:

- Updated metrics
- Updated concept ranking score
- Concept performance history

---

### Prompt Agent (AI)

Implementation: Claude-backed JSON agent.

Input:

- Engagement history

Responsibilities:

55. Generate replacement creative brief when a concept retires
56. Add replacement brief to the `needs_review` pool

Output:

- New replacement concept awaiting approval

---

### Storage (Deterministic)

57. Store all assets, metadata, metrics, briefs, and history

---

## Agent Boundaries

### Outfit Agent

Responsible for:

- outfit generation
- creative brief interpretation
- diversity
- product search
- product candidate ranking and selection

Not responsible for:

- image processing
- publishing
- analytics

---

### Collage Agent

Responsible for:

- visual composition
- spacing
- branding
- layout

Not responsible for:

- downloading images
- removing backgrounds
- exporting files

---

### Engagement Agent

Responsible for:

- captions
- descriptions
- hashtags
- music selection

Not responsible for:

- publishing
- analytics

---

### Prompt Agent

Responsible for:

- generating replacement creative briefs
- maintaining concept freshness

Not responsible for:

- engagement calculation
- retirement logic

---

## Core Principle

The system should always follow:

```text
Creative Brief
  -> Outfit Agent
  -> Product Pipeline
  -> Collage Agent
  -> Image Export
  -> Engagement Agent
  -> Publishing
  -> Analytics
  -> Prompt Agent
  -> Repeat
```

No agent should call another agent directly.

Every stage should accept a typed input, produce a typed output, and be independently executable and testable.

Deterministic stages should never erase the original brief context. If an agent needs a simplified display phrase, that phrase should be derived in addition to the full brief, not instead of it.
