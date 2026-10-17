# Serial protocol

Firmware → app over USB CDC. CircuitPython writes one line per heartbeat;
`SerialBatonSource` parses them and decodes pin pairs into people.

## Line format

```
HB pins=0b00000 seq=123\n
```

| Field | Meaning |
|-------|---------|
| `pins` | 5-bit mask; bit0 = baton pin 1 … bit4 = pin 5. `1` = GPIO low (tied to GND) |
| `seq` | Optional wrapping counter (ignored by the app; useful for sniffing) |

Also accepted: `pins=0x15` or `pins=21` (same mask).

Examples:

| Line | Meaning |
|------|---------|
| `HB pins=0b00000 seq=1` | No baton (empty) |
| `HB pins=0b00011 seq=2` | Pins 1+2 → person with `baton_pins = [1, 2]` |
| `HB pins=0b00001 seq=3` | Single pin → UNKNOWN (never another person) |

## Timing

- Firmware interval: ~100–200ms (`HEARTBEAT_S` in `firmware/code.py`)
- App `[serial].heartbeat_timeout_ms` (default 1500): no valid `HB` → device
  **DISCONNECTED**; next heartbeat → reconnect (mid-leg returns to FROZEN)
- App `[timers].debounce_ms` (default 80): pin mask must stay stable this long
  before a new reading is applied (filters bounce on insert/pull)

## Port selection

`[serial].port = "auto"` prefers Raspberry Pi VID `0x2E8A` and descriptions
matching CircuitPython / Pico. Set an explicit `COM7` or `/dev/ttyACM0` if
auto-pick is wrong.

Baud defaults to `115200` (CDC ignores baud on most hosts; keep it for config).
