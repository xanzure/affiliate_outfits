# Affiliate Content Engine Pipeline

This document defines the complete end-to-end pipeline for the system.

Every stage must have a single responsibility.

AI should only be used where subjective or creative decisions are required.

Everything else should be implemented deterministically.

---

## Pipeline

### Scheduler (Deterministic)

1. Load active prompt list
2. Determine which prompts need posts today
3. Determine how many outfits to generate per prompt

---

### Outfit Agent (AI)

Input:

- Prompt
- Outfit history

Responsibilities:

4. Check outfit history for that prompt
5. Generate new outfit specification
6. Validate diversity constraints
7. Regenerate if diversity check fails
8. Normalize into structured clothing categories
9. Generate retailer search queries
10. Search affiliate retailers
11. Rank matching products
12. Select best products

Output:

- Structured outfit
- Selected products

---

### Product Pipeline (Deterministic)

13. Retrieve affiliate link
14. Download product image
15. Verify image quality
16. Remove background
17. Normalize image size/orientation

Output:

- Clean product assets

---

### Collage Agent (AI)

Input:

- Product images
- Product metadata

Responsibilities:

18. Generate collage layout
19. Place products into layout
20. Add text / branding / numbering

Output:

- Final collage design

---

### Image Export (Deterministic)

21. Export final image

Output:

- Publishable image asset

---

### Engagement Agent (AI)

Input:

- Prompt
- Outfit

Responsibilities:

22. Generate TikTok caption
23. Generate Pinterest description
24. Generate hashtags
25. Select music category
26. Select trending sound from internal library

Output:

- Platform copy
- Hashtags
- Audio selection

---

### Publishing (Deterministic)

27. Generate landing page (optional)
28. Attach affiliate links
29. Upload TikTok
30. Upload Pinterest
31. Store post IDs

Output:

- Published posts
- Platform identifiers

---

### Analytics (Deterministic)

32. Wait for collection window
33. Collect views
34. Collect likes
35. Collect comments
36. Collect shares
37. Collect saves
38. Collect affiliate clicks
39. Compute engagement score
40. Update prompt statistics
41. Check engagement trend
42. Increment/reset decline counter
43. Retire prompt if necessary

Output:

- Updated metrics
- Prompt performance history

---

### Prompt Agent (AI)

Input:

- Engagement history

Responsibilities:

44. Generate replacement prompt
45. Add replacement prompt to active pool

Output:

- New active prompt

---

### Storage (Deterministic)

46. Store all assets, metadata, metrics, and history

---

## Agent Boundaries

### Outfit Agent

Responsible for:

- outfit generation
- diversity
- retailer search
- product selection

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

- generating replacement prompts
- maintaining prompt freshness

Not responsible for:

- engagement calculation
- retirement logic

---

## Core Principle

The system should always follow:

```text
Prompt
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
