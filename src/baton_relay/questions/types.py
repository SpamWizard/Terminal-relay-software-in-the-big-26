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


def _score_accepted(
    *,
    answer: Any,
    accepted: list[str] | None,
    points: float,
    case_sensitive: bool,
    strip_whitespace: bool,
) -> ScoreResult:
    text = "" if answer is None else str(answer)
    norm = _norm_text(text, case_sensitive=case_sensitive, strip=strip_whitespace)
    ok_list = [
        _norm_text(a, case_sensitive=case_sensitive, strip=strip_whitespace)
        for a in (accepted or [])
    ]
    ok = norm in ok_list
    return ScoreResult(
        points if ok else 0.0,
        points,
        ok,
        "Correct" if ok else "Incorrect",
    )


@register("multiple_choice")
@dataclass
class MultipleChoice(Question):
    choices: list[str] | None = None
    answer: int = 0
    # Taken off the award for each distinct wrong guess. 0 leaves the step to miss_floor.
    miss_cost: float = 0.0
    # Lowest award after every wrong letter has been tried. 0 means the award can hit zero.
    miss_floor: float = 0.0

    def shrinks_when_wrong(self) -> bool:
        return self.miss_cost > 0 or (0 < self.miss_floor < self.points)

    def value_after_misses(self, misses: int) -> float:
        """Points still on offer after this many wrong guesses."""
        if misses <= 0 or not self.shrinks_when_wrong():
            return self.points
        if self.miss_cost > 0:
            return max(self.miss_floor, round(self.points - self.miss_cost * misses, 4))
        # Spread (points - floor) across the wrong letters. Integer awards shed
        # the remainder on the last steps, so 10 with a floor of 1 and four
        # wrong letters goes 10, 8, 6, 4, 1.
        slots = max(1, len(self.choices or []) - 1)
        taken = min(misses, slots)
        span = self.points - self.miss_floor
        if (
            float(span).is_integer()
            and float(self.points).is_integer()
            and float(self.miss_floor).is_integer()
        ):
            span_i = int(span)
            base, extra = divmod(span_i, slots)
            dropped = 0
            for step in range(taken):
                dropped += base + (1 if step >= slots - extra else 0)
            return float(int(self.points) - dropped)
        return max(self.miss_floor, round(self.points - span * taken / slots, 4))

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


@register("desk")
@dataclass
class Desk(Question):
    """Desk challenge: work in a WSL copy of public_dir and submit a flag."""

    accepted: list[str] | None = None
    case_sensitive: bool = True
    strip_whitespace: bool = True
    public_dir: str = ""
    panes: list[str] | None = None
    page_file: str | None = None

    def score(self, answer: Any, scoring: ScoringConfig) -> ScoreResult:
        return _score_accepted(
            answer=answer,
            accepted=self.accepted,
            points=self.points,
            case_sensitive=self.case_sensitive,
            strip_whitespace=self.strip_whitespace,
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


def _nonneg(data: dict[str, Any], key: str) -> float:
    if key not in data or data[key] is None:
        return 0.0
    value = data[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{key} must be a number")
    if value < 0:
        raise ValueError(f"{key} must be zero or more")
    return float(value)


def _build_multiple_choice(data: dict[str, Any]) -> Question:
    return MultipleChoice(
        **_common(data),
        choices=list(data["choices"]),
        answer=int(data["answer"]),
        miss_cost=_nonneg(data, "miss_cost"),
        miss_floor=_nonneg(data, "miss_floor"),
    )


def _build_desk(data: dict[str, Any]) -> Question:
    panes_raw = data.get("panes") or ["files", "terminal"]
    if not isinstance(panes_raw, list) or not panes_raw:
        raise ValueError("desk.panes must be a non-empty list")
    panes = [str(p) for p in panes_raw]
    allowed = {"files", "terminal", "page"}
    bad = [p for p in panes if p not in allowed]
    if bad:
        raise ValueError(f"desk.panes unknown: {', '.join(bad)} (allowed: files, terminal, page)")
    public = str(data.get("public_dir") or "")
    if not public:
        raise ValueError("desk.public_dir is required (set by the challenge folder loader)")
    page_file = data.get("page_file")
    return Desk(
        **_common(data),
        accepted=[str(x) for x in data.get("accepted") or []],
        case_sensitive=bool(data.get("case_sensitive", True)),
        strip_whitespace=bool(data.get("strip_whitespace", True)),
        public_dir=public,
        panes=panes,
        page_file=str(page_file) if page_file else None,
    )


register_builder("multiple_choice", _build_multiple_choice)
register_builder("desk", _build_desk)
