"""Human-readable answers for logs and the score sheet."""

from __future__ import annotations

from typing import Any

from baton_relay.questions.base import Question
from baton_relay.questions.types import Desk, MultipleChoice


def _letter(index: int) -> str:
    if 0 <= index < 26:
        return chr(65 + index)
    return str(index + 1)


def _choice(choices: list[str] | None, index: int) -> str:
    items = choices or []
    if 0 <= index < len(items):
        return f"{_letter(index)}. {items[index]}"
    return str(index)


def format_submitted(question: Question, answer: Any) -> str:
    """What the player submitted, in the same words they saw on screen."""
    try:
        return _format_submitted(question, answer)
    except (TypeError, ValueError, IndexError):
        return "" if answer is None else str(answer)


def format_expected(question: Question) -> str:
    """The answer key, so a logged question can be re-scored later."""
    try:
        return _format_expected(question)
    except (TypeError, ValueError, IndexError):
        return ""


def _format_submitted(question: Question, answer: Any) -> str:
    if isinstance(question, MultipleChoice):
        return _choice(question.choices, int(answer))
    if answer is None:
        return ""
    return str(answer)


def _format_expected(question: Question) -> str:
    if isinstance(question, MultipleChoice):
        return _format_submitted(question, question.answer)
    if isinstance(question, Desk):
        return " | ".join(question.accepted or [])
    return ""
