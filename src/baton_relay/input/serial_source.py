"""RP2040 USB CDC baton reader (CircuitPython heartbeat lines)."""

from __future__ import annotations

import re
import time
from typing import Callable

from PySide6.QtCore import QObject, QTimer

from baton_relay.config import AppConfig
from baton_relay.input.base import BatonReading, BatonSource, ReadingCallback
from baton_relay.input.decode import decode_pins, pins_from_mask

# HB pins=0b10101 seq=123
_HB_RE = re.compile(
    r"^HB\s+pins=(?:0b(?P<bin>[01]+)|0x(?P<hex>[0-9a-fA-F]+)|(?P<dec>\d+))"
    r"(?:\s+seq=(?P<seq>-?\d+))?\s*$",
    re.IGNORECASE,
)

# Bootloader uses Raspberry Pi's VID. Running CircuitPython uses Adafruit's.
_BOARD_VIDS = (0x2E8A, 0x239A)
_HINTS = (
    "circuitpython",
    "pico",
    "rp2040",
    "adafruit",
    "usb serial device",
    "usb serial",
)

LinkCallback = Callable[[], None]


def parse_heartbeat(line: str) -> tuple[int, int | None] | None:
    """Parse one heartbeat line → (pin_mask, seq_or_None)."""
    text = line.strip()
    if not text:
        return None
    m = _HB_RE.match(text)
    if not m:
        return None
    if m.group("bin") is not None:
        mask = int(m.group("bin"), 2) & 0x1F
    elif m.group("hex") is not None:
        mask = int(m.group("hex"), 16) & 0x1F
    else:
        mask = int(m.group("dec"), 10) & 0x1F
    seq_raw = m.group("seq")
    seq = int(seq_raw) if seq_raw is not None else None
    return mask, seq


def list_candidate_ports() -> list[str]:
    """Ranked COM/tty devices likely to be the baton board."""
    try:
        from serial.tools import list_ports
    except Exception:
        return []

    scored: list[tuple[int, str]] = []
    for info in list_ports.comports():
        score = 0
        desc = (info.description or "").lower()
        mfg = (info.manufacturer or "").lower()
        product = (getattr(info, "product", None) or "").lower()
        hwid = (info.hwid or "").lower()
        blob = f"{desc} {mfg} {product} {hwid}"
        if info.vid in _BOARD_VIDS:
            score += 100
        for hint in _HINTS:
            if hint in blob:
                score += 10
        # Prefer the CircuitPython *data* CDC over the REPL console.
        if "circuitpython" in blob and "data" in blob:
            score += 40
        if score > 0:
            scored.append((score, info.device))
    scored.sort(key=lambda t: (-t[0], t[1]))
    return [dev for _, dev in scored]


def resolve_port(preferred: str) -> str | None:
    """Resolve config port (`auto` or explicit) to a device path."""
    preferred = (preferred or "auto").strip()
    if preferred.lower() != "auto":
        return preferred
    candidates = list_candidate_ports()
    return candidates[0] if candidates else None


