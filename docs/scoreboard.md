# SaintCon scoreboard

The game already writes one folder per team under `results/`. This publishes that list to:

```text
PUT https://saintcon.org/api/scoreboards/<id>
Authorization: Bearer <key>
Content-Type: application/json
```

Each PUT replaces the whole board. The publisher sends every team (up to 200), already in rank order.

## What gets sent

Higher points rank first. Teams with the same score share a rank, and the one that used less time is listed first. `score` is points. `detail` is the clock and how many questions they solved. `team` is the roster, shortened to fit.

A run that still has `checkpoint.json` and no `summary.json` is live. Its detail starts with `live` and shows time left. When the run finishes, the summary replaces it on the next push.

`status` is `upcoming`, `live`, `ended`, or `final`. `frozen` marks a frozen board. `message` is the line under the title (140 characters).

## Turn it on

In CONFIG → Board, or in `config/config.toml`:

```toml
[scoreboard]
enabled = true
id = "your-board-id"
status = "live"
frozen = false
message = "Finals 3 PM, Ballroom B"
interval_seconds = 60
```

`enabled` makes the game window push on its own. It sends a new board when scores change, and never more often than `interval_seconds` (minimum 15, because the API allows one push per 15 seconds). Once a minute is enough. Restart is not required after you save CONFIG; the game notices within a few seconds.

The API key is not written into `config.toml`. Set one of these before you launch:

```powershell
$env:SAINTCON_SCOREBOARD_KEY = "the-key"
```

or a single line in `config/scoreboard.key` (that file is gitignored). The environment variable wins if both are set.

## Commands

```text
relay board show          # print the JSON it would send
relay board show --out board.json
relay board push          # PUT once, even if enabled is false
relay board watch         # keep pushing without the game window
relay board serve         # projector page at http://127.0.0.1:8765
relay board serve --host 0.0.0.0 --port 8765
```

`serve` only reads `results/`. It does not push. Open it on the game PC, or bind `0.0.0.0` if the projector is another machine on the LAN. The page refreshes every few seconds.

Use either the in-game switch or `relay board watch`, not both. Two pushers will trip the 15 second limit.

`show` is the manual fallback: it writes the same JSON the curl example expects, and you can still PUT that file yourself.
