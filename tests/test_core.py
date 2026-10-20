"""Unit tests for config, questions, baton decode, and state machine."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from baton_relay.config import ConfigError, ScoringConfig, load_config
from baton_relay.input.decode import decode_pins
from baton_relay.input.base import ReadingKind
from baton_relay.questions.loader import QuestionLoadError, load_all_question_files
from baton_relay.questions.registry import ensure_builtin_types_loaded
from baton_relay.questions.types import MultipleChoice, SelectAll, ShortAnswer
from baton_relay.state.machine import GameSession, RelayState


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "config.toml"


@pytest.fixture
def config():
    return load_config(CONFIG)


@pytest.fixture
def sets(config):
    return load_all_question_files(config.questions.files)


def _with_warmup(config, warmup_count: int = 9999, **q_kwargs):
    """Linear warm-up mode for tests that answer before the board."""
    q = replace(config.questions, warmup_count=warmup_count, **q_kwargs)
    return config.with_updates(questions=q)


def test_load_config(config):
    assert config.team_size == len(config.people)
    assert config.team_size >= 2
    assert config.people[0].baton_pins == (1, 2)
    assert config.timers.leg_seconds > 0
    assert config.timers.game_seconds > 0
    assert config.timers.resume_bonus_seconds == 10
    assert config.theme.name == "deep_space"
    assert config.controller.unlock_buttons  # organizer-configurable chord
    assert all(b for b in config.controller.unlock_buttons)
    assert config.controller.bindings["confirm"] == "A"
    assert config.questions.warmup_count == 0
    assert config.questions.board_slots >= 1
    assert config.questions.questions_per_pick >= 1


def test_number_expr():
    from baton_relay.config import ConfigError, _as_number_expr

    assert _as_number_expr("4*60", "t") == 240
    assert _as_number_expr("40 * 60", "t") == 2400
    assert _as_number_expr(90, "t") == 90
    with pytest.raises(ConfigError):
        _as_number_expr("import os", "t")


def test_load_questions(sets):
    assert len(sets) >= 2
    ids = {s.set_id for s in sets}
    assert "type_test" in ids
    assert "potatoes" in ids
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


def test_pins_from_mask():
    from baton_relay.input.decode import pins_from_mask

    assert pins_from_mask(0b00000) == ()
    assert pins_from_mask(0b00011) == (1, 2)
    assert pins_from_mask(0b10101) == (1, 3, 5)


def test_split_serial_lines():
    from baton_relay.probe import split_serial_lines

    buf = bytearray(b"Adafruit CircuitPython\nHB pins=0b00011 seq=1\npartial")
    masks, others = split_serial_lines(buf)
    assert masks == [0b00011]
    assert others == ["Adafruit CircuitPython"]
    assert bytes(buf) == b"partial"


def test_describe_mask(config):
    from baton_relay.probe import describe_mask

    plugged = describe_mask(0b00011, config)
    assert "1:ON" in plugged
    assert "2:ON" in plugged
    assert "3:--" in plugged
    assert "#1 A" in plugged
    assert "nothing plugged in" in describe_mask(0, config)
    assert "unknown (1)" in describe_mask(0b00001, config)


def test_parse_heartbeat():
    from baton_relay.input.serial_source import parse_heartbeat

    assert parse_heartbeat("HB pins=0b00011 seq=9") == (0b00011, 9)
    assert parse_heartbeat("HB pins=0b10101") == (0b10101, None)
    assert parse_heartbeat("HB pins=0x15 seq=1") == (0x15 & 0x1F, 1)
    assert parse_heartbeat("HB pins=3 seq=2") == (3, 2)
    assert parse_heartbeat("garbage") is None
    assert parse_heartbeat("") is None


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
    cfg = _with_warmup(config)
    session = GameSession(
        cfg, sets, team_name="Test", player_names=["Ada", "Ben", "Cy", "Dee"]
    )
    assert session.state == RelayState.WAITING_FOR_BATON
    assert session.roster[0].player_number == 1
    assert session.roster[0].name == "Ada"
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
    # Same person resumes — gains resume bonus on leg + game timers
    leg_before = session.leg_remaining
    game_before = session.game_remaining
    session.on_baton_reading(0, source="fake")
    assert session.state == RelayState.ACTIVE
    assert session.leg_remaining == pytest.approx(
        leg_before + cfg.timers.resume_bonus_seconds
    )
    assert session.game_remaining == pytest.approx(
        game_before + cfg.timers.resume_bonus_seconds
    )


def test_answer_logs_player(config, sets):
    events: list[tuple[str, dict]] = []
    cfg = _with_warmup(config)
    session = GameSession(
        cfg,
        sets,
        team_name="Nova",
        player_names=["Ada", "Ben", "Cy", "Dee"],
        on_event=lambda n, p: events.append((n, p)),
    )
    session.on_baton_reading(0, source="fake")
    result = session.submit_answer(3)
    assert result is not None
    answer_events = [p for n, p in events if n == "answer"]
    assert answer_events
    payload = answer_events[0]
    assert payload["player_name"] == "Ada"
    assert payload["player_number"] == 1
    assert payload["team"] == "Nova"
    assert payload["set_title"]
    assert payload["question_prompt"]
    assert payload["answer_text"] == "D. Right"
    assert payload["expected_text"] == "D. Right"
    assert payload["points"] == 5
    assert payload["max_points"] == 5
    assert "time_used" in payload
    assert "local_time" in payload


def test_timers_wait_for_first_baton(config, sets):
    cfg = _with_warmup(config)
    session = GameSession(cfg, sets, team_name="Test")
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
    cfg = _with_warmup(config)
    session = GameSession(cfg, sets, team_name="Test")
    session.on_baton_reading(0, source="fake")
    session.leg_remaining = 0.05
    session.tick(0.1)
    assert session.state == RelayState.WAITING_FOR_BATON
    assert session.expected_person_index == 1


def test_answer_advances(config, sets):
    cfg = _with_warmup(config)
    session = GameSession(cfg, sets, team_name="Test")
    session.on_baton_reading(0, source="fake")
    q = session.current_question()
    assert q is not None
    # First question is multiple_choice; "Right" is index 3
    result = session.submit_answer(3)
    assert result is not None
    assert result.correct
    assert session.progress.total_score > 0


def test_board_opens_when_warmup_zero(config, sets):
    session = GameSession(config, sets, team_name="Test")
    assert session.state == RelayState.CHOOSING_CATEGORY
    assert session.progress.phase == "board"
    cats = session.board_categories()
    assert len(cats) >= 1
    assert all(title for _sid, title in cats)


def test_board_timers_frozen(config, sets):
    session = GameSession(config, sets, team_name="Test")
    assert session.state == RelayState.CHOOSING_CATEGORY
    # Pretend timers already started (e.g. mid-run return to board)
    session.timers_started = True
    game_before = session.game_remaining
    leg_before = session.leg_remaining
    notes: list[int] = []
    session.add_listener(lambda _snap: notes.append(1))
    session.tick(5.0)
    assert session.game_remaining == game_before
    assert session.leg_remaining == leg_before
    assert notes == []


def test_select_category_and_refill(config, sets):
    cfg = _with_warmup(config, warmup_count=0, questions_per_pick=1, board_slots=2)
    session = GameSession(
        cfg, sets, team_name="Test", player_names=["Ada", "Ben", "Cy", "Dee"]
    )
    assert session.state == RelayState.CHOOSING_CATEGORY
    first_id = session.progress.board_slots[0]
    assert session.select_category(first_id)
    assert session.progress.phase == "in_pick"
    assert session.progress.pick_remaining == 1
    # Need baton to answer
    assert session.state == RelayState.WAITING_FOR_BATON
    session.on_baton_reading(0, source="fake")
    q = session.current_question()
    assert q is not None
    # Answer correctly for first Q of whichever set was picked
    if q.type == "multiple_choice":
        session.submit_answer(q.answer)  # type: ignore[attr-defined]
    elif q.type == "short_answer":
        session.submit_answer(q.accepted[0])  # type: ignore[attr-defined]
    else:
        session.skip_question(organizer=True)
    # Back on board with a category (refill or remaining)
    assert session.state == RelayState.CHOOSING_CATEGORY
    assert session.progress.board_slots


def test_warmup_then_board(config, sets):
    cfg = _with_warmup(config, warmup_count=1, questions_per_pick=2, board_slots=4)
    session = GameSession(
        cfg, sets, team_name="Test", player_names=["Ada", "Ben", "Cy", "Dee"]
    )
    assert session.state == RelayState.WAITING_FOR_BATON
    assert session.progress.phase == "warmup"
    session.on_baton_reading(0, source="fake")
    session.submit_answer(3)  # first MC in type_test
    assert session.state == RelayState.CHOOSING_CATEGORY
    assert session.progress.phase == "board"
    # First question of type_test consumed
    assert session.progress.set_cursors.get("type_test", 0) >= 1


def test_board_ends_when_categories_exhausted(config, sets):
    # One question per pick; exhaust everything
    cfg = _with_warmup(
        config,
        warmup_count=0,
        questions_per_pick=100,
        board_slots=8,
        redo_missed_at_set_end=False,
    )
    events: list[tuple[str, dict]] = []
    session = GameSession(
        cfg,
        sets,
        team_name="Test",
        player_names=["Ada", "Ben", "Cy", "Dee"],
        on_event=lambda n, p: events.append((n, p)),
    )
    session.on_baton_reading(0, source="fake")  # ready while on board
    # Drain all categories
    safety = 0
    while session.state == RelayState.CHOOSING_CATEGORY and safety < 50:
        safety += 1
        sid = session.progress.board_slots[0]
        session.select_category(sid)
        if session.state == RelayState.WAITING_FOR_BATON:
            session.on_baton_reading(0, source="fake")
        while session.progress.phase == "in_pick" and not session.progress.finished:
            q = session.current_question()
            if q is None:
                break
            session.skip_question(organizer=True)
    assert session.state == RelayState.PAUSED_SCORE
    ended = [p for n, p in events if n == "game_ended"]
    assert ended
    assert "game_remaining" in ended[0]
    assert "leg_remaining" in ended[0]


def test_missing_config(tmp_path):
    with pytest.raises(ConfigError):
        load_config(tmp_path / "nope.toml")


def test_save_config_roundtrip(config, tmp_path):
    from dataclasses import replace

    from baton_relay.config import save_config

    dest = tmp_path / "config.toml"
    save_config(config, dest)
    reloaded = load_config(dest)
    assert reloaded.team_size == config.team_size
    assert reloaded.timers.resume_bonus_seconds == config.timers.resume_bonus_seconds
    assert reloaded.controller.bindings == config.controller.bindings
    assert reloaded.theme.name == config.theme.name

    disabled = config.with_updates(
        controller=replace(config.controller, enabled=False)
    )
    save_config(disabled, dest)
    assert load_config(dest).controller.enabled is False


def test_team_name_collision_and_resume(config, sets, tmp_path):
    from baton_relay.results.checkpoint import load_checkpoint, save_checkpoint
    from baton_relay.results.log import (
        find_resumable_run,
        new_run_dir,
        team_name_taken,
    )

    cfg = _with_warmup(config)
    assert not team_name_taken(tmp_path, "Orbit")
    run = new_run_dir(tmp_path, "Orbit")
    session = GameSession(
        cfg, sets, team_name="Orbit", player_names=["Ada", "Ben", "Cy", "Dee"]
    )
    session.on_baton_reading(0, source="fake")
    session.submit_answer(3)
    save_checkpoint(run / "checkpoint.json", session)
    (run / "events.jsonl").write_text(
        '{"event":"game_started","team":"Orbit"}\n', encoding="utf-8"
    )

    assert team_name_taken(tmp_path, "Orbit")
    assert team_name_taken(tmp_path, "orbit")
    resumable = find_resumable_run(tmp_path, "Orbit")
    assert resumable is not None
    assert resumable.run_dir == run

    restored = load_checkpoint(run / "checkpoint.json", cfg, sets)
    assert restored.team_name == "Orbit"
    assert restored.roster[0].name == "Ada"
    assert restored.progress.total_score > 0
    assert restored.state == RelayState.FROZEN  # mid-leg requires baton again


def test_player_display_skips_numeric_duplicate(config, sets):
    session = GameSession(
        _with_warmup(config), sets, team_name="T", player_names=["1", "Ben", "Cy", "Dee"]
    )
    assert session.player_display(0) == "#1"
    assert session.player_display(1) == "#2 Ben"


def test_device_reconnect_returns_to_frozen(config, sets):
    session = GameSession(
        _with_warmup(config),
        sets,
        team_name="T",
        player_names=["Ada", "Ben", "Cy", "Dee"],
    )
    session.on_baton_reading(0, source="fake")
    assert session.state == RelayState.ACTIVE
    session.on_device_disconnected()
    assert session.state == RelayState.DISCONNECTED
    session.on_device_reconnected()
    assert session.state == RelayState.FROZEN
    assert session.current_person_index == 0


def test_checkpoint_restores_board(config, sets, tmp_path):
    from baton_relay.results.checkpoint import load_checkpoint, save_checkpoint

    session = GameSession(
        config, sets, team_name="Board", player_names=["Ada", "Ben", "Cy", "Dee"]
    )
    assert session.state == RelayState.CHOOSING_CATEGORY
    slots = list(session.progress.board_slots)
    path = tmp_path / "checkpoint.json"
    save_checkpoint(path, session)
    restored = load_checkpoint(path, config, sets)
    assert restored.state == RelayState.CHOOSING_CATEGORY
    assert restored.progress.board_slots == slots
    assert restored.progress.phase == "board"
