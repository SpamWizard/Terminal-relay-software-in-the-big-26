# Terminal Relay

Needs Python 3.11 or newer.
## Setup
python -m venv .venv

Turn the venv on:

# Windows (PowerShell)
.\.venv\Scripts\Activate.ps1
# Windows (cmd)
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate

Install it:
bash
pip install -e ".[dev]"

## Start
# Real baton (board plugged in):
bash
relay run

# Fake baton (no board, use the keyboard):
relay run --fake-device
With the fake baton, click the game window, then press control `1`–`6` to put a baton in and `P` to pull it out.

# Skip the name screen and open category selection (a player is already in):
relay quick

## Scoreboard
Finished and in-progress teams in `results/` can be pushed to a SaintCon scoreboard. The game does that while `[scoreboard]` is enabled. A projector page that only displays scores is `relay board serve`. Setup, the API key, and the rank rules are in `docs/scoreboard.md`.

## HC-style challenges
Board tiles can be challenge folders under `challenges/` (see `docs/questions.md`). Each desk challenge has a `public/` folder, an in-window terminal, and a flag box. Baton freeze keeps the terminal scrollback — talk to your teammates across the handoff. Default game length is 25 minutes.
