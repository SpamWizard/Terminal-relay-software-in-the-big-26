"""Scoring + loader checks for kept question types (multiple_choice + desk)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from baton_relay.config import ScoringConfig
from baton_relay.questions.loader import QuestionLoadError, load_question_file
from baton_relay.questions.registry import ensure_builtin_types_loaded
from baton_relay.questions.types import Desk, MultipleChoice


@pytest.fixture(autouse=True)
def _types():
    ensure_builtin_types_loaded()


SCORING = ScoringConfig(partial_credit=True, wrong_answer_penalty=0, redo_multiplier=0.5)
SCORING_PENALTY = ScoringConfig(partial_credit=True, wrong_answer_penalty=2, redo_multiplier=0.5)


def test_fake_logos_warn_that_misses_cost():
    root = Path(__file__).resolve().parents[1]
    logos = load_question_file(root / "questions" / "fake_logos.json")
    assert logos.questions
    for question in logos.questions:
        assert isinstance(question, MultipleChoice)
        assert "Points go down each time you guess wrong." in question.prompt
        assert question.points == 10
        assert question.miss_floor == 1
        assert [question.value_after_misses(n) for n in range(5)] == [10, 8, 6, 4, 1]


def test_question_miss_cost_overrides_the_set(tmp_path: Path):
    path = tmp_path / "set.json"
    path.write_text(
        json.dumps(
            {
                "set_id": "pics",
                "title": "Pics",
                "miss_cost": 0.25,
                "questions": [
                    {
                        "id": "q",
                        "type": "multiple_choice",
                        "prompt": "p",
                        "points": 1,
                        "choices": ["A", "B"],
                        "answer": 1,
                        "miss_cost": 0.5,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    question = load_question_file(path).questions[0]
    assert isinstance(question, MultipleChoice)
    assert question.miss_cost == pytest.approx(0.5)


def test_negative_miss_cost_rejected(tmp_path: Path):
    path = tmp_path / "set.json"
    path.write_text(
        json.dumps(
            {
                "set_id": "pics",
                "title": "Pics",
                "miss_cost": -1,
                "questions": [
                    {
                        "id": "q",
                        "type": "multiple_choice",
                        "prompt": "p",
                        "points": 1,
                        "choices": ["A", "B"],
                        "answer": 1,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(QuestionLoadError, match="miss_cost"):
        load_question_file(path)


def test_mc_penalty():
    q = MultipleChoice(id="a", type="multiple_choice", prompt="p", points=10, choices=["a", "b"], answer=1)
    bad = q.score(0, SCORING_PENALTY)
    assert not bad.correct
    assert bad.points == -2


def test_mc_invalid():
    q = MultipleChoice(id="a", type="multiple_choice", prompt="p", points=10, choices=["a", "b"], answer=1)
    assert not q.score("x", SCORING).correct


def test_desk_flag():
    q = Desk(
        id="d",
        type="desk",
        prompt="p",
        points=50,
        accepted=["TR{ok}"],
        public_dir="/tmp",
        panes=["files", "terminal"],
    )
    assert q.score("TR{ok}", SCORING).correct
    assert not q.score("TR{no}", SCORING).correct


def test_unknown_type_rejected(tmp_path: Path):
    path = tmp_path / "bad.json"
    path.write_text(
        json.dumps(
            {
                "set_id": "x",
                "title": "X",
                "questions": [{"id": "1", "type": "select_all", "prompt": "p", "points": 1, "choices": ["a"], "answer": [0]}],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(QuestionLoadError):
        load_question_file(path)
