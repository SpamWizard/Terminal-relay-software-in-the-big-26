# Serial protocol (planned)

Firmware → app over USB CDC serial. Not implemented in the app yet (`relay run`
always falls back to `--fake-device`).

Planned line format (CircuitPython):

```
HB pins=0b00000 seq=123\n
```

- Heartbeat every ~100–200ms
- `pins` bitmask: bit0=pin1 … bit4=pin5, 1 = tied to GND
- App treats missing heartbeats beyond `heartbeat_timeout_ms` as DISCONNECTED

Exact framing will be locked when the board reader lands.
