"""Exhaustive scoring + loader rejection for every built-in question type."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from baton_relay.config import ScoringConfig
from baton_relay.questions.loader import QuestionLoadError, load_all_question_files, load_question_file
from baton_relay.questions.registry import ensure_builtin_types_loaded
from baton_relay.questions.types import (
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


@pytest.fixture(autouse=True)
def _types():
    ensure_builtin_types_loaded()


SCORING = ScoringConfig(partial_credit=True, wrong_answer_penalty=0, redo_multiplier=0.5)
SCORING_PENALTY = ScoringConfig(partial_credit=True, wrong_answer_penalty=2, redo_multiplier=0.5)
SCORING_NO_PARTIAL = ScoringConfig(partial_credit=False, wrong_answer_penalty=0, redo_multiplier=0.5)


def test_mc_penalty():
    q = MultipleChoice(id="a", type="multiple_choice", prompt="p", points=10, choices=["a", "b"], answer=1)
    bad = q.score(0, SCORING_PENALTY)
    assert not bad.correct
    assert bad.points == -2


def test_mc_invalid():
    q = MultipleChoice(id="a", type="multiple_choice", prompt="p", points=10, choices=["a", "b"], answer=1)
    assert not q.score("x", SCORING).correct


def test_put_in_order_full_and_partial():
    q = PutInOrder(
        id="o", type="put_in_order", prompt="p", points=10, items=["a", "b", "c"], answer=[2, 0, 1]
    )
    assert q.score([2, 0, 1], SCORING).correct
    partial = q.score([2, 1, 0], SCORING)
    assert partial.partial
    assert partial.points == pytest.approx(3.33)
    assert q.score([0, 1, 2], SCORING_NO_PARTIAL).points == 0


def test_match_up_full_and_partial():
    q = MatchUp(
        id="m",
        type="match_up",
        prompt="p",
        points=9,
        left=["a", "b", "c"],
        right=["A", "B", "C"],
        answer={"0": 0, "1": 1, "2": 2},
    )
    assert q.score({"0": 0, "1": 1, "2": 2}, SCORING).correct
    partial = q.score({"0": 0, "1": 0, "2": 2}, SCORING)
    assert partial.partial
    assert partial.points == 6.0
    assert not q.score("nope", SCORING).correct


def test_numeric_tolerance():
    q = Numeric(id="n", type="numeric", prompt="p", points=5, answer=10.0, tolerance=0.5)
    assert q.score(10.4, SCORING).correct
    assert not q.score(10.6, SCORING).correct
    assert not q.score("x", SCORING).correct


def test_fill_blank_and_flag():
    blank = FillBlank(
        id="b", type="fill_blank", prompt="p", points=3, accepted=["Blue"], case_sensitive=False
    )
    assert blank.score(" blue ", SCORING).correct
    flag = Flag(id="f", type="flag", prompt="p", points=3, accepted=["FLAG{x}"])
    assert flag.score("FLAG{x}", SCORING).correct
    assert not flag.score("flag{x}", SCORING).correct


def test_hands_on_flag_and_stub():
    ok = HandsOn(
        id="h",
        type="hands_on",
        prompt="p",
        points=7,
        image="img",
        success={"type": "flag", "accepted": ["FLAG{ok}"]},
    )
    assert ok.score("FLAG{ok}", SCORING).correct
    stub = HandsOn(id="h2", type="hands_on", prompt="p", points=7, success={"type": "container"})
    r = stub.score("x", SCORING)
    assert not r.correct
    assert "not available" in r.feedback.lower()


def test_select_all_invalid():
    q = SelectAll(
        id="s", type="select_all", prompt="p", points=10, choices=["a", "b"], answer=[0], partial_credit=True
    )
    assert not q.score("bad", SCORING).correct


def test_short_case_sensitive():
    q = ShortAnswer(
        id="s",
        type="short_answer",
        prompt="p",
        points=1,
        accepted=["AbC"],
        case_sensitive=True,
        strip_whitespace=False,
    )
    assert q.score("AbC", SCORING).correct
    assert not q.score("abc", SCORING).correct


@pytest.mark.parametrize(
    "payload,match",
    [
        ("not json", "JSON parse"),
        ("[]", "object"),
        ("{}", "set_id"),
        ('{"set_id":"x","title":"t","questions":[]}', "non-empty"),
        (
            '{"set_id":"x","title":"t","questions":[{"id":"a","type":"nope","prompt":"p","points":1}]}',
            "unknown",
        ),
        (
            '{"set_id":"x","title":"t","questions":['
            '{"id":"a","type":"multiple_choice","prompt":"p","points":1,"choices":["a"],"answer":0},'
            '{"id":"a","type":"multiple_choice","prompt":"p","points":1,"choices":["a"],"answer":0}]}',
            "duplicate",
        ),
    ],
)
def test_loader_rejects(tmp_path: Path, payload: str, match: str):
    path = tmp_path / "bad.json"
    path.write_text(payload, encoding="utf-8")
    with pytest.raises(QuestionLoadError, match=match):
        load_question_file(path)


def test_loader_duplicate_set_id(tmp_path: Path):
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    body = {
        "set_id": "same",
        "title": "T",
        "questions": [
            {
                "id": "q1",
                "type": "multiple_choice",
                "prompt": "p",
                "points": 1,
                "choices": ["a", "b"],
                "answer": 0,
            }
        ],
    }
    a.write_text(json.dumps(body), encoding="utf-8")
    body2 = dict(body)
    body2["questions"] = [
        {
            "id": "q2",
            "type": "multiple_choice",
            "prompt": "p",
            "points": 1,
            "choices": ["a", "b"],
            "answer": 0,
        }
    ]
    b.write_text(json.dumps(body2), encoding="utf-8")
    with pytest.raises(QuestionLoadError, match="duplicate set_id"):
        load_all_question_files([a, b])


def test_loader_duplicate_qid_across_sets(tmp_path: Path):
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    q = {
        "id": "shared",
        "type": "numeric",
        "prompt": "p",
        "points": 1,
        "answer": 1,
        "tolerance": 0,
    }
    a.write_text(json.dumps({"set_id": "a", "title": "A", "questions": [q]}), encoding="utf-8")
    b.write_text(json.dumps({"set_id": "b", "title": "B", "questions": [q]}), encoding="utf-8")
    with pytest.raises(QuestionLoadError, match="duplicate question id"):
        load_all_question_files([a, b])


def test_load_repo_files_score_smoke(sets):
    """Every question in the repo sample files must accept at least one score call."""
    for s in sets:
        for q in s.questions:
            # Wrong / garbage should not explode
            q.score(None, SCORING)
            q.score("garbage", SCORING)
            q.score([], SCORING)
            q.score({}, SCORING)
