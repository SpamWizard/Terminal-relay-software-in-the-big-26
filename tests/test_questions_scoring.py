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
