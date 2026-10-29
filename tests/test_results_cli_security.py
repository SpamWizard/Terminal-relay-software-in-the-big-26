"""Results log, reset, checkpoint edges, CLI dispatch, security."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from baton_relay.cli import build_parser, main
from baton_relay.config import PathsConfig, save_config
from baton_relay.results.checkpoint import (
    apply_checkpoint,
    load_checkpoint,
    progress_from_dict,
    progress_to_dict,
    save_checkpoint,
    session_to_dict,
)
from baton_relay.results.log import (
    EventLog,
    find_team_folder,
    list_team_runs,
    new_run_dir,
    team_name_taken,
    team_slug,
)
from baton_relay.reset import reset_machine
from baton_relay.security import hash_password, verify_password
from baton_relay.state.machine import GameSession, Progress, RelayState
from tests.conftest import tiny_sets, with_questions


def test_team_slug_edges():
    assert team_slug("") == "team"
    assert team_slug("  ") == "team"
    assert "_" in team_slug("Hello World!")
    assert team_slug("Alpha-1") == "Alpha-1"


def test_event_log_and_summary(tmp_path: Path):
    log = EventLog(tmp_path / "events.jsonl")
    log.emit("game_started", team="X")
    log.emit("answer", points=5)
    text = (tmp_path / "events.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(text) == 2
    assert json.loads(text[0])["event"] == "game_started"
    summary_path = tmp_path / "summary.json"
    log.write_summary(summary_path, {"team": "X", "score": 5})
    data = json.loads(summary_path.read_text(encoding="utf-8"))
    assert data["score"] == 5
    assert "ts" in data


def test_score_sheet_counts_last_answer_and_time():
    from baton_relay.duration import format_duration
    from baton_relay.results.log import score_sheet

    events = [
        {
            "event": "game_started",
            "team": "Orbit",
            "local_time": "2026-10-19 21:00:00",
            "roster": [
                {"player_number": 1, "name": "Ada"},
                {"player_number": 2, "name": "Ben"},
            ],
        },
        {
            "event": "answer",
            "question_id": "mc1",
            "question_prompt": "Pick the right answer.",
            "set_title": "Type smoke test (easy)",
            "player_number": 1,
            "player_name": "Ada",
            "answer_text": "A. Wrong",
            "expected_text": "D. Right",
            "points": 0,
            "correct": False,
            "skipped": False,
        },
        {
            "event": "answer",
            "question_id": "mc1",
            "question_prompt": "Pick the right answer.",
            "set_title": "Type smoke test (easy)",
            "player_number": 2,
            "player_name": "Ben",
            "answer_text": "D. Right",
            "expected_text": "D. Right",
            "points": 2.5,
            "correct": True,
            "redo": True,
            "skipped": False,
        },
        {
            "event": "skip",
            "question_id": "short1",
            "question_prompt": "Type the word Right.",
            "player_number": 1,
            "player_name": "Ada",
            "skipped": True,
        },
        {
            "event": "game_ended",
            "score": 2.5,
            "reason": "All categories complete.",
            "local_time": "2026-10-19 21:12:34",
            "time_used_seconds": 754.2,
            "time_used": "12:34",
            "game_limit_seconds": 2700,
            "game_remaining": 1945.8,
            "leg_remaining": 40,
        },
    ]
    sheet = score_sheet(events)
    assert sheet["team"] == "Orbit"
    assert sheet["time_used"] == "12:34"
    assert sheet["finished_at"] == "2026-10-19 21:12:34"
    assert sheet["started_at"] == "2026-10-19 21:00:00"
    assert len(sheet["attempts"]) == 3
    assert sheet["attempts"][2]["kind"] == "skip"
    assert len(sheet["counted_answers"]) == 1
    assert sheet["counted_answers"][0]["answer_text"] == "D. Right"
    assert sheet["players"][0]["points"] == 0
    assert sheet["players"][1]["points"] == 2.5
    assert format_duration(754.2) == "12:34"


def test_empty_events_file_does_not_take_team_name(tmp_path: Path):
    run = new_run_dir(tmp_path, "nope")
    (run / "events.jsonl").write_text("", encoding="utf-8")
    assert find_team_folder(tmp_path, "nope") is not None
    assert list_team_runs(tmp_path, "nope") == []
    assert not team_name_taken(tmp_path, "nope")


def test_list_team_runs_finished_and_unfinished(config, tmp_path):
    run = new_run_dir(tmp_path, "Orbit")
    (run / "events.jsonl").write_text(
        '{"event":"game_started","team":"Orbit"}\n', encoding="utf-8"
    )
    assert team_name_taken(tmp_path, "Orbit")
    assert find_team_folder(tmp_path, "orbit") is not None
    runs = list_team_runs(tmp_path, "Orbit")
    assert len(runs) == 1
    assert not runs[0].finished

    (run / "summary.json").write_text('{"score":1}\n', encoding="utf-8")
    runs2 = list_team_runs(tmp_path, "Orbit")
    assert runs2[0].finished


def test_progress_roundtrip_board_fields():
    p = Progress(
        phase="board",
        warmup_done=3,
        set_cursors={"a": 2},
        board_slots=["a", "b"],
        pool=["c"],
        pick_set_id=None,
        pick_remaining=0,
        pick_missed=["x"],
        total_score=12.5,
        spent_choices={"logo_google": [0, 2]},
    )
    back = progress_from_dict(progress_to_dict(p))
    assert back.phase == "board"
    assert back.warmup_done == 3
    assert back.set_cursors == {"a": 2}
    assert back.board_slots == ["a", "b"]
    assert back.pool == ["c"]
    assert back.pick_missed == ["x"]
    assert back.total_score == 12.5
    assert back.spent_choices == {"logo_google": [0, 2]}


def test_apply_checkpoint_paused_becomes_waiting(config):
    sets = tiny_sets(1, 1)
    cfg = with_questions(config, warmup_count=99)
    session = GameSession(cfg, sets, team_name="T", player_names=["A", "B", "C"])
    data = session_to_dict(session)
    data["state"] = "PAUSED_SCORE"
    apply_checkpoint(session, data, cfg)
    assert session.state == RelayState.WAITING_FOR_BATON
    assert not session.progress.finished


def test_apply_checkpoint_unknown_state(config):
    sets = tiny_sets(1, 1)
    cfg = with_questions(config, warmup_count=99)
    session = GameSession(cfg, sets, team_name="T", player_names=["A", "B", "C"])
    data = session_to_dict(session)
    data["state"] = "NOT_A_REAL_STATE"
    apply_checkpoint(session, data, cfg)
    assert session.state == RelayState.WAITING_FOR_BATON


def test_checkpoint_corrupt_raises(config, tmp_path):
    sets = tiny_sets(1, 1)
    path = tmp_path / "bad.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        load_checkpoint(path, config, sets)


def test_reset_archives_checkpoints(config, tmp_path):
    conf = tmp_path / "config.toml"
    cfg2 = config.with_updates(
        paths=PathsConfig(
            results_dir=tmp_path / "results",
            checkpoint_path=tmp_path / "mirror.json",
        ),
        config_path=conf,
    )
    save_config(cfg2, conf)

    (tmp_path / "mirror.json").write_text('{"version":1}\n', encoding="utf-8")
    run = new_run_dir(tmp_path / "results", "TeamZ")
    (run / "checkpoint.json").write_text('{"version":1}\n', encoding="utf-8")
    (run / "events.jsonl").write_text("{}\n", encoding="utf-8")

    rc = reset_machine(conf)
    assert rc == 0
    assert not (tmp_path / "mirror.json").exists()
    assert not (run / "checkpoint.json").exists()
    archived = list((tmp_path / "results" / "_archived_checkpoints").glob("*"))
    assert len(archived) >= 2


def test_security_dev_hash():
    h = hash_password("secret")
    assert h.startswith("argon2$dev$")
    assert verify_password("secret", h)
    assert not verify_password("wrong", h)
    assert not verify_password("secret", "argon2$id$other")


def test_cli_parser_has_probe():
    p = build_parser()
    args = p.parse_args(["probe", "--port", "COM9"])
    assert args.func.__name__ == "cmd_probe"
    assert args.port == "COM9"


def test_cli_defaults_to_run():
    with patch("baton_relay.app.run_app", return_value=42) as run_app:
        assert main([]) == 42
        run_app.assert_called_once()
        assert run_app.call_args.kwargs["quick"] is False
        assert run_app.call_args.kwargs["fake_device"] is True


def test_cli_no_fake_device():
    with patch("baton_relay.app.run_app", return_value=0) as run_app:
        assert main(["run", "--no-fake-device"]) == 0
        assert run_app.call_args.kwargs["fake_device"] is False
        assert run_app.call_args.kwargs["quick"] is False


def test_cli_quick_skips_setup():
    with patch("baton_relay.app.run_app", return_value=0) as run_app:
        assert main(["quick"]) == 0
        assert run_app.call_args.kwargs["quick"] is True
        assert run_app.call_args.kwargs["fake_device"] is True
        run_app.reset_mock()
        assert main(["run", "--quick"]) == 0
        assert run_app.call_args.kwargs["quick"] is True
        assert run_app.call_args.kwargs["fake_device"] is True


def test_cli_reset_dispatch(tmp_path, config):
    conf = tmp_path / "c.toml"
    cfg = config.with_updates(
        paths=PathsConfig(
            results_dir=tmp_path / "r",
            checkpoint_path=tmp_path / "ck.json",
        ),
        config_path=conf,
    )
    save_config(cfg, conf)
    # Global --config must come after a real subcommand name, otherwise main()
    # rewrites argv to default `run`.
    with patch("baton_relay.cli._default_config_path", return_value=conf):
        assert main(["reset"]) == 0


def test_save_load_checkpoint_mid_pick(config, tmp_path):
    sets = tiny_sets(2, 3)
    cfg = with_questions(
        config, warmup_count=0, questions_per_pick=2, board_slots=2, redo_missed_at_set_end=False
    )
    session = GameSession(cfg, sets, team_name="Mid", player_names=["A", "B", "C"])
    session.on_baton_reading(0, source="fake")
    session.select_category(session.progress.board_slots[0])
    session.submit_answer(1)
    path = tmp_path / "ck.json"
    save_checkpoint(path, session)
    restored = load_checkpoint(path, cfg, sets)
    assert restored.progress.phase == "in_pick"
    assert restored.progress.pick_remaining == 1
    assert restored.state == RelayState.FROZEN  # ACTIVE → FROZEN on restore
