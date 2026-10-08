"""Decode 5-pin baton readings into person indices."""

from __future__ import annotations

from baton_relay.config import AppConfig, VALID_BATON_PAIRS
from baton_relay.input.base import BatonReading, ReadingKind


def pins_from_mask(mask: int) -> tuple[int, ...]:
    """Convert a serial heartbeat bitmask to pin numbers (bit0 = pin 1)."""
    pins = []
    for i in range(5):
        if mask & (1 << i):
            pins.append(i + 1)
    return tuple(pins)


def decode_pins(pins: tuple[int, ...] | list[int], config: AppConfig) -> BatonReading:
    cleaned = tuple(sorted({int(p) for p in pins if 1 <= int(p) <= 5}))
    if not cleaned:
        return BatonReading(kind=ReadingKind.EMPTY, pins=(), source="baton")
    if len(cleaned) != 2 or cleaned not in VALID_BATON_PAIRS:
        return BatonReading(kind=ReadingKind.UNKNOWN, pins=cleaned, source="baton")
    person = config.person_for_pins((cleaned[0], cleaned[1]))
    if person is None:
        return BatonReading(kind=ReadingKind.UNKNOWN, pins=cleaned, source="baton")
    idx = config.person_index(person.id)
    return BatonReading(
        kind=ReadingKind.PERSON,
        person_index=idx,
        pins=cleaned,
        source="baton",
    )
