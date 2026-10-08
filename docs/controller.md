# Controller guide

Xbox / XInput-style pads via pygame (SDL). Enable/disable and rebinds apply from **CONFIG → Xbox** without restarting the app.

## In-app controls (Minecraft-style)

1. Toggle **Xbox controller** on/off, then **Save**.
2. Unlock chord chips: click to toggle which buttons must be held.
3. Action binds: click a bind → it says **Press a button…** → press that control on the pad (Esc cancels).

Footer / on-screen flash shows pad locked vs unlocked. Hold the unlock chord to unlock; inactivity re-locks. Bound actions (skip, force swap, confirm/submit, …) fire only while unlocked.

Series X pads often report the D-pad as buttons 11–14 (not a hat); those map to `DPadUp` / `Down` / `Left` / `Right`.

## Config keys

| Key | Meaning |
|-----|---------|
| `enabled` | Master switch (hot-applied) |
| `device_name` | Label |
| `inactivity_lock_seconds` | Auto-lock when idle |
| `unlock_hold_ms` | Hold time for unlock chord |
| `unlock_buttons` | Chord buttons (e.g. `LB` + `RB`, or `LT` + `DPadUp`) |
| `bindings.*` | Action → button |
