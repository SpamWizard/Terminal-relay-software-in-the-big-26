# Config reference

Config file: TOML at `config/config.toml` (override with `--config`).

Prefer the in-app **CONFIG** screen on launch. Edits save to `config.toml` and apply without a text editor. Short debug timers are set there, or by editing `leg_seconds` in the file. `config/config.local.toml` is gitignored; the app does not load it.

## Sections

| Section | Purpose |
|---------|---------|
| `[team]` | size (3–6), rotation, `[[team.people]]` id/label/color/baton_pins (Okabe–Ito colorblind-safe defaults) |
| `[timers]` | leg_seconds, game_seconds (number or `"4*60"`), leg_runs_while_frozen, debounce_ms (serial pin settle), resume_bonus_seconds (~10) |
| `[serial]` | port (`auto` or `COMx` / `/dev/ttyACM0`), baud, heartbeat_timeout_ms — RP2040 USB CDC |
| `[scoring]` | partial_credit, wrong_answer_penalty, redo_multiplier |
| `[questions]` | files (each file = board category), warmup_count, board_slots, questions_per_pick, redo_missed_at_set_end |
| `[controller]` | Xbox: enabled, device_name, inactivity_lock_seconds, unlock_hold_ms, unlock_buttons, `[controller.bindings]` |
| `[organizer]` | `password_hash`, stored only; the app does not prompt for it |
| `[questions].files` | JSON sets and/or challenge folders (`challenges/...`) |
| `[timers].leg_runs_while_frozen` | `false` pauses the leg during a baton handoff |
| `[paths]` | results_dir, checkpoint_path (mirror of the active run checkpoint) |
| `[theme]` | `name` selects a preset (default `deep_space`); optional accent/background/foreground overrides |
| `[themes.<name>]` | Named color presets (deep_space, neon_terminal, amber_grid, violet_pulse, ice, crimson, …) |
| `[ui]` | correct toast timings; `switch_sound` / `switch_sound_volume` (0–1) for change alert |

Person `color` values tint the whole game UI (background wash, borders, accents) for whoever is up.

Timer values may be plain numbers (`180`) or arithmetic strings (`"3*60"`, `"45*60"`).

Team name and player names are entered on the launch screen, not in this file. Player numbers follow entry order (`#1`, `#2`, …). Reusing a team name opens a dialog: an unfinished run can be resumed, and a finished name has to be changed. The app does not add `#1` / `#2` suffixes.
