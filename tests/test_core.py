"""Unit tests for config, questions, baton decode, and state machine."""

from __future__ import annotations

from pathlib import Path

import pytest

from baton_relay.config import ConfigError, load_config
from baton_relay.input.decode import decode_pins
from baton_relay.input.base import ReadingKind
from baton_relay.questions.loader import QuestionLoadError, load_all_question_files
from baton_relay.questions.registry import ensure_builtin_types_loaded
from baton_relay.questions.types import MultipleChoice, SelectAll, ShortAnswer
from baton_relay.config import ScoringConfig
from baton_relay.state.machine import GameSession, RelayState


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "config.toml"


@pytest.fixture
def config():
    return load_config(CONFIG)


@pytest.fixture
def sets(config):
    return load_all_question_files(config.questions.files)


def test_load_config(config):
    assert config.team_size == 4
    assert len(config.people) == 4
    assert config.people[0].baton_pins == (1, 2)
    assert config.timers.leg_seconds > 0
    assert config.timers.game_seconds > 0
    assert config.theme.name == "neon_terminal"


def test_number_expr():
    from baton_relay.config import ConfigError, _as_number_expr

    assert _as_number_expr("4*60", "t") == 240
    assert _as_number_expr("40 * 60", "t") == 2400
    assert _as_number_expr(90, "t") == 90
    with pytest.raises(ConfigError):
        _as_number_expr("import os", "t")


def test_load_questions(sets):
    assert len(sets) == 1
    assert sets[0].set_id == "type_test"
    types = {q.type for s in sets for q in s.questions}
    for needed in (
        "multiple_choice",
        "select_all",
        "put_in_order",
        "match_up",
        "short_answer",
        "numeric",
        "fill_blank",
        "flag",
        "hands_on",
    ):
        assert needed in types


def test_bad_question_file(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text('{"set_id": "x", "title": "t", "questions": []}', encoding="utf-8")
    with pytest.raises(QuestionLoadError, match="non-empty"):
        load_all_question_files([bad])


def test_decode_exact_pair(config):
    r = decode_pins((1, 2), config)
    assert r.kind == ReadingKind.PERSON
    assert r.person_index == 0


def test_decode_unknown_one_pin(config):
    r = decode_pins((1,), config)
    assert r.kind == ReadingKind.UNKNOWN


def test_decode_empty(config):
    r = decode_pins((), config)
    assert r.kind == ReadingKind.EMPTY


def test_scoring_mc():
    ensure_builtin_types_loaded()
    q = MultipleChoice(
        id="a", type="multiple_choice", prompt="p", points=10, choices=["a", "b"], answer=1
    )
    scoring = ScoringConfig(True, 0, 0.5)
    assert q.score(1, scoring).correct
    assert q.score(0, scoring).points == 0


def test_scoring_select_all_partial():
    q = SelectAll(
        id="a",
        type="select_all",
        prompt="p",
        points=10,
        partial_credit=True,
        choices=["a", "b", "c"],
        answer=[0, 1],
    )
    scoring = ScoringConfig(True, 0, 0.5)
    partial = q.score([0], scoring)
    assert partial.partial
    assert partial.points == 5.0


def test_short_answer_casefold():
    q = ShortAnswer(
        id="a",
        type="short_answer",
        prompt="p",
        points=5,
        accepted=["Hello"],
        case_sensitive=False,
    )
    scoring = ScoringConfig(True, 0, 0.5)
    assert q.score("  hello ", scoring).correct


def test_state_machine_baton_flow(config, sets):
    # Short timers for tests
    session = GameSession(config, sets, team_name="Test")
    assert session.state == RelayState.WAITING_FOR_BATON
    # Wrong person
    session.on_baton_reading(1, source="fake")
    assert session.state == RelayState.WAITING_FOR_BATON
    assert session.wrong_baton
    # Correct person 0
    session.on_baton_reading(0, source="fake")
    assert session.state == RelayState.ACTIVE
    # Pull out
    session.on_baton_reading(None, source="fake")
    assert session.state == RelayState.FROZEN
    # Same person resumes
    session.on_baton_reading(0, source="fake")
    assert session.state == RelayState.ACTIVE


def test_timers_wait_for_first_baton(config, sets):
    session = GameSession(config, sets, team_name="Test")
    game_before = session.game_remaining
    leg_before = session.leg_remaining
    session.tick(5.0)
    assert session.game_remaining == game_before
    assert session.leg_remaining == leg_before
    assert not session.timers_started
    session.on_baton_reading(0, source="fake")
    assert session.timers_started
    session.tick(1.0)
    assert session.game_remaining == pytest.approx(game_before - 1.0)
    assert session.leg_remaining == pytest.approx(leg_before - 1.0)


def test_leg_timer_forces_swap(config, sets):
    session = GameSession(config, sets, team_name="Test")
    session.on_baton_reading(0, source="fake")
    session.leg_remaining = 0.05
    session.tick(0.1)
    assert session.state == RelayState.WAITING_FOR_BATON
    assert session.expected_person_index == 1


def test_answer_advances(config, sets):
    session = GameSession(config, sets, team_name="Test")
    session.on_baton_reading(0, source="fake")
    q = session.current_question()
    assert q is not None
    # First question is multiple_choice; "Right" is index 3
    result = session.submit_answer(3)
    assert result is not None
    assert result.correct
    assert session.progress.total_score > 0


def test_missing_config(tmp_path):
    with pytest.raises(ConfigError):
        load_config(tmp_path / "nope.toml")
