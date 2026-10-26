# SaintCon scoreboard

The game already writes one folder per team under `results/`. This publishes that list to:

```text
PUT https://saintcon.org/api/scoreboards/<id>
Authorization: Bearer <key>
Content-Type: application/json
```

Each PUT replaces the whole board. The publisher sends every team it knows about (up to 200), already in rank order. With more than one game PC, each machine pulls the others first so a push from either one still contains every team.

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
peers = ["http://192.168.1.21:8765"]
listen = "0.0.0.0"
listen_port = 8765
machine = "lane 1"
```

## More than one machine

SaintCon stores only the most recent push. If lane 1 sends its teams and then lane 2 sends only its own, lane 1 disappears. Both games avoid that by trading standings on the LAN and merging before the PUT.

On each PC, `peers` is the other PCs, not itself:

```toml
# lane 1
peers = ["http://192.168.1.21:8765"]

# lane 2
peers = ["http://192.168.1.20:8765"]
```

While the game is open (scoreboard enabled, or any peer listed), it listens on `listen_port` (8765). The startup line prints the address to put on the other machine. `http://<that-address>:8765/standings.json` is this PC's teams only. The projector page and the SaintCon push use the merged list.

A peer that drops off the network stays on the board from the last copy we got, for 8 hours. What is shared is the score, the clock, solves, and the roster. Answer keys stay on the machine that ran the team.

Both games can have `enabled` on. Each push already includes everyone. If they push in the same 15 seconds, one may be told to wait; the next interval sends the full board again.

`relay board serve` on a third PC shows the same merged list and does not push. Give that PC the same `peers`.

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

`serve` shows the merged board and does not push. The page refreshes every few seconds.

On one PC, use either the in-game switch or `relay board watch`, not both. Two pushers on the same PC will trip the 15 second limit. Two different game PCs can both push, because each one already includes the other's teams.

`show` is the manual fallback: it writes the same JSON the curl example expects, and you can still PUT that file yourself.
