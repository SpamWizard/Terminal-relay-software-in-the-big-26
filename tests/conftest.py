"""Shared fixtures for the exhaustive suite."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from baton_relay.config import load_config
from baton_relay.questions.base import QuestionSet
from baton_relay.questions.loader import load_all_question_files
from baton_relay.questions.types import MultipleChoice


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "config.toml"


@pytest.fixture
def config():
    return load_config(CONFIG_PATH)


@pytest.fixture
def sets(config):
    return load_all_question_files(config.questions.files)


def with_questions(config, **kwargs):
    return config.with_updates(questions=replace(config.questions, **kwargs))


def tiny_sets(n_sets: int = 3, q_per: int = 4) -> list[QuestionSet]:
    out: list[QuestionSet] = []
    for i in range(n_sets):
        qs = [
            MultipleChoice(
                id=f"s{i}_q{j}",
                type="multiple_choice",
                prompt=f"Set {i} Q {j}",
                points=5,
                choices=["no", "yes"],
                answer=1,
            )
            for j in range(q_per)
        ]
        out.append(
            QuestionSet(
                set_id=f"cat_{i}",
                title=f"Category {i}",
                questions=qs,
            )
        )
    return out
