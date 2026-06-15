# Internal API

Everything communicates through typed interfaces.

No agent should directly call another agent.

---

## Outfit

Method:

`POST /outfit/generate`

Input:

```json
{
  "prompt": "...",
  "history": []
}
```

Output:

```json
{
  "outfit": {},
  "products": []
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
  "image_path": "..."
}
```

---

## Engagement

Method:

`POST /engagement/generate`

Input:

```json
{
  "prompt": "...",
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

## Prompt

Method:

`POST /prompt/generate`

Input:

```json
{
  "engagement_history": []
}
```

Output:

```json
{
  "new_prompt": "..."
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
