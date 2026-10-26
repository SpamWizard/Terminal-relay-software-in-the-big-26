"""Human-readable answers for logs and the score sheet."""

from __future__ import annotations

from typing import Any

from baton_relay.questions.base import Question
from baton_relay.questions.types import (
    Desk,
    FillBlank,
    Flag,
    HandsOn,
    MatchUp,
    MultipleChoice,
    Numeric,
    PutInOrder,
    SelectAll,
    ShortAnswer,
)


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
    if isinstance(question, SelectAll):
        indexes = sorted(int(i) for i in answer)
        if not indexes:
            return "(none)"
        return ", ".join(_choice(question.choices, i) for i in indexes)
    if isinstance(question, PutInOrder):
        items = question.items or []
        labels = []
        for raw in answer:
            i = int(raw)
            labels.append(items[i] if 0 <= i < len(items) else str(i))
        return " → ".join(labels)
    if isinstance(question, MatchUp):
        if not isinstance(answer, dict):
            return str(answer)
        left = question.left or []
        right = question.right or []
        parts: list[str] = []
        for key in sorted(answer, key=lambda k: int(k)):
            li = int(key)
            ri = int(answer[key])
            ltxt = left[li] if 0 <= li < len(left) else str(key)
            rtxt = right[ri] if 0 <= ri < len(right) else str(ri)
            parts.append(f"{ltxt} → {rtxt}")
        return "; ".join(parts)
    if isinstance(question, Numeric):
        return str(answer)
    if answer is None:
        return ""
    return str(answer)


def _format_expected(question: Question) -> str:
    if isinstance(question, MultipleChoice):
        return _format_submitted(question, question.answer)
    if isinstance(question, SelectAll):
        return _format_submitted(question, question.answer or [])
    if isinstance(question, PutInOrder):
        return _format_submitted(question, question.answer or [])
    if isinstance(question, MatchUp):
        return _format_submitted(question, question.answer or {})
    if isinstance(question, Numeric):
        if question.tolerance:
            return f"{question.answer:g} ± {question.tolerance:g}"
        return f"{question.answer:g}"
    if isinstance(question, (ShortAnswer, FillBlank, Flag, Desk)):
        return " | ".join(question.accepted or [])
    if isinstance(question, HandsOn):
        success = question.success or {}
        accepted = success.get("accepted") or []
        return " | ".join(str(item) for item in accepted)
    return ""
