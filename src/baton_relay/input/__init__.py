"""Input sources package."""

from baton_relay.input.base import BatonReading, BatonSource, ReadingKind
from baton_relay.input.fake import FakeBatonSource

__all__ = ["BatonReading", "BatonSource", "ReadingKind", "FakeBatonSource"]
