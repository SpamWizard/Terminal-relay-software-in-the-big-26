# Config reference

Config file: TOML at `config/config.toml` (override with `--config`).

Prefer the in-app **CONFIG** screen on launch — edits save to `config.toml` and apply without a text editor.

For short local debug timers, use `config/config.local.toml` (gitignored) if you add a loader override later, or edit `leg_seconds` temporarily in-app.

## Sections

| Section | Purpose |
|---------|---------|
| `[team]` | size (3–6), rotation, `[[team.people]]` id/label/color/baton_pins (Okabe–Ito colorblind-safe defaults) |
| `[timers]` | leg_seconds, game_seconds (number or `"4*60"`), leg_runs_while_frozen, debounce_ms (serial pin settle), resume_bonus_seconds (~10) |
| `[serial]` | port (`auto` or `COMx` / `/dev/ttyACM0`), baud, heartbeat_timeout_ms — RP2040 USB CDC |
| `[scoring]` | partial_credit, wrong_answer_penalty, redo_multiplier |
| `[questions]` | files (each file = board category), warmup_count, board_slots, questions_per_pick, redo_missed_at_set_end |
| `[controller]` | Xbox: enabled, device_name, inactivity_lock_seconds, unlock_hold_ms, unlock_buttons, `[controller.bindings]` |
| `[organizer]` | password_hash — reserved (CONFIG lock not wired yet) |
| `[questions].files` | JSON sets and/or challenge folders (`challenges/...`) |
| `[timers].leg_runs_while_frozen` | `false` pauses the leg during baton handoff (HC-style default) |
| `[paths]` | results_dir, checkpoint_path (mirror of the active run checkpoint) |
| `[theme]` | `name` selects a preset (default `deep_space`); optional accent/background/foreground overrides |
| `[themes.<name>]` | Named color presets (deep_space, neon_terminal, amber_grid, violet_pulse, ice, crimson, …) |
| `[ui]` | correct toast timings; `switch_sound` / `switch_sound_volume` (0–1) for change alert |

Person `color` values tint the whole game UI (background wash, borders, accents) for whoever is up.

Timer values may be plain numbers (`180`) or arithmetic strings (`"3*60"`, `"45*60"`).

Team name and player names are **not** in config — entered on the launch screen. Player numbers are assigned in entry order (`#1`, `#2`, …). Reusing a team name pops a WOAH dialog (resume unfinished, or change the name — no auto `#1`/`#2` suffixes).
