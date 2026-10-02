# Results format (MVP)

Each team run creates:

```
results/<team_slug>/<UTC_timestamp>/
  events.jsonl
  summary.json
```

## events.jsonl

One JSON object per line, flushed on every event. Common fields: `ts`, `event`, `team`.

Events include: `game_started`, `baton_accepted`, `baton_rejected`, `baton_unknown`, `frozen`, `leg_swap`, `leg_expired`, `answer`, `skip`, `set_started`, `game_ended`, …

`source` is `fake`, `baton`, or `controller` when relevant.

## summary.json

Written when the game ends (timer or all questions done): team name, total score, per-question points.
