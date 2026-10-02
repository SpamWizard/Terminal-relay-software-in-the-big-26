"""Baton / identity input sources."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum, auto
from typing import Callable


class ReadingKind(Enum):
    EMPTY = auto()
    UNKNOWN = auto()
    PERSON = auto()


@dataclass(frozen=True)
class BatonReading:
    kind: ReadingKind
    person_index: int | None = None
    pins: tuple[int, ...] = ()
    source: str = "baton"


ReadingCallback = Callable[[BatonReading], None]


class BatonSource(ABC):
    """Pluggable identity sensor: fake keys, RP2040 serial, or controller override."""

    @abstractmethod
    def start(self, on_reading: ReadingCallback) -> None:
        ...

    @abstractmethod
    def stop(self) -> None:
        ...

    @property
    @abstractmethod
    def status_label(self) -> str:
        ...
