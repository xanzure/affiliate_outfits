# Terminology

This project uses `concept` and `prompt` for different things.

## Concept

A concept is a tracked content idea.

Concepts are stored in the database, scheduled, scored, posted, and retired.

Examples:

- Bad Bunny summer concert outfit
- Dark academia rainy campus outfit
- Coastal grandmother workday outfit

A concept contains a structured creative brief with fields such as:

- seed
- subject
- occasion
- context notes
- style cues
- color cues
- avoid rules
- ranking score

Use `concept` in code and docs when referring to:

- scheduler inputs
- database records
- active/retired content ideas
- ranking scores
- daily posting eligibility
- replacement ideas

## Prompt

A prompt is an instruction sent to an LLM.

Prompts are not scheduled or scored. They are templates or generated text used to ask an LLM for structured output.

Use `prompt` only when referring to:

- provider request instructions
- LLM request text
- prompt template files
- agent prompt builders
- the Prompt Agent, which generates replacement concept drafts

## Rule Of Thumb

If it can be posted, ranked, retired, or replaced, it is a concept.

If it is copied into an LLM, it is a prompt.
