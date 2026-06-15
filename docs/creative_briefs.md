# Creative Briefs

Creative briefs are the source material for outfit generation. They are intentionally richer than simple outfit labels.

A creative brief is the structured payload inside a concept. The concept is the tracked database object; the brief is the creative context the agents interpret.

The system should support briefs based on:

- celebrities or artists
- songs, albums, tours, or events
- cities, regions, or cultural references
- aesthetics and moods
- occasions
- seasons and weather
- budget or retailer constraints
- platform trends

## Why Briefs Exist

A one-line concept label can lose the reason an outfit should feel specific.

Bad example:

```text
Bad Bunny -> linen summer outfit
```

This loses too much information. It ignores the artist reference, performance context, Puerto Rican cultural cues, possible colors, accessories, silhouettes, and styling history.

Better example:

```json
{
  "seed": "Bad Bunny summer concert outfit",
  "subject": "Bad Bunny",
  "occasion": "summer concert",
  "context_notes": [
    "Puerto Rican cultural references are relevant",
    "Look for tasteful color references, especially red, white, and blue",
    "Known styling references may include streetwear, playful accessories, relaxed silhouettes, and bold sunglasses"
  ],
  "style_cues": [
    "streetwear",
    "warm-weather comfort",
    "statement accessories",
    "music-event styling"
  ],
  "required_considerations": [
    "Preserve the artist-specific reference",
    "Include at least one brief-specific detail when product availability allows"
  ],
  "avoid": [
    "costume styling",
    "cultural stereotypes",
    "generic vacation outfit",
    "unsupported claims"
  ]
}
```

## Recommended Fields

- `seed`: short human-readable idea
- `subject`: person, place, event, song, trend, or aesthetic being referenced
- `occasion`: where the outfit would be worn
- `audience`: intended viewer or shopper
- `context_notes`: important background the agent should consider
- `style_cues`: silhouette, mood, category, texture, accessory, or styling notes
- `color_cues`: colors or palette guidance
- `reference_links`: optional URLs or source notes for known looks
- `budget`: price range or affordability constraint
- `retailer_constraints`: preferred or excluded retailers
- `required_considerations`: details the outfit should try to honor
- `avoid`: stereotypes, costume risk, overused ideas, or brand safety constraints
- `metadata`: version, source, campaign, and evaluation tags
- `ranking_score`: concept-level score used for scheduling, default `50`

## Deterministic Responsibilities

Deterministic components should:

- store the complete brief
- preserve the brief payload across pipeline stages
- select top-ranked eligible briefs without rewriting their creative meaning
- track usage, engagement, ranking score, and retirement at the brief level
- validate that required fields exist

Deterministic components should not:

- convert nuanced references into generic outfit labels
- discard cultural or context notes
- decide the creative interpretation
- infer sensitive meaning beyond what is explicitly stored

## Agent Responsibilities

Agents should:

- interpret the brief into clothing categories and search queries
- explain which cues were used
- explain which cues were discarded and why
- keep cultural references tasteful and grounded
- avoid stereotypes or costume-like styling
- produce structured output that deterministic services can test and store
