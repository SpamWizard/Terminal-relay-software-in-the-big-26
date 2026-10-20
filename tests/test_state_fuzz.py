"""Seeded random-walk fuzz over the state machine (fast + thorough)."""

from __future__ import annotations

import random
from dataclasses import replace

import pytest

from baton_relay.state.machine import GameSession, RelayState
from tests.conftest import tiny_sets, with_questions


def _invariants(session: GameSession) -> None:
    assert isinstance(session.state, RelayState)
    if session.progress.finished:
        assert session.state == RelayState.PAUSED_SCORE
    if session.state == RelayState.PAUSED_SCORE:
        assert session.progress.finished
    # Score equals sum of latest answers
    expected = sum(r.points for r in session.progress.answered.values())
    assert session.progress.total_score == pytest.approx(expected)
    for sid in session.progress.board_slots:
        assert sid in session._sets_by_id
        assert session._remaining_in_set(sid) > 0 or session.progress.phase != "board"


def _walk(session: GameSession, rng: random.Random, steps: int) -> None:
    team = session.config.team_size
    for _ in range(steps):
        if session.progress.finished:
            break
        action = rng.random()
        try:
            if action < 0.18:
                session.on_baton_reading(None, source="fake")
            elif action < 0.40:
                session.on_baton_reading(rng.randrange(team), source="fake")
            elif action < 0.55:
                if session.state == RelayState.CHOOSING_CATEGORY and session.progress.board_slots:
                    sid = rng.choice(session.progress.board_slots)
                    session.select_category(sid)
                else:
                    session.select_category("missing")
            elif action < 0.75:
                if session.state == RelayState.ACTIVE:
                    # Mix correct (1) and wrong (0) for tiny MC sets
                    session.submit_answer(rng.choice([0, 1, "x", None, []]))
            elif action < 0.85:
                session.skip_question(organizer=rng.random() < 0.7)
            elif action < 0.92:
                session.tick(rng.choice([0.0, 0.05, 0.5, 2.0, 30.0]))
            elif action < 0.96:
                session.on_device_disconnected()
            else:
                session.on_device_reconnected()
        except Exception as exc:  # noqa: BLE001 — fuzz must surface crashes
            raise AssertionError(
                f"crash in state={session.state} phase={session.progress.phase}: {exc}"
            ) from exc
        _invariants(session)


@pytest.mark.parametrize("seed", range(40))
def test_random_walk_seeds(config, seed: int):
    rng = random.Random(seed)
    n_sets = rng.randint(1, 5)
    q_per = rng.randint(1, 6)
    sets = tiny_sets(n_sets, q_per)
    cfg = with_questions(
        config,
        warmup_count=rng.choice([0, 0, 1, 3, 99]),
        board_slots=rng.randint(1, min(8, max(1, n_sets))),
        questions_per_pick=rng.randint(1, 8),
        redo_missed_at_set_end=rng.choice([True, False]),
    )
    cfg = cfg.with_updates(
        timers=replace(
            cfg.timers,
            leg_seconds=rng.choice([5.0, 30.0, 90.0]),
            game_seconds=rng.choice([20.0, 120.0, 2700.0]),
            leg_runs_while_frozen=rng.choice([True, False]),
            resume_bonus_seconds=rng.choice([0.0, 5.0, 10.0]),
        )
    )
    names = [f"P{i}" for i in range(cfg.team_size)]
    session = GameSession(cfg, sets, team_name=f"fuzz{seed}", player_names=names)
    _walk(session, rng, steps=200)
    _invariants(session)


@pytest.mark.parametrize(
    "warmup,slots,per_pick,n_sets,q_per",
    [
        (0, 1, 1, 1, 1),
        (0, 4, 3, 6, 2),
        (0, 8, 100, 3, 5),
        (1, 2, 2, 4, 3),
        (5, 3, 1, 2, 4),
        (999, 2, 5, 2, 2),
    ],
)
def test_category_matrix(config, warmup, slots, per_pick, n_sets, q_per):
    sets = tiny_sets(n_sets, q_per)
    cfg = with_questions(
        config,
        warmup_count=warmup,
        board_slots=slots,
        questions_per_pick=per_pick,
        redo_missed_at_set_end=False,
    )
    session = GameSession(
        cfg, sets, team_name="matrix", player_names=["A", "B", "C"]
    )
    session.on_baton_reading(0, source="fake")
    safety = 0
    while not session.progress.finished and safety < 500:
        safety += 1
        if session.state == RelayState.CHOOSING_CATEGORY:
            if not session.progress.board_slots:
                break
            session.select_category(session.progress.board_slots[0])
            if session.state == RelayState.WAITING_FOR_BATON:
                session.on_baton_reading(0, source="fake")
            continue
        if session.state == RelayState.ACTIVE:
            session.skip_question(organizer=True)
            continue
        if session.state in (RelayState.WAITING_FOR_BATON, RelayState.FROZEN):
            session.on_baton_reading(session.expected_person_index, source="fake")
            continue
        session.tick(0.1)
    # Either finished or still mid warm-up with huge warmup_count
    if warmup < n_sets * q_per:
        assert session.progress.finished or session.state == RelayState.PAUSED_SCORE
