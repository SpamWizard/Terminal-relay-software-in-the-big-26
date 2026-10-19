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


def _outputs():
    """Console and data CDC, non-blocking.

    Windows often exposes only one of the two ports. Writing only to data,
    and blocking when that port has no reader, makes the visible port silent.
    """
    ports = []
    for port in (usb_cdc.console, usb_cdc.data):
        if port is None:
            continue
        try:
            port.timeout = 0
        except Exception:
            pass
        ports.append(port)
    return ports


def main() -> None:
    dios = []
    for pin in PINS:
        dio = digitalio.DigitalInOut(pin)
        dio.switch_to_input(pull=digitalio.Pull.UP)
        dios.append(dio)

    outs = _outputs()
    seq = 0
    while True:
        mask = 0
        for i, dio in enumerate(dios):
            # Low = bridged to GND by the baton.
            if not dio.value:
                mask |= 1 << i
        seq = (seq + 1) & 0xFFFF
        payload = f"HB pins=0b{mask:05b} seq={seq}\n".encode("utf-8")
        for port in outs:
            try:
                port.write(payload)
            except Exception:
                pass
        time.sleep(HEARTBEAT_S)


main()
