"""Built-in question type implementations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from baton_relay.config import ScoringConfig
from baton_relay.questions.base import Question, ScoreResult
from baton_relay.questions.registry import register, register_builder


def _norm_text(s: str, *, case_sensitive: bool, strip: bool) -> str:
    if strip:
        s = " ".join(s.split())
    if not case_sensitive:
        s = s.casefold()
    return s


@register("multiple_choice")
@dataclass
class MultipleChoice(Question):
    choices: list[str] | None = None
    answer: int = 0

    def score(self, answer: Any, scoring: ScoringConfig) -> ScoreResult:
        try:
            chosen = int(answer)
        except (TypeError, ValueError):
            return ScoreResult(0, self.points, False, "Invalid choice")
        ok = chosen == self.answer
        if ok:
            return ScoreResult(self.points, self.points, True, "Correct")
        penalty = max(0.0, scoring.wrong_answer_penalty)
        return ScoreResult(0.0 if penalty == 0 else -penalty, self.points, False, "Incorrect")


@register("select_all")
@dataclass
class SelectAll(Question):
    choices: list[str] | None = None
    answer: list[int] | None = None

    def score(self, answer: Any, scoring: ScoringConfig) -> ScoreResult:
        correct_set = set(self.answer or [])
        try:
            chosen = set(int(x) for x in answer)
        except (TypeError, ValueError):
            return ScoreResult(0, self.points, False, "Invalid selection")
        if chosen == correct_set:
            return ScoreResult(self.points, self.points, True, "Correct")
        if self.uses_partial(scoring) and correct_set:
            # Credit for true positives minus false positives, floored at 0
            tp = len(chosen & correct_set)
            fp = len(chosen - correct_set)
            fn = len(correct_set - chosen)
            ratio = max(0.0, (tp - fp) / len(correct_set))
            # Also penalize missing? using (tp / (tp+fp+fn)) alternative:
            ratio = tp / len(correct_set) if not fp else max(0.0, (tp - fp) / len(correct_set))
            pts = round(self.points * ratio, 2)
            return ScoreResult(pts, self.points, False, f"Partial ({tp}/{len(correct_set)})", True)
        return ScoreResult(0, self.points, False, "Incorrect")


@register("put_in_order")
@dataclass
class PutInOrder(Question):
    items: list[str] | None = None
    answer: list[int] | None = None

    def score(self, answer: Any, scoring: ScoringConfig) -> ScoreResult:
        expected = list(self.answer or [])
        try:
            got = [int(x) for x in answer]
        except (TypeError, ValueError):
            return ScoreResult(0, self.points, False, "Invalid order")
        if got == expected:
            return ScoreResult(self.points, self.points, True, "Correct")
        if self.uses_partial(scoring) and expected:
            matches = sum(1 for a, b in zip(got, expected) if a == b)
            # Also count items in correct relative positions
            pts = round(self.points * (matches / len(expected)), 2)
            return ScoreResult(pts, self.points, False, f"Partial ({matches}/{len(expected)})", True)
        return ScoreResult(0, self.points, False, "Incorrect")


@register("match_up")
@dataclass
class MatchUp(Question):
    left: list[str] | None = None
    right: list[str] | None = None
    answer: dict[str, int] | None = None

    def score(self, answer: Any, scoring: ScoringConfig) -> ScoreResult:
        expected = {str(k): int(v) for k, v in (self.answer or {}).items()}
        if not isinstance(answer, dict):
            return ScoreResult(0, self.points, False, "Invalid matching")
        got = {str(k): int(v) for k, v in answer.items()}
        if got == expected:
            return ScoreResult(self.points, self.points, True, "Correct")
        if self.uses_partial(scoring) and expected:
            matches = sum(1 for k, v in expected.items() if got.get(k) == v)
            pts = round(self.points * (matches / len(expected)), 2)
            return ScoreResult(pts, self.points, False, f"Partial ({matches}/{len(expected)})", True)
        return ScoreResult(0, self.points, False, "Incorrect")


@register("short_answer")
@dataclass
class ShortAnswer(Question):
    accepted: list[str] | None = None
    case_sensitive: bool = False
    strip_whitespace: bool = True

    def score(self, answer: Any, scoring: ScoringConfig) -> ScoreResult:
        text = "" if answer is None else str(answer)
        norm = _norm_text(text, case_sensitive=self.case_sensitive, strip=self.strip_whitespace)
        accepted = [
            _norm_text(a, case_sensitive=self.case_sensitive, strip=self.strip_whitespace)
            for a in (self.accepted or [])
        ]
        ok = norm in accepted
        return ScoreResult(
            self.points if ok else 0.0,
            self.points,
            ok,
            "Correct" if ok else "Incorrect",
        )


@register("numeric")
@dataclass
class Numeric(Question):
    answer: float = 0.0
    tolerance: float = 0.0

    def score(self, answer: Any, scoring: ScoringConfig) -> ScoreResult:
        try:
            val = float(answer)
        except (TypeError, ValueError):
            return ScoreResult(0, self.points, False, "Not a number")
        ok = abs(val - float(self.answer)) <= float(self.tolerance)
        return ScoreResult(
            self.points if ok else 0.0,
            self.points,
            ok,
            "Correct" if ok else "Incorrect",
        )


@register("fill_blank")
@dataclass
class FillBlank(Question):
    accepted: list[str] | None = None
    case_sensitive: bool = False
    strip_whitespace: bool = True

    def score(self, answer: Any, scoring: ScoringConfig) -> ScoreResult:
        # Same rules as short answer
        return ShortAnswer(
            id=self.id,
            type=self.type,
            prompt=self.prompt,
            points=self.points,
            partial_credit=self.partial_credit,
            accepted=self.accepted,
            case_sensitive=self.case_sensitive,
            strip_whitespace=self.strip_whitespace,
        ).score(answer, scoring)


@register("flag")
@dataclass
class Flag(Question):
    accepted: list[str] | None = None
    case_sensitive: bool = True
    strip_whitespace: bool = True

    def score(self, answer: Any, scoring: ScoringConfig) -> ScoreResult:
        return ShortAnswer(
            id=self.id,
            type=self.type,
            prompt=self.prompt,
            points=self.points,
            accepted=self.accepted,
            case_sensitive=self.case_sensitive,
            strip_whitespace=self.strip_whitespace,
        ).score(answer, scoring)


@register("hands_on")
@dataclass
class HandsOn(Question):
    image: str = ""
    ports: list[int] | None = None
    success: dict[str, Any] | None = None

    def score(self, answer: Any, scoring: ScoringConfig) -> ScoreResult:
        # Flag-style success works now; full container challenges are Linux-only later.
        success = self.success or {}
        if success.get("type") == "flag":
            return Flag(
                id=self.id,
                type="flag",
                prompt=self.prompt,
                points=self.points,
                accepted=list(success.get("accepted") or []),
                case_sensitive=True,
            ).score(answer, scoring)
        return ScoreResult(
            0,
            self.points,
            False,
            "Hands-on container challenges are not available yet.",
        )


def _common(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": data["id"],
        "type": data["type"],
        "prompt": data["prompt"],
        "points": float(data.get("points", 0)),
        "partial_credit": data.get("partial_credit"),
        "raw": data,
    }


def _build_multiple_choice(data: dict[str, Any]) -> Question:
    return MultipleChoice(
        **_common(data),
        choices=list(data["choices"]),
        answer=int(data["answer"]),
    )


def _build_select_all(data: dict[str, Any]) -> Question:
    return SelectAll(
        **_common(data),
        choices=list(data["choices"]),
        answer=[int(x) for x in data["answer"]],
    )


def _build_put_in_order(data: dict[str, Any]) -> Question:
    return PutInOrder(
        **_common(data),
        items=list(data["items"]),
        answer=[int(x) for x in data["answer"]],
    )


def _build_match_up(data: dict[str, Any]) -> Question:
    ans = data["answer"]
    if isinstance(ans, dict):
        answer = {str(k): int(v) for k, v in ans.items()}
    else:
        raise ValueError("match_up.answer must be an object mapping left index -> right index")
    return MatchUp(
        **_common(data),
        left=list(data["left"]),
        right=list(data["right"]),
        answer=answer,
    )


def _build_short(data: dict[str, Any]) -> Question:
    return ShortAnswer(
        **_common(data),
        accepted=[str(x) for x in data["accepted"]],
        case_sensitive=bool(data.get("case_sensitive", False)),
        strip_whitespace=bool(data.get("strip_whitespace", True)),
    )


def _build_numeric(data: dict[str, Any]) -> Question:
    return Numeric(
        **_common(data),
        answer=float(data["answer"]),
        tolerance=float(data.get("tolerance", 0)),
    )


def _build_fill(data: dict[str, Any]) -> Question:
    return FillBlank(
        **_common(data),
        accepted=[str(x) for x in data["accepted"]],
        case_sensitive=bool(data.get("case_sensitive", False)),
        strip_whitespace=bool(data.get("strip_whitespace", True)),
    )


def _build_flag(data: dict[str, Any]) -> Question:
    return Flag(
        **_common(data),
        accepted=[str(x) for x in data["accepted"]],
        case_sensitive=bool(data.get("case_sensitive", True)),
        strip_whitespace=bool(data.get("strip_whitespace", True)),
    )


def _build_hands_on(data: dict[str, Any]) -> Question:
    return HandsOn(
        **_common(data),
        image=str(data.get("image", "")),
        ports=[int(x) for x in data.get("ports", [])],
        success=dict(data.get("success") or {}),
    )


register_builder("multiple_choice", _build_multiple_choice)
register_builder("select_all", _build_select_all)
register_builder("put_in_order", _build_put_in_order)
register_builder("match_up", _build_match_up)
register_builder("short_answer", _build_short)
register_builder("numeric", _build_numeric)
register_builder("fill_blank", _build_fill)
register_builder("flag", _build_flag)
register_builder("hands_on", _build_hands_on)
