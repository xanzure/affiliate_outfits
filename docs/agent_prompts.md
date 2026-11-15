# Agent Prompt Documentation

This document defines the purpose, requirements, versioning, and evaluation approach for LLM prompts used by each agent.

Prompts are instructions sent to an LLM. Concepts are the tracked content ideas that are scheduled, scored, posted, and retired.

## Creative Brief Model

In this project, a concept is a structured creative brief, not a direct mapping to a generic outfit phrase.

A brief should preserve:

- seed idea
- subject or reference
- occasion
- audience or platform context
- cultural, regional, music, celebrity, event, or era cues
- colors, textures, silhouettes, accessories, and styling motifs
- known looks or reference links when available
- budget or retailer constraints
- required considerations
- avoid rules
- notes on what must not be oversimplified

Example:

```json
{
  "seed": "Bad Bunny summer concert outfit",
  "subject": "Bad Bunny",
  "occasion": "summer concert",
  "context_notes": [
    "Puerto Rican cultural references are relevant",
    "Consider Puerto Rican colors or motifs when tasteful",
    "Reference recognizable styling cues from public looks when available"
  ],
  "style_cues": [
    "streetwear",
    "statement sunglasses",
    "playful proportion",
    "warm-weather comfort"
  ],
  "required_considerations": [
    "Preserve the subject-specific nuance",
    "Do not collapse this into a generic summer outfit"
  ],
  "avoid": [
    "costume styling",
    "cultural stereotypes",
    "unsupported claims"
  ]
}
```

The deterministic system stores and routes this brief. The agents interpret it.

---

## Outfit Agent Prompt

Purpose:

Generate five distinct outfit concepts that interpret the same full creative brief while maintaining variety.

Inputs:

- creative brief
- previous outfits

Constraints:

- no more than two repeated core styling elements across the five outfits
- realistic products
- cohesive aesthetic
- output structured json
- preserve brief-specific nuance
- explain which brief cues influenced the outfit
- include culturally specific or reference-specific details only when tasteful, grounded, and product-searchable
- avoid turning a person, place, music reference, or event into a generic aesthetic shortcut

Notes:

The output should include each outfit and its interpretation rationale. For example, if the brief references Bad Bunny, the agent may select streetwear silhouettes, Puerto Rican color cues, statement accessories, or references to known public styling patterns. It should not merely output "linen summer outfit" unless that is explicitly justified by the brief.

Suggested output shape:

```json
{
  "outfits": [
    {
      "interpretation": {
        "primary_reference": "...",
        "used_cues": [],
        "discarded_cues": [],
        "rationale": "..."
      },
      "outfit": {
        "title": "...",
        "categories": [],
        "colors": [],
        "materials": [],
        "accessories": []
      },
      "search_queries": [],
      "diversity_notes": []
    }
  ]
}
```

---

## Collage (no prompt)

The collage stage was planned as an agent but shipped deterministic: layouts are
declarative HTML/CSS templates chosen by the outfit curator before sourcing (see
[pipeline.md](pipeline.md#collage-renderer-deterministic)). Design goals carried
over from the original prompt spec:

- neutral background
- consistent spacing
- premium feel
- minimal typography
- product focused

The one subjective call left — a shared background, accent, and type style per
batch, so the five collages read as a set — is made by a small style agent
(`app/agents/collage/style_agent.py`) and passed to the renderer as data.

---

## Engagement Agent Prompt

Purpose:

Generate content optimized for engagement.

Outputs:

- TikTok caption
- Pinterest description
- hashtags
- music category

Constraints:

- short
- searchable
- natural
- preserve the creative brief's nuance without overexplaining it
- do not make cultural references feel forced or tokenized

Notes:

TBD

---

## Prompt Agent Prompt

Purpose:

Generate replacement creative briefs when scored concepts are retired.

Requirements:

- evergreen
- fashion focused
- high engagement potential
- enough context to guide nuanced outfit selection
- can include a short display phrase, but must also include structured brief fields
- replacement concepts start with ranking score `50`
- maintain a pool of 8 active concepts
- avoid duplicating active concepts

Notes:

The Prompt Agent should not only generate labels like "summer outfit." It should generate brief seeds with interpretable context, such as subject, occasion, style cues, constraints, and avoid rules.

The Prompt Agent should see the retired concept, its score history, current active concepts, and any user notes. It should generate a replacement concept that enters `needs_review` until approved.

---

## Concept Versioning

Every concept should be version controlled.

Record:

- date
- model
- temperature
- changes
- performance
- brief schema version
- source of reference context
- what nuance was added or removed

---

## Evaluation

Every concept should be measurable.

Metrics:

- views
- likes
- shares
- saves
- affiliate clicks
- CTR
- engagement score
- concept ranking score
- score adjustment
