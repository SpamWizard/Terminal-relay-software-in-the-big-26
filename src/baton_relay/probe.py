"""Plain-terminal baton probe. Prints which pins are tied to GND."""

from __future__ import annotations

import time
from dataclasses import replace
from pathlib import Path

from baton_relay.config import AppConfig, load_config
from baton_relay.input.base import ReadingKind
from baton_relay.input.decode import decode_pins, pins_from_mask
from baton_relay.input.serial_source import parse_heartbeat, resolve_port


def describe_mask(mask: int, config: AppConfig) -> str:
    """One line: each pin ON/-- and the seat that pair maps to."""
    pins = pins_from_mask(mask & 0x1F)
    reading = decode_pins(pins, config)
    cells = "  ".join(f"{n}:{'ON' if n in pins else '--'}" for n in range(1, 6))
    if reading.kind is ReadingKind.EMPTY:
        who = "nothing plugged in"
    elif reading.kind is ReadingKind.PERSON and reading.person_index is not None:
        person = config.people[reading.person_index]
        who = f"#{reading.person_index + 1} {person.label}"
    else:
        shown = "+".join(str(p) for p in pins) if pins else "?"
        who = f"unknown ({shown})"
    return f"{cells}   {who}"


def _seat_lines(config: AppConfig) -> list[str]:
    lines = ["seats:"]
    for i, person in enumerate(config.people):
        a, b = person.baton_pins
        lines.append(f"  #{i + 1} {person.label}  pins {a}+{b}")
    return lines


# Opening the COM port reboots CircuitPython. Boot plus code.py is often
# longer than the in-game heartbeat timeout, so the first wait is separate.
_BOOT_WAIT_S = 8.0


def split_serial_lines(buf: bytearray) -> tuple[list[int], list[str]]:
    """Pull complete lines out of buf. Heartbeats become masks; other text is kept."""
    masks: list[int] = []
    others: list[str] = []
    while True:
        nl = buf.find(b"\n")
        if nl < 0:
            if len(buf) > 4096:
                del buf[:-512]
            break
        raw = bytes(buf[:nl])
        del buf[: nl + 1]
        if raw.endswith(b"\r"):
            raw = raw[:-1]
        text = raw.decode("utf-8", errors="ignore").strip()
        if not text:
            continue
        parsed = parse_heartbeat(text)
        if parsed is None:
            others.append(text)
        else:
            masks.append(parsed[0])
    return masks, others


def _print_ports(preferred: str) -> str | None:
    chosen = resolve_port(preferred)
    try:
        from serial.tools import list_ports

        infos = list(list_ports.comports())
    except Exception as exc:
        print(f"could not list serial ports: {exc}", flush=True)
        return chosen

    if not infos:
        print("no serial ports found", flush=True)
    else:
        print("serial ports:", flush=True)
        for info in infos:
            mark = "  <-- using" if info.device == chosen else ""
            desc = info.description or ""
            print(f"  {info.device}  {desc}{mark}", flush=True)
    if preferred.strip().lower() == "auto" and chosen is None:
        print("auto did not find a CircuitPython / Pico port", flush=True)
    elif chosen is not None and infos and all(info.device != chosen for info in infos):
        print(f"configured port {chosen} is not plugged in", flush=True)
    return chosen


def _open_port(path: str, baud: int, *, reboot: bool):
    import serial

    # dtr=True reboots CircuitPython. Set it before open(); passing it to
    # Serial() is rejected by pyserial.
    ser = serial.Serial()
    ser.port = path
    ser.baudrate = baud
    ser.timeout = 0.2
    ser.dtr = reboot
    ser.rts = False
    ser.open()
    return ser


def _listen_once(
    path: str,
    config: AppConfig,
    *,
    reboot: bool,
    give_up_s: float,
) -> str:
    """Read until heartbeats stop, the port drops, or the board stays silent.

    Returns ``silent``, ``talking``, ``stopped``, ``lost``, or ``closed``.
    """
    try:
        ser = _open_port(path, config.serial.baud, reboot=reboot)
    except Exception as exc:
        print(f"could not open {path}: {exc}", flush=True)
        return "closed"

    if reboot:
        print(f"rebooted {path} — waiting for code.py to start", flush=True)
    else:
        print(f"listening on {path}", flush=True)

    buf = bytearray()
    opened_at = time.monotonic()
    last_hb: float | None = None
    last_mask: int | None = None
    saw_text = False
    timeout_s = max(0.2, config.serial.heartbeat_timeout_ms / 1000.0)
    try:
        while True:
            try:
                chunk = ser.read(ser.in_waiting or 1)
            except Exception as exc:
                print(f"read failed: {exc}", flush=True)
                return "lost"
            now = time.monotonic()
            if chunk:
                buf.extend(chunk)
                masks, others = split_serial_lines(buf)
                for text in others:
                    saw_text = True
                    print(f"board: {text}", flush=True)
                for mask in masks:
                    last_hb = now
                    if mask == last_mask:
                        continue
                    last_mask = mask
                    print(describe_mask(mask, config), flush=True)
            if last_hb is not None:
                if (now - last_hb) > timeout_s:
                    print("heartbeat stopped", flush=True)
                    return "stopped"
                continue
            if (now - opened_at) <= give_up_s:
                continue
            if buf:
                saw_text = True
                print(f"board: {bytes(buf[:300])!r}", flush=True)
                buf.clear()
            if saw_text:
                print(
                    "The board is sending text, but no HB line. "
                    "A traceback above means code.py on CIRCUITPY did not start.",
                    flush=True,
                )
                return "talking"
            return "silent"
    finally:
        try:
            ser.close()
        except Exception:
            pass


def run_probe(config_path: Path, *, port: str | None = None) -> int:
    """Watch the RP2040 and print a line whenever the pin mask changes."""
    config = load_config(config_path)
    if port:
        config = config.with_updates(serial=replace(config.serial, port=port.strip()))

    for line in _seat_lines(config):
        print(line, flush=True)
    print(flush=True)
    _print_ports(config.serial.port)
    print("Ctrl+C to stop", flush=True)

    try:
        while True:
            path = resolve_port(config.serial.port)
            if path is None:
                print("waiting for a board…", flush=True)
                time.sleep(1.0)
                continue
            reason = _listen_once(path, config, reboot=False, give_up_s=2.0)
            if reason == "silent":
                print("No data yet. Rebooting the board once so code.py can start.", flush=True)
                reason = _listen_once(path, config, reboot=True, give_up_s=_BOOT_WAIT_S)
            if reason == "silent":
                print(
                    f"No heartbeat on {path}. Nothing arrived. "
                    "Copy firmware/boot.py and firmware/code.py onto the CIRCUITPY drive, "
                    "let the board reboot, and run this again.",
                    flush=True,
                )
                time.sleep(2.0)
            else:
                time.sleep(0.5)
    except KeyboardInterrupt:
        print(flush=True)
        return 0


