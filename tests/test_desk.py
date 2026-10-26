"""Desk sandbox, challenge folders, and scoring."""

from __future__ import annotations

from pathlib import Path

import pytest

from baton_relay.config import ScoringConfig
from baton_relay.desk.sandbox import SandboxError, resolve_in_public
from baton_relay.desk.terminal import run_desk_command
from baton_relay.questions.loader import QuestionLoadError, load_all_question_files, load_challenge_dir
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


def test_terminal_cat_and_unknown(tmp_path: Path):
    pub = tmp_path / "public"
    pub.mkdir()
    (pub / "notes.txt").write_text("hello\nTR{x}\n", encoding="utf-8")
    out = run_desk_command(pub, "cat notes.txt")
    assert "TR{x}" in out.output
    assert run_desk_command(pub, "cat ../notes.txt").exit_code == 1
    assert "unknown" in run_desk_command(pub, "rm notes.txt").output.casefold()


def test_terminal_python_script(tmp_path: Path):
    pub = tmp_path / "public"
    pub.mkdir()
    (pub / "hi.py").write_text("print('ok')\n", encoding="utf-8")
    result = run_desk_command(pub, "python hi.py")
    assert result.exit_code == 0
    assert "ok" in result.output


def test_load_find_the_line_challenge():
    qset = load_challenge_dir(ROOT / "challenges" / "find_the_line")
    assert qset.set_id == "find_the_line"
    assert len(qset.questions) == 1
    q = qset.questions[0]
    assert isinstance(q, Desk)
    assert q.score("TR{6677ac63}", SCORING).correct
    assert not q.score("TR{decoy_not_this}", SCORING).correct
    assert Path(q.public_dir).joinpath("scan.txt").is_file()
    # private must not be under public; no plaintext flag sitting in public
    assert not Path(q.public_dir).joinpath("flag.txt").exists()
    public_text = "\n".join(
        p.read_text(encoding="utf-8", errors="ignore")
        for p in Path(q.public_dir).rglob("*")
        if p.is_file() and p.suffix.casefold() in {".txt", ".html", ".py", ".md"}
    )
    assert "TR{6677ac63}" not in public_text


def test_terminal_hash_and_b64(tmp_path: Path):
    pub = tmp_path / "public"
    pub.mkdir()
    (pub / "tok.txt").write_text("relay_view_source", encoding="utf-8")
    assert "c0ffee" not in run_desk_command(pub, "sha256 hello").output  # just runs
    out = run_desk_command(pub, "b64 cmVsYXlfdmlld19zb3VyY2U=")
    assert "relay_view_source" in out.output


def test_load_all_config_challenges():
    paths = [
        ROOT / "challenges" / "find_the_line",
        ROOT / "challenges" / "bash_crumbs",
        ROOT / "challenges" / "page_source",
        ROOT / "challenges" / "stego_tail",
        ROOT / "challenges" / "broken_check",
        ROOT / "questions" / "06_fake_logos.json",
    ]
    sets = load_all_question_files(paths)
    assert len(sets) == 6
    types = {q.type for s in sets for q in s.questions}
    assert "desk" in types
    assert "multiple_choice" in types


def test_desk_challenge_requires_public(tmp_path: Path):
    root = tmp_path / "empty"
    root.mkdir()
    (root / "challenge.json").write_text(
        '{"id":"x","type":"desk","prompt":"p","points":1,"accepted":["a"]}',
        encoding="utf-8",
    )
    with pytest.raises(QuestionLoadError, match="public"):
        load_challenge_dir(root)


def test_wrong_flag_allows_retry(config):
    from baton_relay.config import load_config
    from baton_relay.state.machine import GameSession, RelayState

    cfg = load_config(ROOT / "config" / "config.toml")
    sets = load_all_question_files(cfg.questions.files)
    session = GameSession(
        cfg, sets, team_name="Retry", player_names=["A", "B", "C"]
    )
    assert session.state == RelayState.CHOOSING_CATEGORY
    sid = next(s for s in session.progress.board_slots if s == "find_the_line")
    session.select_category(sid)
    session.on_baton_reading(0, source="fake")
    bad = session.submit_answer("TR{nope}")
    assert bad is not None and not bad.correct
    assert session.progress.phase == "in_pick"
    assert session.current_question() is not None
    assert session.current_question().id == "find_the_line"
    good = session.submit_answer("TR{6677ac63}")
    assert good is not None and good.correct
    assert session.state == RelayState.CHOOSING_CATEGORY
