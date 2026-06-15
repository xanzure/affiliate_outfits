# System Architecture

## Philosophy

Use AI for creativity. Use software engineering for everything else.

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

- prompt
- outfit history

Output:

- structured outfit
- selected products

---

### Product Pipeline

Input:

- structured outfit

Output:

- affiliate products
- images
- metadata

---

### Collage Agent

Input:

- products
- images

Output:

- finished collage

---

### Engagement Agent

Input:

- prompt
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

- TikTok post
- Pinterest post

---

### Analytics

Input:

- post ids

Output:

- metrics
- engagement score

---

### Prompt Agent

Input:

- engagement history

Output:

- replacement prompt

---

## Data Flow

```text
Prompt
  -> Outfit
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
