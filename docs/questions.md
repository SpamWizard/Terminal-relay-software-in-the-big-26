# Question format reference (MVP)

Question sets are JSON files listed in `[questions].files`.

```json
{
  "set_id": "warmup",
  "title": "Warm-up",
  "questions": [ { "id": "w1", "type": "multiple_choice", "prompt": "...", "points": 10, ... } ]
}
```

## Types

| type | Key fields |
|------|------------|
| `multiple_choice` | `choices[]`, `answer` (index) |
| `select_all` | `choices[]`, `answer` (index array) |
| `put_in_order` | `items[]`, `answer` (index order) |
| `match_up` | `left[]`, `right[]`, `answer` `{ "0": 1, ... }` |
| `short_answer` | `accepted[]`, `case_sensitive`, `strip_whitespace` |
| `numeric` | `answer`, `tolerance` |
| `fill_blank` | same as short_answer |
| `flag` | `accepted[]` (usually case-sensitive) |
| `hands_on` | `image`, `ports`, `success` — containers later; flag success works now |

All files are validated at startup; the app refuses to start on errors.
