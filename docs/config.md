# Config reference (MVP)

Config file: TOML at `config/config.toml` (override with `--config`).

## Sections

| Section | Purpose |
|---------|---------|
| `[team]` | size (3–6), rotation, `[[team.people]]` id/label/color/baton_pins |
| `[timers]` | leg_seconds, game_seconds, leg_runs_while_frozen, debounce_ms |
| `[serial]` | port, baud, heartbeat_timeout_ms (serial reader later) |
| `[scoring]` | partial_credit, wrong_answer_penalty, redo_multiplier |
| `[questions]` | files (ordered), redo_missed_at_set_end |
| `[controller]` | enabled, inactivity_lock_seconds, unlock_hold_ms |
| `[organizer]` | password_hash |
| `[containers]` | runtime/limits (Linux later) |
| `[paths]` | results_dir, checkpoint_path |
| `[theme]` | neon terminal colors |

Team names are **not** in config — entered on the startup screen.
