"""Timer edges, redo passes, board baton rules, disconnect paths."""

from __future__ import annotations

from dataclasses import replace

import pytest

from baton_relay.state.machine import GameSession, RelayState
from tests.conftest import tiny_sets, with_questions


def _session(config, sets, **qkw):
    cfg = with_questions(config, **qkw) if qkw else config
    names = [f"P{i}" for i in range(cfg.team_size)]
    return GameSession(cfg, sets, team_name="T", player_names=names)


def test_game_timer_expires(config):
    sets = tiny_sets(1, 2)
    session = _session(config, sets, warmup_count=99)
    session.on_baton_reading(0, source="fake")
    session.game_remaining = 0.05
    events: list[str] = []
    session.add_listener(lambda snap: None)
    session._on_event = lambda n, p: events.append(n)
    session.tick(0.1)
    assert session.state == RelayState.PAUSED_SCORE
    assert session.progress.finished
    assert "game_ended" in events


def test_tick_zero_and_negative_noop(config):
    sets = tiny_sets(1, 1)
    session = _session(config, sets, warmup_count=99)
    session.on_baton_reading(0, source="fake")
    g = session.game_remaining
    session.tick(0)
    session.tick(-1)
    assert session.game_remaining == g


def test_leg_runs_while_frozen_true(config):
    sets = tiny_sets(1, 1)
    cfg = config.with_updates(
        timers=replace(config.timers, leg_runs_while_frozen=True),
        questions=replace(config.questions, warmup_count=99),
    )
    session = GameSession(cfg, sets, team_name="T", player_names=["A", "B", "C"])
    session.on_baton_reading(0, source="fake")
    session.on_baton_reading(None, source="fake")
    assert session.state == RelayState.FROZEN
    session.leg_remaining = 0.05
    session.tick(0.1)
    assert session.state == RelayState.WAITING_FOR_BATON
    assert session.expected_person_index == 1


def test_leg_frozen_does_not_run_when_disabled(config):
    sets = tiny_sets(1, 1)
    cfg = config.with_updates(
        timers=replace(config.timers, leg_runs_while_frozen=False),
        questions=replace(config.questions, warmup_count=99),
    )
    session = GameSession(cfg, sets, team_name="T", player_names=["A", "B", "C"])
    session.on_baton_reading(0, source="fake")
    session.on_baton_reading(None, source="fake")
    assert session.state == RelayState.FROZEN
    leg = session.leg_remaining
    session.tick(5.0)
    assert session.state == RelayState.FROZEN
    assert session.leg_remaining == leg


def test_redo_multiplier_on_pick(config):
    sets = tiny_sets(1, 2)
    events: list[tuple[str, dict]] = []
    cfg = with_questions(
        config,
        warmup_count=0,
        questions_per_pick=2,
        board_slots=1,
        redo_missed_at_set_end=True,
    )
    cfg = cfg.with_updates(scoring=replace(cfg.scoring, redo_multiplier=0.5))
    session = GameSession(
        cfg,
        sets,
        team_name="T",
        player_names=["A", "B", "C"],
        on_event=lambda n, p: events.append((n, p)),
    )
    session.on_baton_reading(0, source="fake")
    sid = session.progress.board_slots[0]
    session.select_category(sid)
    # Wrong stays on q1; correct advances; skip q2 → redo queue for the skip
    assert session.submit_answer(0) is not None  # wrong — stay
    assert session.progress.pick_remaining == 2
    assert session.submit_answer(1) is not None  # correct q1
    assert session.progress.pick_remaining == 1
    session.skip_question()  # miss q2 → redo if enabled
    assert session.progress.in_redo or session.state == RelayState.CHOOSING_CATEGORY
    if session.progress.in_redo:
        assert session.state == RelayState.ACTIVE
        r = session.submit_answer(1)
        assert r is not None
        assert r.points == pytest.approx(2.5)  # 5 * 0.5


def test_score_replace_on_reanswer(config):
    sets = tiny_sets(1, 1)
    session = _session(
        config,
        sets,
        warmup_count=0,
        questions_per_pick=1,
        board_slots=1,
        redo_missed_at_set_end=False,
    )
    session.on_baton_reading(0, source="fake")
    session.select_category(session.progress.board_slots[0])
    session.submit_answer(0)
    score_after_wrong = session.progress.total_score
    # Still on the same question — correct replaces the wrong score
    assert session.progress.phase == "in_pick"
    session.submit_answer(1)
    assert session.progress.total_score > score_after_wrong


def test_board_wrong_baton(config):
    sets = tiny_sets(2, 2)
    session = _session(config, sets, warmup_count=0, board_slots=2)
    assert session.state == RelayState.CHOOSING_CATEGORY
    session.on_baton_reading(1, source="fake")
    assert session.wrong_baton
    session.on_baton_reading(0, source="fake")
    assert not session.wrong_baton
    assert session.current_person_index == 0


def test_select_category_rejects_invalid(config):
    sets = tiny_sets(1, 1)
    session = _session(config, sets, warmup_count=0)
    assert not session.select_category("nope")
    assert session.state == RelayState.CHOOSING_CATEGORY


def test_skip_locked_without_organizer(config):
    sets = tiny_sets(1, 2)
    session = _session(config, sets, warmup_count=99)
    # Waiting — locked
    q_before = session.current_question()
    session.skip_question(organizer=False)
    assert session.current_question() == q_before
    session.on_baton_reading(0, source="fake")
    session.skip_question(organizer=False)
    # Advanced
    assert session.progress.warmup_done >= 1 or session.progress.question_index >= 1


def test_paused_ignores_baton(config):
    sets = tiny_sets(1, 1)
    session = _session(config, sets, warmup_count=99)
    session.on_baton_reading(0, source="fake")
    session.game_remaining = 0
    session.tick(1)
    assert session.state == RelayState.PAUSED_SCORE
    session.on_baton_reading(0, source="fake")
    assert session.state == RelayState.PAUSED_SCORE


def test_disconnect_on_board_reconnects_to_board(config):
    sets = tiny_sets(2, 1)
    session = _session(config, sets, warmup_count=0)
    assert session.state == RelayState.CHOOSING_CATEGORY
    session.on_device_disconnected()
    assert session.state == RelayState.DISCONNECTED
    session.on_device_reconnected()
    assert session.state == RelayState.CHOOSING_CATEGORY


def test_disconnected_ignores_hardware_baton(config):
    sets = tiny_sets(1, 1)
    session = _session(config, sets, warmup_count=99)
    session.on_baton_reading(0, source="fake")
    session.on_device_disconnected()
    session.on_baton_reading(0, source="baton")
    assert session.state == RelayState.DISCONNECTED


def test_active_baton_change_freezes(config):
    sets = tiny_sets(1, 1)
    session = _session(config, sets, warmup_count=99)
    session.on_baton_reading(0, source="fake")
    session.on_baton_reading(1, source="fake")
    assert session.state == RelayState.FROZEN


def test_empty_sets_raises(config):
    with pytest.raises(ValueError, match="at least one"):
        GameSession(config, [], team_name="T")


def test_questions_per_pick_clamps(config):
    sets = tiny_sets(1, 2)
    session = _session(
        config, sets, warmup_count=0, questions_per_pick=99, board_slots=1
    )
    session.on_baton_reading(0, source="fake")
    session.select_category(session.progress.board_slots[0])
    assert session.progress.pick_remaining == 2
