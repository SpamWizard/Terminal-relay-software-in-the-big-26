# Config reference (MVP)

Config file: TOML at `config/config.toml` (override with `--config`).

## Sections

| Section | Purpose |
|---------|---------|
| `[team]` | size (3–6), rotation, `[[team.people]]` id/label/color/baton_pins (Okabe–Ito colorblind-safe defaults) |
| `[timers]` | leg_seconds, game_seconds (number or `"4*60"`), leg_runs_while_frozen, debounce_ms |
| `[serial]` | port, baud, heartbeat_timeout_ms (serial reader later) |
| `[scoring]` | partial_credit, wrong_answer_penalty, redo_multiplier |
| `[questions]` | files (ordered), redo_missed_at_set_end |
| `[controller]` | enabled, inactivity_lock_seconds, unlock_hold_ms |
| `[organizer]` | password_hash |
| `[containers]` | runtime/limits (Linux later) |
| `[paths]` | results_dir, checkpoint_path |
| `[theme]` | `name` selects a preset; optional accent/background/foreground overrides |
| `[themes.<name>]` | Named color presets (neon_terminal, amber_grid, violet_pulse, ice, crimson, …) |
| `[ui]` | correct toast timings; `switch_sound` / `switch_sound_volume` (0–1) for change alert |

Person `color` values tint the whole game UI (background wash, borders, accents) for whoever is up.

Timer values may be plain numbers (`180`) or arithmetic strings (`"3*60"`, `"45*60"`). Restart the app after config edits.

Team names are **not** in config — entered on the startup screen.
