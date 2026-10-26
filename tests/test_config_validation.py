"""Config validation matrix and save/load fidelity."""

from __future__ import annotations

from pathlib import Path

import pytest

from baton_relay.config import ConfigError, _as_number_expr, load_config, save_config


ROOT = Path(__file__).resolve().parents[1]
BASE = (ROOT / "config" / "config.toml").read_text(encoding="utf-8")


def _write(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "config.toml"
    p.write_text(body, encoding="utf-8")
    return p


def test_full_roundtrip_preserves_questions(config, tmp_path):
    dest = tmp_path / "out.toml"
    save_config(config, dest)
    reloaded = load_config(dest)
    assert reloaded.questions.warmup_count == config.questions.warmup_count
    assert reloaded.questions.board_slots == config.questions.board_slots
    assert reloaded.questions.questions_per_pick == config.questions.questions_per_pick
    assert reloaded.questions.redo_missed_at_set_end == config.questions.redo_missed_at_set_end
    assert len(reloaded.questions.files) == len(config.questions.files)
    assert reloaded.team_size == config.team_size
    assert reloaded.rotation == config.rotation
    assert [p.id for p in reloaded.people] == [p.id for p in config.people]
    assert reloaded.scoring.partial_credit == config.scoring.partial_credit
    assert reloaded.organizer_password_hash == config.organizer_password_hash


@pytest.mark.parametrize(
    "expr,expected",
    [
        ("4*60", 240),
        ("40 * 60", 2400),
        ("(3+1)*60", 240),
        ("2**3", 8),
        ("10//3", 3),
        ("-5", -5),
        ("100%7", 2),
    ],
)
def test_number_expr_extended(expr, expected):
    assert _as_number_expr(expr, "t") == expected


@pytest.mark.parametrize(
    "expr",
    ["import os", "os.system", "__import__", "a+b", "1 and 1", "lambda:1"],
)
def test_number_expr_rejects_unsafe(expr):
    with pytest.raises(ConfigError):
        _as_number_expr(expr, "t")


def test_bad_team_size(tmp_path):
    if "size = 3" in BASE:
        body = BASE.replace("size = 3", "size = 2", 1)
    elif "size = 4" in BASE:
        body = BASE.replace("size = 4", "size = 2", 1)
    else:
        pytest.skip("unexpected team size in base config")
    with pytest.raises(ConfigError, match="must be 3-6"):
        load_config(_write(tmp_path, body))


def test_negative_warmup(tmp_path):
    if "warmup_count" not in BASE:
        pytest.skip("no warmup_count in base config")
    body = BASE.replace("warmup_count = 0", "warmup_count = -1", 1)
    with pytest.raises(ConfigError, match="warmup_count"):
        load_config(_write(tmp_path, body))


def test_zero_board_slots(tmp_path):
    import re

    body = re.sub(r"board_slots = \d+", "board_slots = 0", BASE, count=1)
    with pytest.raises(ConfigError, match="board_slots"):
        load_config(_write(tmp_path, body))


def test_zero_questions_per_pick(tmp_path):
    import re

    body = re.sub(r"questions_per_pick = \d+", "questions_per_pick = 0", BASE, count=1)
    with pytest.raises(ConfigError, match="questions_per_pick"):
        load_config(_write(tmp_path, body))


def test_empty_question_files(tmp_path):
    # Replace files list with empty
    import re

    body = re.sub(
        r"files = \[[^\]]*\]",
        "files = []",
        BASE,
        count=1,
        flags=re.DOTALL,
    )
    with pytest.raises(ConfigError, match="files"):
        load_config(_write(tmp_path, body))


def test_person_for_pins(config):
    p = config.people[0]
    found = config.person_for_pins(tuple(sorted(p.baton_pins)))
    assert found is not None
    assert found.id == p.id
    assert config.person_for_pins((9, 8)) is None


def test_with_updates_immutable(config):
    other = config.with_updates(team_size=config.team_size)
    assert other.team_size == config.team_size
