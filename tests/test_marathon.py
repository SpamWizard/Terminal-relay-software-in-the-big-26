"""Hour-scale stress marathon. Opt-in via marker or env.

  pytest -m marathon
  RELAY_MARATHON_SECONDS=3300 pytest -m marathon -s

Default duration is 55 minutes so a full `pytest -m marathon` run barely
fits an hour when stacked after the regular suite.
"""

from __future__ import annotations

import os
import random
import time
from dataclasses import replace

import pytest

from baton_relay.config import ScoringConfig
from baton_relay.questions.types import (
    FillBlank,
    Flag,
    MatchUp,
    MultipleChoice,
    Numeric,
    PutInOrder,
    SelectAll,
    ShortAnswer,
)
from baton_relay.results.checkpoint import (
    apply_checkpoint,
    progress_from_dict,
    progress_to_dict,
    session_to_dict,
)
from baton_relay.state.machine import GameSession, RelayState
from tests.conftest import tiny_sets, with_questions
from tests.test_state_fuzz import _invariants, _walk


pytestmark = pytest.mark.marathon


def _seconds() -> float:
    return float(os.environ.get("RELAY_MARATHON_SECONDS", "3300"))


def test_marathon_state_machine_hammer(config):
    """Random-walk sessions until the wall clock budget is spent."""
    budget = _seconds()
    # Reserve ~15% of budget for scoring + checkpoint hammers in sibling tests
    # when run together; this test takes the bulk.
    deadline = time.monotonic() + budget * 0.70
    rng = random.Random(20261019)
    walks = 0
    steps_total = 0
    while time.monotonic() < deadline:
        n_sets = rng.randint(1, 8)
        q_per = rng.randint(1, 10)
        sets = tiny_sets(n_sets, q_per)
        cfg = with_questions(
            config,
            warmup_count=rng.choice([0, 0, 0, 1, 2, 5, 50]),
            board_slots=rng.randint(1, min(8, max(1, n_sets))),
            questions_per_pick=rng.randint(1, 12),
            redo_missed_at_set_end=rng.choice([True, False]),
        )
        cfg = cfg.with_updates(
            timers=replace(
                cfg.timers,
                leg_seconds=float(rng.choice([3, 15, 60, 120])),
                game_seconds=float(rng.choice([30, 180, 900, 3600])),
                leg_runs_while_frozen=rng.choice([True, False]),
                resume_bonus_seconds=float(rng.choice([0, 5, 10])),
            ),
            scoring=ScoringConfig(
                partial_credit=rng.choice([True, False]),
                wrong_answer_penalty=float(rng.choice([0, 1, 5])),
                redo_multiplier=float(rng.choice([0.25, 0.5, 1.0])),
            ),
        )
        names = [f"P{i}" for i in range(cfg.team_size)]
        session = GameSession(cfg, sets, team_name=f"m{walks}", player_names=names)
        steps = rng.randint(80, 400)
        _walk(session, rng, steps)
        _invariants(session)
        # Occasional checkpoint roundtrip mid-chaos
        if walks % 7 == 0:
            data = session_to_dict(session)
            apply_checkpoint(session, data, cfg)
            _invariants(session)
            p2 = progress_from_dict(progress_to_dict(session.progress))
            assert p2.phase == session.progress.phase
        walks += 1
        steps_total += steps
        if walks % 25 == 0:
            left = max(0.0, deadline - time.monotonic())
            print(
                f"[marathon] walks={walks} steps={steps_total} left={left:.0f}s",
                flush=True,
            )
    assert walks >= 10, f"marathon too short: only {walks} walks"
    print(f"\n[marathon] walks={walks} steps={steps_total} budget={budget}s", flush=True)


def test_marathon_scoring_hammer():
    """Pound every scorer with garbage + correct answers for the remaining budget."""
    budget = _seconds() * 0.15
    deadline = time.monotonic() + budget
    rng = random.Random(42)
    scoring_opts = [
        ScoringConfig(True, 0, 0.5),
        ScoringConfig(False, 0, 0.5),
        ScoringConfig(True, 3, 0.25),
        ScoringConfig(False, 10, 1.0),
    ]
    questions = [
        MultipleChoice(
            id="mc", type="multiple_choice", prompt="p", points=10, choices=["a", "b", "c"], answer=2
        ),
        SelectAll(
            id="sa",
            type="select_all",
            prompt="p",
            points=10,
            choices=["a", "b", "c", "d"],
            answer=[0, 2],
            partial_credit=True,
        ),
        PutInOrder(
            id="ord", type="put_in_order", prompt="p", points=8, items=["a", "b", "c"], answer=[1, 2, 0]
        ),
        MatchUp(
            id="mu",
            type="match_up",
            prompt="p",
            points=9,
            left=["a", "b", "c"],
            right=["A", "B", "C"],
            answer={"0": 1, "1": 2, "2": 0},
        ),
        ShortAnswer(id="sh", type="short_answer", prompt="p", points=5, accepted=["yes", "y"]),
        Numeric(id="nu", type="numeric", prompt="p", points=5, answer=3.14, tolerance=0.01),
        FillBlank(id="fb", type="fill_blank", prompt="p", points=4, accepted=["blue"]),
        Flag(id="fl", type="flag", prompt="p", points=4, accepted=["FLAG{z}"]),
    ]
    garbage = [
        None,
        "",
        "nope",
        0,
        1,
        2,
        99,
        -1,
        [],
        {},
        [0],
        [0, 1, 2],
        {"0": 0},
        3.14,
        "FLAG{z}",
        "yes",
        "Y",
    ]
    n = 0
    while time.monotonic() < deadline:
        q = rng.choice(questions)
        sc = rng.choice(scoring_opts)
        q.score(rng.choice(garbage), sc)
        n += 1
    assert n >= 1000
    print(f"\n[marathon] scoring calls={n}")


def test_marathon_exhaust_boards(config):
    """Repeatedly drain boards of many tiny categories."""
    budget = _seconds() * 0.15
    deadline = time.monotonic() + budget
    games = 0
    while time.monotonic() < deadline:
        sets = tiny_sets(8, 3)
        cfg = with_questions(
            config,
            warmup_count=0,
            board_slots=6,
            questions_per_pick=2,
            redo_missed_at_set_end=False,
        )
        session = GameSession(
            cfg, sets, team_name=f"ex{games}", player_names=["A", "B", "C"]
        )
        session.on_baton_reading(0, source="fake")
        guard = 0
        while not session.progress.finished and guard < 400:
            guard += 1
            if session.state == RelayState.CHOOSING_CATEGORY:
                if not session.progress.board_slots:
                    break
                session.select_category(session.progress.board_slots[0])
                if session.state == RelayState.WAITING_FOR_BATON:
                    session.on_baton_reading(0, source="fake")
            elif session.state == RelayState.ACTIVE:
                session.submit_answer(1)
            elif session.state in (RelayState.WAITING_FOR_BATON, RelayState.FROZEN):
                session.on_baton_reading(session.expected_person_index, source="fake")
            else:
                session.tick(0.2)
        assert session.progress.finished
        games += 1
    assert games >= 5
    print(f"\n[marathon] full drains={games}")
