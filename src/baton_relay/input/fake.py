"""Keyboard-simulated baton source for development and Windows testing."""

from __future__ import annotations

from baton_relay.config import AppConfig
from baton_relay.input.base import BatonReading, BatonSource, ReadingCallback, ReadingKind


class FakeBatonSource(BatonSource):
    """
    Keys (when forwarded from the UI):
      1-6  → insert that person's baton (seat index 0-5)
      0/U  → unknown reading
      P / Backspace / Space → pull out (empty)
    """

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self._callback: ReadingCallback | None = None
        self._last: BatonReading = BatonReading(kind=ReadingKind.EMPTY, source="fake")

    def start(self, on_reading: ReadingCallback) -> None:
        self._callback = on_reading

    def stop(self) -> None:
        self._callback = None

    @property
    def status_label(self) -> str:
        return "FAKE"

    def handle_key(self, key: str) -> None:
        if not self._callback:
            return
        k = key.upper()
        reading: BatonReading | None = None
        if k in ("P", "BACKSPACE", " "):
            reading = BatonReading(kind=ReadingKind.EMPTY, source="fake")
        elif k in ("0", "U"):
            reading = BatonReading(kind=ReadingKind.UNKNOWN, pins=(1,), source="fake")
        elif k in "123456":
            idx = int(k) - 1
            if idx < self.config.team_size:
                pins = self.config.people[idx].baton_pins
                reading = BatonReading(
                    kind=ReadingKind.PERSON,
                    person_index=idx,
                    pins=pins,
                    source="fake",
                )
            else:
                reading = BatonReading(kind=ReadingKind.UNKNOWN, source="fake")
        if reading is None:
            return
        self._last = reading
        self._callback(reading)
