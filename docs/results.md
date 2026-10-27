# Results format

Each team run creates:

```
results/<team_slug>/<UTC_timestamp>/
  events.jsonl
  checkpoint.json   # while in progress (removed when the run finishes)
  summary.json      # written at end
```

Team names must be unique. Re-entering a name that already has results opens a dialog. An unfinished run with a checkpoint can be resumed. A finished name has to be changed. The app does not add `#1` / `#2` suffixes.

## events.jsonl

One JSON object per line, flushed on every event. Common fields: `ts` (UTC ISO), `event`, `team`.

Events include: `game_started`, `run_resumed`, `baton_accepted`, `baton_rejected`, `baton_unknown`, `frozen`, `leg_swap`, `leg_expired`, `answer`, `skip`, `set_started`, `board_opened`, `category_selected`, `game_ended`, …

`source` is `fake`, `baton`, or `controller` when relevant.

`game_started` includes the full `roster` (`player_number`, `name`, `person_index`, `color`).

`answer` records everything needed to score that response: category (`set_id`, `set_title`), prompt, question point value, who answered (`player_number`, `player_name`), what they submitted (`answer` plus readable `answer_text`), the key (`expected_text`), `points`, `max_points`, `correct`, `partial`, `redo`, running `total_score`, `local_time`, `time_used` / `time_used_seconds`, and both clocks remaining.

`skip` records the same question identity, who skipped, and `points: 0`.

`game_ended` includes `score`, `reason`, `time_used`, `time_used_seconds`, `game_limit_seconds`, `game_remaining`, `leg_remaining`, and `local_time`.

## summary.json

Written when the game ends. This is the score sheet:

- `team`, `roster`, `started_at`, `finished_at`, `reason`
- `score`, `time_used`, `time_used_seconds`, `game_limit_seconds`, `game_remaining`, `leg_remaining`
- `players`: points that counted, per player
- `counted_answers`: the last answer for each question (redos replace the earlier one)
- `attempts`: every answer and skip, in order, with prompt, submitted answer, expected answer, and points

`time_used` is the game clock (allotted time minus time left), not wall-clock time. Resume bonuses that add time back shorten it.

## Scoreboard Pi

When `[scoreboard].enabled` is true, writing `summary.json` also POSTs that run to the Scoreboard Pi (`POST /api/v1/runs`). The game client never talks to saintcon.org.

- Auth: `Authorization: Bearer <pi-ip>` (same string as the host in `base_url`)
- Body: `{ machine_id, submitted_at, summary }` where `summary` is the exact `summary.json` object
- Success writes a `scoreboard_submitted` marker in the run folder
- Failures are logged and queued in `data/scoreboard_pending.jsonl` for retry (same payload; Pi upsert is idempotent). The queue is drained periodically — the app does **not** scan/upload the whole `results/` tree on startup.
