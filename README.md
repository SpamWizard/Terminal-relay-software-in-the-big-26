# Terminal Relay

Space-themed desktop relay app with physical baton (RP2040) identity, timed crew
rotation, extensible question types, and optional hands-on challenges (Linux later).

Package import name: `baton_relay`. CLI: `relay`.

## Quick start

```bash
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows:    .venv\Scripts\activate
pip install -e ".[dev]"
relay run --fake-device          # keyboard batons (dev / no hardware)
# relay run                    # real RP2040 baton over USB serial
# or: python -m baton_relay --fake-device
```

Opens fullscreen. Enter **team name** + **player names** (numbers `#1`… assigned
in order). **CONFIG** (top-left) edits timers, theme, serial port, and Xbox
bindings in-app.

**Real baton:** flash CircuitPython, copy `firmware/boot.py` + `firmware/code.py`
to `CIRCUITPY`, wire pins per `docs/firmware.md` / `docs/baton-wiring.md`, then
`relay run` (set `[serial].port` if auto-detect misses the board).

Reusing a team name shows a **WOAH** dialog — resume an unfinished run, or change
the name (no automatic `#1` / `#2` suffixes).

Unplug mid-leg → resume overlay shows the roster and adds ~10s (configurable)
back onto the timers.

Fake baton keys (when the game window has focus):

| Key | Action |
|-----|--------|
| `1`–`6` | Insert baton for person 1–6 |
| `0` / `U` | Unknown / bad reading |
| `P` / `Backspace` / `Space` | Pull baton out (freeze) |

While answering, hold **Ctrl** with those keys so they don’t conflict with typing.

## Reset for next team

```bash
relay reset
```

Archives active / unfinished checkpoints under `results/_archived_checkpoints/`
so the next crew can’t accidentally resume the previous run. Challenge containers
are not cleared yet (not implemented).

## Layout

- `src/baton_relay/` — application package
- `config/config.toml` — runtime config (edit in-app or by hand)
- `questions/` — question set JSON files
- `docs/` — config, questions, results, controller, wiring references
- `tests/` — unit tests

RP2040 firmware is in `firmware/`; protocol + wiring under `docs/`.

## Platforms

- **Linux** — full target (serial, Podman challenges, Xbox controller).
- **Windows** — UI, fake-device, questions, scoring, controller testing.
  Container challenges are Linux-only.

## Docs

See `docs/` for config, questions, results, serial, controller, and baton wiring.
