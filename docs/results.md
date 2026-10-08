# Results format (MVP)

Each team run creates:

```
results/<team_slug>/<UTC_timestamp>/
  events.jsonl
  summary.json
```

## events.jsonl

One JSON object per line, flushed on every event. Common fields: `ts` (UTC ISO), `event`, `team`.

Events include: `game_started`, `baton_accepted`, `baton_rejected`, `baton_unknown`, `frozen`, `leg_swap`, `leg_expired`, `answer`, `skip`, `set_started`, `game_ended`, …

`source` is `fake`, `baton`, or `controller` when relevant.

`game_started` includes the full `roster` (`player_number`, `name`, `person_index`, `color`).

`answer` records who scored what: `player_number`, `player_name`, `question_id`, `question_prompt`, `points`, `max_points`, `correct`, `answer`, `local_time`, remaining timers, and running `total_score`.

## summary.json

Written when the game ends (timer or all questions done): team name, roster, total score, per-question points.
