# Results format

Each team run creates:

```
results/<team_slug>/<UTC_timestamp>/
  events.jsonl
  checkpoint.json   # while in progress (removed when the run finishes)
  summary.json      # written at end
```

Team names must be unique. Re-entering a name that already has results shows a
**WOAH** dialog — unfinished runs with a checkpoint can **Resume**; finished
(or non-resumable) names must be changed (no automatic `#1` / `#2` suffixes).

## events.jsonl

One JSON object per line, flushed on every event. Common fields: `ts` (UTC ISO), `event`, `team`.

Events include: `game_started`, `run_resumed`, `baton_accepted`, `baton_rejected`, `baton_unknown`, `frozen`, `leg_swap`, `leg_expired`, `answer`, `skip`, `set_started`, `board_opened`, `category_selected`, `game_ended`, …

`game_ended` includes `score`, `reason`, `game_remaining`, and `leg_remaining`.

`source` is `fake`, `baton`, or `controller` when relevant.

`game_started` includes the full `roster` (`player_number`, `name`, `person_index`, `color`).

`answer` records who scored what: `player_number`, `player_name`, `question_id`, `question_prompt`, `points`, `max_points`, `correct`, `answer`, `local_time`, remaining timers, and running `total_score`.

## summary.json

Written when the game ends (timer, all categories done, etc.): team name, roster, total score, `game_remaining`, `leg_remaining`, `reason`, per-question points.
