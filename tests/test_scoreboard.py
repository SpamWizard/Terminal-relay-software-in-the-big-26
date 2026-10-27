"""Scoreboard Pi client: payload shape, markers, pending queue, config."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from baton_relay.config import ConfigError, ScoreboardConfig, load_config, save_config
from baton_relay.results.log import EventLog
from baton_relay.results.scoreboard import (
    bearer_token_from_base_url,
    build_payload,
    enqueue_pending,
    is_submitted,
    mark_submitted,
    pending_queue_path,
    post_run,
    retry_pending,
    runs_url,
    submit_summary,
)


ROOT = Path(__file__).resolve().parents[1]
BASE = (ROOT / "config" / "config.toml").read_text(encoding="utf-8")

ORBIT_SUMMARY = {
    "ts": "2026-10-19T21:12:34.123456+00:00",
    "team": "Orbit",
    "roster": [
        {"player_number": 1, "name": "Ada", "person_index": 0, "color": "#56B4E9"},
        {"player_number": 2, "name": "Ben", "person_index": 1, "color": "#E69F00"},
        {"player_number": 3, "name": "Cid", "person_index": 2, "color": "#009E73"},
    ],
    "started_at": "2026-10-19 21:00:00",
    "finished_at": "2026-10-19 21:12:34",
    "reason": "All categories complete.",
    "score": 42.5,
    "time_used": "12:34",
    "time_used_seconds": 754.2,
    "game_limit_seconds": 1500,
    "game_remaining": 745.8,
    "leg_remaining": 40.0,
    "players": [
        {"player_number": 1, "name": "Ada", "points": 10.0},
        {"player_number": 2, "name": "Ben", "points": 20.0},
        {"player_number": 3, "name": "Cid", "points": 12.5},
    ],
    "counted_answers": [],
    "attempts": [],
}


def _cfg(**kwargs) -> ScoreboardConfig:
    base = dict(
        enabled=True,
        base_url="http://192.168.1.50:8080",
        machine_id="station-3",
        timeout_seconds=10,
    )
    base.update(kwargs)
    return ScoreboardConfig(**base)


def test_bearer_token_is_pi_ip():
    assert bearer_token_from_base_url("http://192.168.1.50:8080") == "192.168.1.50"
    assert bearer_token_from_base_url("http://127.0.0.1:8080/") == "127.0.0.1"
    assert runs_url("http://192.168.1.50:8080") == "http://192.168.1.50:8080/api/v1/runs"


def test_payload_matches_orbit_example_shape():
    payload = build_payload(
        _cfg(),
        ORBIT_SUMMARY,
        submitted_at="2026-10-19T21:12:35Z",
    )
    assert payload == {
        "machine_id": "station-3",
        "submitted_at": "2026-10-19T21:12:35Z",
        "summary": ORBIT_SUMMARY,
    }


def test_disabled_skips_post(tmp_path: Path):
    summary_path = tmp_path / "run" / "summary.json"
    summary_path.parent.mkdir()
    summary_path.write_text(json.dumps(ORBIT_SUMMARY), encoding="utf-8")
    with patch("baton_relay.results.scoreboard.post_run") as post:
        ok = submit_summary(
            _cfg(enabled=False),
            root_dir=tmp_path,
            summary_path=summary_path,
        )
    assert ok is False
    post.assert_not_called()
    assert not is_submitted(summary_path.parent)


def test_success_marks_submitted(tmp_path: Path):
    run_dir = tmp_path / "results" / "Orbit" / "20261019T211234Z"
    summary_path = run_dir / "summary.json"
    run_dir.mkdir(parents=True)
    summary_path.write_text(json.dumps(ORBIT_SUMMARY), encoding="utf-8")
    with patch("baton_relay.results.scoreboard.post_run", return_value={"ok": True}):
        ok = submit_summary(_cfg(), root_dir=tmp_path, summary_path=summary_path)
    assert ok is True
    assert is_submitted(run_dir)
    assert not pending_queue_path(tmp_path).is_file()


def test_failure_enqueues_same_payload(tmp_path: Path):
    run_dir = tmp_path / "run"
    summary_path = run_dir / "summary.json"
    run_dir.mkdir()
    summary_path.write_text(json.dumps(ORBIT_SUMMARY), encoding="utf-8")
    with patch(
        "baton_relay.results.scoreboard.post_run",
        side_effect=OSError("down"),
    ):
        ok = submit_summary(_cfg(), root_dir=tmp_path, summary_path=summary_path)
    assert ok is False
    assert not is_submitted(run_dir)
    queue = pending_queue_path(tmp_path)
    assert queue.is_file()
    rec = json.loads(queue.read_text(encoding="utf-8").strip())
    assert rec["run_dir"] == str(run_dir)
    assert rec["payload"]["machine_id"] == "station-3"
    assert rec["payload"]["summary"]["team"] == "Orbit"


def test_retry_uses_queued_payload_not_results_scan(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    payload = build_payload(
        _cfg(), ORBIT_SUMMARY, submitted_at="2026-10-19T21:12:35Z"
    )
    enqueue_pending(tmp_path, run_dir=run_dir, payload=payload)
    # Old finished run elsewhere must not be touched/scanned into the queue.
    orphan = tmp_path / "results" / "Old" / "stamp"
    orphan.mkdir(parents=True)
    (orphan / "summary.json").write_text(json.dumps(ORBIT_SUMMARY), encoding="utf-8")

    with patch("baton_relay.results.scoreboard.post_run", return_value={"ok": True}) as post:
        n = retry_pending(_cfg(), root_dir=tmp_path)
    assert n == 1
    post.assert_called_once_with(_cfg(), payload)
    assert is_submitted(run_dir)
    assert not is_submitted(orphan)
    assert not pending_queue_path(tmp_path).is_file()


def test_already_submitted_skips_repost(tmp_path: Path):
    run_dir = tmp_path / "run"
    summary_path = run_dir / "summary.json"
    run_dir.mkdir()
    summary_path.write_text(json.dumps(ORBIT_SUMMARY), encoding="utf-8")
    mark_submitted(run_dir)
    with patch("baton_relay.results.scoreboard.post_run") as post:
        ok = submit_summary(_cfg(), root_dir=tmp_path, summary_path=summary_path)
    assert ok is True
    post.assert_not_called()


def test_write_summary_then_submit_reads_exact_file(tmp_path: Path):
    log = EventLog(tmp_path / "events.jsonl")
    summary_path = tmp_path / "summary.json"
    sheet = {k: v for k, v in ORBIT_SUMMARY.items() if k != "ts"}
    log.write_summary(summary_path, sheet)
    written = json.loads(summary_path.read_text(encoding="utf-8"))
    assert "ts" in written

    captured: list[dict] = []

    def _capture(cfg, payload):
        captured.append(payload)
        return {"ok": True}

    with patch("baton_relay.results.scoreboard.post_run", side_effect=_capture):
        assert submit_summary(_cfg(), root_dir=tmp_path, summary_path=summary_path)
    assert captured[0]["summary"] == written


def test_config_loads_scoreboard(config):
    assert isinstance(config.scoreboard.enabled, bool)
    assert config.scoreboard.machine_id
    assert config.scoreboard.base_url
    assert config.scoreboard.timeout_seconds > 0


def test_missing_scoreboard_section_defaults_disabled(tmp_path: Path):
    # Strip [scoreboard] so load uses code defaults (off until event day).
    import re

    body = re.sub(
        r"\n\[scoreboard\][^\[]*",
        "\n",
        BASE,
        count=1,
        flags=re.DOTALL,
    )
    path = tmp_path / "config.toml"
    path.write_text(body, encoding="utf-8")
    loaded = load_config(path)
    assert loaded.scoreboard.enabled is False


def test_config_roundtrip_preserves_scoreboard(config, tmp_path: Path):
    updated = config.with_updates(
        scoreboard=_cfg(
            enabled=True,
            base_url="http://10.0.0.9:8080",
            machine_id="station-14",
            timeout_seconds=8,
        )
    )
    dest = tmp_path / "out.toml"
    # questions paths must exist relative to root — reuse original via save of full config
    save_config(updated, dest)
    # Rewrite question file paths: save_config may keep them; load from dest needs files
    # Point root by nesting under a fake config/ layout
    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir()
    body = dest.read_text(encoding="utf-8")
    # Use BASE questions paths by loading BASE with scoreboard overlay
    body = BASE
    if "[scoreboard]" not in body:
        body += (
            "\n[scoreboard]\nenabled = true\n"
            'base_url = "http://10.0.0.9:8080"\n'
            'machine_id = "station-14"\n'
            "timeout_seconds = 8\n"
        )
    else:
        body = body.replace("enabled = false", "enabled = true", 1)
        body = body.replace(
            'base_url = "http://192.168.1.50:8080"',
            'base_url = "http://10.0.0.9:8080"',
            1,
        )
        body = body.replace('machine_id = "station-3"', 'machine_id = "station-14"', 1)
        body = body.replace("timeout_seconds = 10", "timeout_seconds = 8", 1)
    path = cfg_dir / "config.toml"
    path.write_text(body, encoding="utf-8")
    loaded = load_config(path)
    assert loaded.scoreboard.enabled is True
    assert loaded.scoreboard.base_url == "http://10.0.0.9:8080"
    assert loaded.scoreboard.machine_id == "station-14"
    assert loaded.scoreboard.timeout_seconds == 8


def test_config_enabled_requires_host(tmp_path: Path):
    body = BASE.replace("enabled = false", "enabled = true", 1).replace(
        'base_url = "http://192.168.1.50:8080"',
        'base_url = "not-a-url"',
        1,
    )
    path = tmp_path / "config.toml"
    path.write_text(body, encoding="utf-8")
    with pytest.raises(ConfigError, match="base_url"):
        load_config(path)


def test_post_run_sets_bearer_from_host():
    cfg = _cfg(base_url="http://127.0.0.1:8080")
    payload = build_payload(cfg, ORBIT_SUMMARY, submitted_at="2026-10-19T21:12:35Z")
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = b'{"ok":true}'
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = False
    with patch("baton_relay.results.scoreboard.urlopen", return_value=mock_resp) as opener:
        out = post_run(cfg, payload)
    assert out == {"ok": True}
    req = opener.call_args[0][0]
    assert req.full_url == "http://127.0.0.1:8080/api/v1/runs"
    assert req.get_header("Authorization") == "Bearer 127.0.0.1"
    assert req.get_header("Content-type") == "application/json"
