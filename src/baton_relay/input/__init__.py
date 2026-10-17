"""Input sources package."""

from baton_relay.input.base import BatonReading, BatonSource, ReadingKind
from baton_relay.input.fake import FakeBatonSource
from baton_relay.input.serial_source import SerialBatonSource, parse_heartbeat

__all__ = [
    "BatonReading",
    "BatonSource",
    "ReadingKind",
    "FakeBatonSource",
    "SerialBatonSource",
    "parse_heartbeat",
]
