# Terminal Relay

Desktop relay app with physical baton (RP2040) identity, timed rotation, extensible question types, and optional hands-on container challenges.

## Quick start (MVP / fake-device mode)

```bash
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows:    .venv\Scripts\activate
pip install -e ".[dev]"
relay run --fake-device
# or: python -m baton_relay --fake-device
```

Opens fullscreen. **F11** toggles windowed; **Esc** leaves fullscreen.

Fake baton keys (when the game window has focus):

| Key | Action |
|-----|--------|
| `1`–`6` | Insert baton for person 1–6 |
| `0` / `U` | Unknown / bad reading |
| `P` / `Backspace` | Pull baton out (freeze) |

While answering, hold **Ctrl** with those keys so they don’t conflict with typing.

## Reset for next team

```bash
relay reset
```

Archives the current run, clears resumable state, stops challenge containers (when enabled).

## Layout

- `src/baton_relay/` — application package
- `config/config.toml` — runtime config
- `questions/` — question set JSON files
- `docs/` — format references (growing with features)
- `firmware/` — CircuitPython (later)
- `tests/` — unit tests

## Platforms

- **Linux** — full target (serial, Podman challenges, Xbox controller).
- **Windows** — UI, fake-device, questions, scoring, controller testing. Container challenges are Linux-only.

## Docs

See `docs/` for config, questions, results, serial, controller, and baton wiring references as those features land.
