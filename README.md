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
Finished and in-progress teams in `results/` can be pushed to a SaintCon scoreboard. Each push replaces the whole board, so list the other game PCs under `[scoreboard].peers` and every machine sends the combined list. Setup is in `docs/scoreboard.md`.

## HC-style challenges
Board tiles can be challenge folders under `challenges/` (see `docs/questions.md`). Each desk challenge has a `public/` folder, an in-window terminal, and a flag box. Baton freeze keeps the terminal scrollback — talk to your teammates across the handoff. Default game length is 25 minutes.