class SerialBatonSource(BatonSource):
    """
    Poll USB CDC for `HB pins=0b…. seq=…` lines.

    Stable pin masks (after debounce) decode to PERSON / EMPTY / UNKNOWN.
    Missing heartbeats past `heartbeat_timeout_ms` fire disconnect callbacks.
    """

    def __init__(self, config: AppConfig, parent: QObject | None = None) -> None:
        self.config = config
        self._callback: ReadingCallback | None = None
        self._on_disconnected: LinkCallback | None = None
        self._on_reconnected: LinkCallback | None = None
        self._ser = None
        self._buf = bytearray()
        self._port_path: str | None = None
        self._status = "waiting"
        self._linked = False
        self._last_hb_mono = 0.0
        self._stable_mask: int | None = None
        self._pending_mask: int | None = None
        self._pending_since = 0.0
        self._last_reading: BatonReading | None = None
        self._retry_at = 0.0
        self._timer = QTimer(parent)
        self._timer.setInterval(40)
        self._timer.timeout.connect(self._tick)

    @property
    def status_label(self) -> str:
        return self._status

    def start(
        self,
        on_reading: ReadingCallback,
        *,
        on_disconnected: LinkCallback | None = None,
        on_reconnected: LinkCallback | None = None,
    ) -> None:
        self._callback = on_reading
        self._on_disconnected = on_disconnected
        self._on_reconnected = on_reconnected
        self._set_status("waiting")
        if not self._timer.isActive():
            self._timer.start()
        self._open_if_needed(force=True)

    def stop(self) -> None:
        self._timer.stop()
        self._close(mark_disconnected=False)
        self._callback = None
        self._on_disconnected = None
        self._on_reconnected = None
        self._set_status("off")

    def apply_config(self, config: AppConfig) -> None:
        """Hot-apply serial / debounce / person pin map without restarting the UI."""
        old_port = self.config.serial.port
        old_baud = self.config.serial.baud
        self.config = config
        if (
            config.serial.port != old_port
            or config.serial.baud != old_baud
            or self._ser is None
        ):
            self._close(mark_disconnected=True)
            self._retry_at = 0.0
            self._open_if_needed(force=True)

    def _set_status(self, text: str) -> None:
        self._status = text

    def _open_if_needed(self, *, force: bool = False) -> None:
        if self._ser is not None:
            return
        now = time.monotonic()
        if not force and now < self._retry_at:
            return
        self._retry_at = now + 1.0
        path = resolve_port(self.config.serial.port)
        if path is None:
            self._set_status("no device")
            return
        try:
            import serial

            self._ser = serial.Serial(
                port=path,
                baudrate=self.config.serial.baud,
                timeout=0,
                write_timeout=0,
            )
            self._port_path = path
            self._buf.clear()
            self._last_hb_mono = time.monotonic()
            self._set_status(path)
            # Link is confirmed on the first valid heartbeat, not merely open.
        except Exception:
            self._ser = None
            self._port_path = None
            self._set_status("open failed")
            self._retry_at = now + 1.5

    def _close(self, *, mark_disconnected: bool) -> None:
        if self._ser is not None:
            try:
                self._ser.close()
            except Exception:
                pass
        self._ser = None
        self._port_path = None
        self._buf.clear()
        self._stable_mask = None
        self._pending_mask = None
        self._last_reading = None
        if mark_disconnected and self._linked:
            self._linked = False
            if self._on_disconnected:
                self._on_disconnected()
            self._set_status("disconnected")

    def _tick(self) -> None:
        if self._ser is None:
            self._open_if_needed()
            return

        try:
            waiting = self._ser.in_waiting
            if waiting:
                chunk = self._ser.read(waiting)
                if chunk:
                    self._buf.extend(chunk)
                    self._drain_lines()
        except Exception:
            self._close(mark_disconnected=True)
            self._retry_at = 0.0
            return

        timeout_ms = self.config.serial.heartbeat_timeout_ms
        if self._linked and timeout_ms > 0:
            age_ms = (time.monotonic() - self._last_hb_mono) * 1000.0
            if age_ms > timeout_ms:
                self._close(mark_disconnected=True)
                self._retry_at = 0.0
                return

        self._flush_debounce()

    def _drain_lines(self) -> None:
        while True:
            nl = self._buf.find(b"\n")
            if nl < 0:
                # Bound garbage if the board never sends newlines
                if len(self._buf) > 4096:
                    del self._buf[:-512]
                break
            raw = self._buf[:nl]
            del self._buf[: nl + 1]
            if raw.endswith(b"\r"):
                raw = raw[:-1]
            try:
                line = raw.decode("utf-8", errors="ignore")
            except Exception:
                continue
            parsed = parse_heartbeat(line)
            if parsed is None:
                continue
            mask, _seq = parsed
            self._on_heartbeat(mask)

    def _on_heartbeat(self, mask: int) -> None:
        now = time.monotonic()
        self._last_hb_mono = now
        if not self._linked:
            self._linked = True
            label = self._port_path or "connected"
            self._set_status(label)
            if self._on_reconnected:
                self._on_reconnected()
        if self._pending_mask != mask:
            self._pending_mask = mask
            self._pending_since = now
        self._flush_debounce()

    def _flush_debounce(self) -> None:
        if self._pending_mask is None or not self._linked:
            return
        debounce_s = max(0, self.config.timers.debounce_ms) / 1000.0
        if time.monotonic() - self._pending_since < debounce_s:
            return
        mask = self._pending_mask
        if mask == self._stable_mask:
            return
        self._stable_mask = mask
        pins = pins_from_mask(mask)
        reading = decode_pins(pins, self.config)
        # Keep source tag as baton so disconnect rules treat this as hardware.
        reading = BatonReading(
            kind=reading.kind,
            person_index=reading.person_index,
            pins=reading.pins,
            source="baton",
        )
        if (
            self._last_reading is not None
            and self._last_reading.kind == reading.kind
            and self._last_reading.person_index == reading.person_index
            and self._last_reading.pins == reading.pins
        ):
            return
        self._last_reading = reading
        if self._callback:
            self._callback(reading)
