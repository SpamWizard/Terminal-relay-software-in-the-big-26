"""Desk sandbox, challenge folders, and WSL shell helpers (no live WSL required)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from baton_relay.config import ScoringConfig
from baton_relay.desk.sandbox import SandboxError, resolve_in_public
from baton_relay.desk.shell import TeamShell, distro_name
from baton_relay.questions.loader import load_challenge_dir
from baton_relay.questions.registry import ensure_builtin_types_loaded
from baton_relay.questions.types import Desk


ROOT = Path(__file__).resolve().parents[1]
SCORING = ScoringConfig(partial_credit=True, wrong_answer_penalty=0, redo_multiplier=0.5)


@pytest.fixture(autouse=True)
def _types():
    ensure_builtin_types_loaded()


def test_resolve_blocks_escape(tmp_path: Path):
    pub = tmp_path / "public"
    pub.mkdir()
    (pub / "a.txt").write_text("x", encoding="utf-8")
    assert resolve_in_public(pub, "a.txt").name == "a.txt"
    with pytest.raises(SandboxError):
        resolve_in_public(pub, "../secret")
    with pytest.raises(SandboxError):
        resolve_in_public(pub, "C:/Windows/notepad.exe")


def test_load_hello_shell_challenge():
    qset = load_challenge_dir(ROOT / "challenges" / "hello_shell")
    assert qset.set_id == "hello_shell"
    assert len(qset.questions) == 1
    q = qset.questions[0]
    assert isinstance(q, Desk)
    assert q.score("TR{hello_wsl_desk}", SCORING).correct
    assert not q.score("TR{nope}", SCORING).correct
    pub = Path(q.public_dir)
    assert (pub / "notes.txt").is_file()
    assert "TR{hello_wsl_desk}" in (pub / "notes.txt").read_text(encoding="utf-8")


def test_distro_name_slug():
    assert distro_name("Red Team!").startswith("relay-")


def test_locked_shell_drops_lines():
    shell = TeamShell(distro="relay-test", repo_root=ROOT)
    shell._proc = MagicMock()
    shell._proc.poll.return_value = None
    shell._proc.stdin = MagicMock()
    shell.locked = True
    shell.send_line("echo should-not-run")
    shell._proc.stdin.write.assert_not_called()
    assert "should-not-run" not in shell.transcript

    shell.locked = False
    shell.send_line("echo hi")
    shell._proc.stdin.write.assert_called()
    assert "› echo hi" in shell.transcript


def test_load_config_files():
    from baton_relay.config import load_config
    from baton_relay.questions.loader import load_all_question_files

    cfg = load_config(ROOT / "config" / "config.toml")
    sets = load_all_question_files(cfg.questions.files)
    types = {q.type for s in sets for q in s.questions}
    assert "desk" in types
    assert "multiple_choice" in types
    ids = {s.set_id for s in sets}
    assert "hello_shell" in ids
    assert "fake_logos" in ids or any("logo" in s.title.casefold() for s in sets)
