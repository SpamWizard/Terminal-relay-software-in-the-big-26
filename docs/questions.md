# Question format reference

Question sets are JSON files listed in `[questions].files`. **Each file is one Jeopardy-style board category** — the `title` is what players click on the board (e.g. `Potatoes.json` → title `"Potatoes"`).

```json
{
  "set_id": "potatoes",
  "title": "Potatoes",
  "questions": [ { "id": "p1", "type": "multiple_choice", "prompt": "...", "points": 10, ... } ]
}
```

## Board flow (config)

| Key | Meaning |
|-----|---------|
| `warmup_count` | Linear questions before the board (`0` = board immediately) |
| `board_slots` | How many categories shown at once |
| `questions_per_pick` | How many questions after picking a category |
| `redo_missed_at_set_end` | Redo missed within warm-up set / within a pick |

After a pick, that slot is refilled from unused categories. Timers freeze on the board. When no categories remain, the game ends.

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
| `hands_on` | `image` (container name), `ports`, `success` — containers later; flag success works now |

Every type also accepts optional pictures. The prompt text still shows. `images` is an array of **1 to 8** picture files, tiled in one framed area (1 wide, 2 side by side, 3 across, 2×2, 3 over 2, 3×2, 4 over 3, 4×2). Shorter rows are centered. Paths are relative to the question JSON file. Formats: `png`, `jpg`, `jpeg`, `gif`, `webp`, `bmp`.

A plain string is just the file. An object can add a caption under that picture:

```json
{
  "id": "topo1",
  "type": "multiple_choice",
  "prompt": "Which picture is a star topology?",
  "images": [
    "images/bus.png",
    { "src": "images/star.png", "caption": "B" }
  ],
  "points": 100,
  "choices": ["A", "B"],
  "answer": 1
}
```

`hands_on.image` is still the container image name. Picture files belong in `images`.

All files are validated at startup; the app refuses to start on errors. Missing pictures, more than 8, or an empty list fail the load.
