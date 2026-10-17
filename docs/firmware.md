# Firmware setup (RP2040 / CircuitPython)

Physical baton identity for Terminal Relay. Files live in `firmware/`.

## 1. Flash CircuitPython

1. Hold **BOOTSEL** on the RP2040 board, plug in USB, release BOOTSEL.
2. A `RPI-RP2` (or similar) drive appears.
3. Download the matching CircuitPython UF2 from
   [circuitpython.org](https://circuitpython.org/downloads) (Pico, Feather RP2040, …).
4. Copy the `.uf2` onto that drive — the board reboots as `CIRCUITPY`.

## 2. Install the relay firmware

Copy both files onto `CIRCUITPY` (overwrite if present):

| File | Role |
|------|------|
| `firmware/boot.py` | Enables a second USB CDC (`data`) for heartbeats |
| `firmware/code.py` | Reads 5 GPIO pins and prints `HB …` lines |

After copy, the board reboots. You should see a serial port named something like
**CircuitPython CDC** / **USB Serial** (Windows: `COMx`, Linux: `/dev/ttyACM*`).

## 3. Wire the batons

5 GPIO inputs + GND. Each baton bridges **exactly two** pins to GND.
See [baton-wiring.md](baton-wiring.md).

Default map in `code.py` (Raspberry Pi Pico):

| Baton pin | Pico GPIO | Physical pin |
|-----------|-----------|--------------|
| 1 | GP0 | 1 |
| 2 | GP1 | 2 |
| 3 | GP2 | 4 |
| 4 | GP3 | 5 |
| 5 | GP4 | 6 |
| GND | GND | 3, 8, 13, … |

Edit the `PINS` tuple in `code.py` if your board uses different pads.

Internal pull-ups: a pin reads **low** when shorted to GND.

## 4. Run the app

In `config/config.toml` (or **CONFIG → Serial**):

```toml
[serial]
port = "auto"          # or e.g. "COM7" / "/dev/ttyACM0"
baud = 115200
heartbeat_timeout_ms = 1500
```

```bash
relay run
```

Omit `--fake-device` so the app opens the RP2040. Status shows the port when
heartbeats arrive; missing heartbeats → **DISCONNECTED** (use Xbox override or
replug).

Keyboard fake mode remains available: `relay run --fake-device`.

## Heartbeat format

```
HB pins=0b00000 seq=123
```

- Every ~150ms from firmware
- `pins` bitmask: bit0 = pin 1 … bit4 = pin 5; `1` = tied to GND
- Protocol details: [serial-protocol.md](serial-protocol.md)
