"""Question type base classes and scoring result."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from baton_relay.config import ScoringConfig


@dataclass(frozen=True)
class ScoreResult:
    points: float
    max_points: float
    correct: bool
    feedback: str = ""
    partial: bool = False


@dataclass
class Question(ABC):
    id: str
    type: str
    prompt: str
    points: float
    partial_credit: bool | None = None
    raw: dict[str, Any] | None = None

    @abstractmethod
    def score(self, answer: Any, scoring: ScoringConfig) -> ScoreResult:
        ...

    def uses_partial(self, scoring: ScoringConfig) -> bool:
        if self.partial_credit is not None:
            return self.partial_credit
        return scoring.partial_credit


@dataclass
class QuestionSet:
    set_id: str
    title: str
    questions: list[Question]
    source_path: str = ""
