"""
Terminal Relay — baton identity firmware (CircuitPython on RP2040).

Copy this file (and optional boot.py) to the CIRCUITPY drive after flashing
CircuitPython. The host app reads heartbeats over USB CDC:

    HB pins=0b00000 seq=123

bit0 = baton pin 1 … bit4 = baton pin 5. A bit is 1 when that GPIO is
tied to GND (baton contact closed). Internal pull-ups; idle = all high.

Default pin map: GP0–GP4 + GND (Pico). Change PINS if your board differs.
"""

import time

import board
import digitalio
import usb_cdc

# Baton pin 1..5 → GPIO (Pico: GP0..GP4)
PINS = (
    board.GP0,
    board.GP1,
    board.GP2,
    board.GP3,
    board.GP4,
)

HEARTBEAT_S = 0.15


def _serial_out():
    # Prefer the data CDC (enabled in boot.py); fall back to the console.
    if usb_cdc.data is not None:
        return usb_cdc.data
    return usb_cdc.console


def main() -> None:
    dios = []
    for pin in PINS:
        dio = digitalio.DigitalInOut(pin)
        dio.switch_to_input(pull=digitalio.Pull.UP)
        dios.append(dio)

    out = _serial_out()
    seq = 0
    while True:
        mask = 0
        for i, dio in enumerate(dios):
            # Low = bridged to GND by the baton.
            if not dio.value:
                mask |= 1 << i
        seq = (seq + 1) & 0xFFFF
        line = f"HB pins=0b{mask:05b} seq={seq}\n"
        try:
            out.write(line.encode("utf-8"))
        except Exception:
            pass
        time.sleep(HEARTBEAT_S)


main()
