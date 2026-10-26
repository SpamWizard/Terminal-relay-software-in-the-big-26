"""SaintCon board payload, push policy, and the local display."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from datetime import datetime, timezone
from email.message import Message
from io import BytesIO
from pathlib import Path

import pytest

from baton_relay.cli import main
from baton_relay.config import ConfigError, PathsConfig, load_config, save_config, scoreboard_settings
from baton_relay.scoreboard.display import make_server, page_html
from baton_relay.scoreboard.sync import build_synced_board
from baton_relay.scoreboard.model import (
    TeamStanding,
    board_signature,
    build_board,
    collect_standings,
    payload_from_standings,
)
from baton_relay.scoreboard.publish import (
    PushState,
    RejectRedirect,
    ScoreboardError,
    attempt_push,
    push_once,
    push_payload,
    resolve_api_key,
)

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 28, 19, 4, tzinfo=timezone.utc)
BOARD_URL = "https://saintcon.org/api/scoreboards/demo"


def _summary(
    results: Path,
    team: str,
    *,
    score: float,
    seconds: float,
    solved: int = 1,
    roster: tuple[str, ...] = ("Ada", "Ben"),
    stamp: str = "20261026T120000Z",
) -> Path:
    slug = "".join(c if c.isalnum() or c in "-_" else "_" for c in team) or "team"
    run = results / slug / stamp
    run.mkdir(parents=True, exist_ok=True)
    payload = {
        "team": team,
        "score": score,
        "time_used_seconds": seconds,
        "roster": [{"name": name} for name in roster],
        "counted_answers": [{"correct": True} for _ in range(solved)],
    }
    path = run / "summary.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _checkpoint(
    results: Path,
    team: str,
    *,
    score: float,
    remaining: float,
    solved: int = 1,
) -> None:
    slug = "".join(c if c.isalnum() or c in "-_" else "_" for c in team) or "team"
    run = results / slug / "20261026T130000Z"
    run.mkdir(parents=True, exist_ok=True)
    payload = {
        "team_name": team,
        "game_remaining": remaining,
        "roster": [{"name": "Ada"}, {"name": "Ben"}],
        "progress": {
            "total_score": score,
            "answered": {f"q{i}": {"correct": True} for i in range(solved)},
        },
    }
    (run / "checkpoint.json").write_text(json.dumps(payload), encoding="utf-8")


def _board_config(config, results: Path, **kwargs):
    defaults = dict(
        enabled=True,
        board_id="demo",
        status="live",
        frozen=False,
        message="Finals 3 PM, Ballroom B",
        interval_seconds=60,
    )
    defaults.update(kwargs)
    return config.with_updates(
        paths=PathsConfig(results_dir=results, checkpoint_path=results / "none.json"),
        scoreboard=scoreboard_settings(**defaults),
    )


def test_repo_scoreboard_starts_off(config):
    assert config.scoreboard.enabled is False
    assert config.scoreboard.interval_seconds >= 15
    assert config.scoreboard.status == "live"


def test_rank_points_then_time_and_ties_share_rank(tmp_path: Path):
    _summary(tmp_path, "Alpha", score=10, seconds=100, solved=2)
    _summary(tmp_path, "Beta", score=10, seconds=50, solved=1)
    _summary(tmp_path, "Gamma", score=12, seconds=400, solved=3, roster=("Cy",))
    payload = payload_from_standings(
        collect_standings(tmp_path),
        status="live",
        frozen=False,
        message="Finals 3 PM, Ballroom B",
        now=NOW,
    )
    assert payload["updated_at"] == "2026-10-28T19:04:00Z"
    assert payload["message"] == "Finals 3 PM, Ballroom B"
    assert [(row["rank"], row["name"], row["score"]) for row in payload["entries"]] == [
        (1, "Gamma", 12),
        (2, "Beta", 10),
        (2, "Alpha", 10),
    ]
    assert payload["entries"][1]["detail"] == "00:50 · 1 solve"
    assert payload["entries"][2]["detail"] == "01:40 · 2 solves"
    assert payload["entries"][0]["team"] == "Cy"


def test_live_checkpoint_outranks_an_older_summary(tmp_path: Path):
    _summary(tmp_path, "Orbit", score=4, seconds=30, stamp="20261026T110000Z")
    _checkpoint(tmp_path, "Orbit", score=9, remaining=125, solved=2)
    found = collect_standings(tmp_path, game_limit_seconds=1500)
    assert len(found) == 1
    assert found[0].live is True
    assert found[0].score == 9
    assert found[0].time_used_seconds == 1375
    payload = payload_from_standings(
        found, status="live", frozen=True, message="", now=NOW
    )
    assert payload["frozen"] is True
    assert payload["entries"][0]["detail"].startswith("live · 02:05 left")
    assert "2 solves" in payload["entries"][0]["detail"]


def test_summary_in_the_same_run_is_the_finished_score(tmp_path: Path):
    run = tmp_path / "Alpha" / "run"
    run.mkdir(parents=True)
    (run / "summary.json").write_text(
        json.dumps({"team": "Alpha", "score": 5, "time_used_seconds": 10}),
        encoding="utf-8",
    )
    (run / "checkpoint.json").write_text(
        json.dumps({"team_name": "Alpha", "progress": {"total_score": 99}}),
        encoding="utf-8",
    )
    found = collect_standings(tmp_path)
    assert found[0].score == 5
    assert found[0].live is False


def test_skips_archived_folders_and_broken_json(tmp_path: Path):
    hidden = tmp_path / "_archived_checkpoints" / "ghost"
    hidden.mkdir(parents=True)
    (hidden / "summary.json").write_text(
        json.dumps({"team": "Ghost", "score": 1000}),
        encoding="utf-8",
    )
    broken = tmp_path / "Broken" / "run"
    broken.mkdir(parents=True)
    (broken / "summary.json").write_text("{", encoding="utf-8")
    _summary(tmp_path, "Kept", score=3, seconds=12, solved=0)
    names = [row.name for row in collect_standings(tmp_path)]
    assert names == ["Kept"]


def test_caps_length_and_entry_count():
    standings = [
        TeamStanding(
            name=("N" * 50) if i == 200 else f"T{i:03d}",
            score=float(i),
            time_used_seconds=1,
            game_remaining=None,
            solved=0,
            live=False,
            roster=("P" * 80,),
        )
        for i in range(201)
    ]
    payload = payload_from_standings(
        standings,
        status="nope",
        frozen=False,
        message="M" * 200,
        now=NOW,
    )
    assert len(payload["entries"]) == 200
    assert payload["entries"][0]["name"] == "N" * 40
    assert len(payload["entries"][0]["team"]) == 40
    assert payload["status"] == "live"
    assert len(payload["message"]) == 140
    again = dict(payload)
    again["updated_at"] = "1999-01-01T00:00:00Z"
    assert board_signature(payload) == board_signature(again)


def test_page_escapes_names_into_text():
    standing = TeamStanding(
        name="<img src=x onerror=alert(1)>",
        score=1,
        time_used_seconds=1,
        game_remaining=None,
        solved=0,
        live=False,
        roster=(),
    )
    html = page_html(
        payload_from_standings(
            [standing], status="live", frozen=False, message="Board", now=NOW
        )
    )
    assert "<img" not in html
    assert "\\u003cimg" in html
    assert "Waiting for the first team." in html


def test_scoreboard_settings_reject_bad_values():
    with pytest.raises(ConfigError, match="id"):
        scoreboard_settings(
            enabled=True,
            board_id="",
            status="live",
            frozen=False,
            message="",
            interval_seconds=60,
        )
    with pytest.raises(ConfigError, match="status"):
        scoreboard_settings(
            enabled=False,
            board_id="demo",
            status="paused",
            frozen=False,
            message="",
            interval_seconds=60,
        )
    with pytest.raises(ConfigError, match="15"):
        scoreboard_settings(
            enabled=False,
            board_id="demo",
            status="live",
            frozen=False,
            message="",
            interval_seconds=5,
        )


def test_roundtrip_keeps_board_and_not_the_key(config, tmp_path: Path, monkeypatch):
    monkeypatch.setenv("SAINTCON_SCOREBOARD_KEY", "super-secret-token")
    updated = config.with_updates(
        scoreboard=scoreboard_settings(
            enabled=True,
            board_id="finals-a",
            status="final",
            frozen=True,
            message="Ballroom B",
            interval_seconds=30,
        )
    )
    dest = tmp_path / "out.toml"
    save_config(updated, dest)
    text = dest.read_text(encoding="utf-8")
    assert "super-secret-token" not in text
    assert "scoreboard.key" in text
    loaded = load_config(dest)
    assert loaded.scoreboard.enabled is True
    assert loaded.scoreboard.board_id == "finals-a"
    assert loaded.scoreboard.status == "final"
    assert loaded.scoreboard.frozen is True
    assert loaded.scoreboard.message == "Ballroom B"
    assert loaded.scoreboard.interval_seconds == 30


def test_api_key_env_beats_file(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("SAINTCON_SCOREBOARD_KEY", "from-env")
    key_file = tmp_path / "config" / "scoreboard.key"
    key_file.parent.mkdir()
    key_file.write_text("# comment\nfrom-file\n", encoding="utf-8")
    assert resolve_api_key(tmp_path) == "from-env"
    monkeypatch.delenv("SAINTCON_SCOREBOARD_KEY")
    assert resolve_api_key(tmp_path) == "from-file"


def test_push_sends_put_and_refuses_other_hosts():
    seen = {}

    def send(url, body, headers):
        seen["url"] = url
        seen["body"] = body
        seen["headers"] = headers
        return 200

    status = push_payload(
        BOARD_URL,
        "secret",
        {"status": "live", "entries": []},
        send=send,
    )
    assert status == 200
    assert seen["url"] == BOARD_URL
    assert seen["headers"]["Authorization"] == "Bearer secret"
    assert seen["headers"]["Content-Type"] == "application/json"
    assert json.loads(seen["body"])["entries"] == []

    def unused(url, body, headers):
        raise AssertionError("should not send")

    with pytest.raises(ScoreboardError, match="unexpected host"):
        push_payload("https://evil.example/board", "secret", {"entries": []}, send=unused)
    with pytest.raises(ScoreboardError, match="64 KB"):
        push_payload(
            BOARD_URL,
            "secret",
            {"blob": "x" * (70 * 1024)},
            send=unused,
        )


def test_push_reports_http_errors(monkeypatch):
    def fake_open(self, request, timeout=10):  # noqa: ANN001
        raise urllib.error.HTTPError(
            BOARD_URL,
            429,
            "slow down",
            Message(),
            BytesIO(b"wait"),
        )

    monkeypatch.setattr(urllib.request.OpenerDirector, "open", fake_open)
    with pytest.raises(ScoreboardError, match="429"):
        push_payload(BOARD_URL, "secret", {"entries": []})


def test_redirect_is_refused():
    with pytest.raises(ScoreboardError, match="redirect"):
        RejectRedirect().redirect_request(None, None, 302, "Found", None, "https://evil.example/")


def test_automatic_push_waits_for_a_change(config, tmp_path: Path, monkeypatch):
    monkeypatch.delenv("SAINTCON_SCOREBOARD_KEY", raising=False)
    monkeypatch.setenv("SAINTCON_SCOREBOARD_KEY", "secret")
    results = tmp_path / "results"
    _summary(results, "Cable Guy", score=10, seconds=40)
    cfg = _board_config(config, results)
    calls: list[dict] = []

    def send(url, body, headers):
        assert headers["Authorization"] == "Bearer secret"
        assert url == BOARD_URL
        calls.append(json.loads(body))
        return 204

    state = PushState()
    first = attempt_push(
        cfg, state, now=0, require_enabled=True, respect_interval=True, send=send
    )
    assert first.action == "pushed"
    assert first.status_code == 204
    second = attempt_push(
        cfg, state, now=30, require_enabled=True, respect_interval=True, send=send
    )
    assert second.action == "skipped"
    _summary(results, "Cable Guy", score=99, seconds=40)
    third = attempt_push(
        cfg, state, now=40, require_enabled=True, respect_interval=True, send=send
    )
    assert third.action == "skipped"
    fourth = attempt_push(
        cfg, state, now=60, require_enabled=True, respect_interval=True, send=send
    )
    assert fourth.action == "pushed"
    assert calls[-1]["entries"][0]["score"] == 99
    assert len(calls) == 2


def test_disabled_game_does_not_push_until_asked(config, tmp_path: Path, monkeypatch):
    monkeypatch.setenv("SAINTCON_SCOREBOARD_KEY", "secret")
    results = tmp_path / "results"
    _summary(results, "Quiet", score=1, seconds=5, solved=0)
    cfg = _board_config(config, results, enabled=False)
    calls: list[str] = []

    def send(url, body, headers):
        calls.append(url)
        return 200

    assert (
        attempt_push(
            cfg, PushState(), now=0, require_enabled=True, respect_interval=True, send=send
        ).action
        == "disabled"
    )
    assert push_once(cfg, send=send) == 0
    assert calls == [BOARD_URL]


def test_missing_key_is_announced_once(config, tmp_path: Path, monkeypatch):
    monkeypatch.delenv("SAINTCON_SCOREBOARD_KEY", raising=False)
    results = tmp_path / "results"
    cfg = _board_config(config, results).with_updates(root_dir=tmp_path)
    state = PushState()
    first = attempt_push(
        cfg, state, now=0, require_enabled=True, respect_interval=True, send=lambda *a: 200
    )
    second = attempt_push(
        cfg, state, now=5, require_enabled=True, respect_interval=True, send=lambda *a: 200
    )
    assert first.action == "no_key"
    assert first.announce is True
    assert second.announce is False


def test_local_display_serves_standings(config, tmp_path: Path):
    results = tmp_path / "results"
    _summary(results, "Fast Hands", score=41.2, seconds=41.2, solved=3, roster=("Ada",))
    cfg = _board_config(config, results, message="Finals 3 PM, Ballroom B")
    httpd = make_server(cfg, "127.0.0.1", 0, reload=False)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/board.json") as resp:
            payload = json.load(resp)
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/") as resp:
            html = resp.read().decode("utf-8")
    finally:
        httpd.shutdown()
        httpd.server_close()
    assert payload["entries"][0]["name"] == "Fast Hands"
    assert payload["entries"][0]["score"] == 41.2
    assert "Finals 3 PM, Ballroom B" in html
    assert "Fast Hands" in html


def test_build_board_uses_config_message(config, tmp_path: Path):
    results = tmp_path / "results"
    cfg = _board_config(config, results, status="upcoming", frozen=True)
    payload = build_board(cfg, now=NOW)
    assert payload["status"] == "upcoming"
    assert payload["frozen"] is True
    assert payload["entries"] == []


def test_cli_board_show_and_usage(config, tmp_path: Path, monkeypatch, capsys):
    results = tmp_path / "results"
    _summary(results, "Cable Guy", score=44, seconds=44, solved=1, roster=("Bea",))
    cfg = _board_config(config, results, enabled=False)
    conf = tmp_path / "config.toml"
    save_config(cfg, conf)
    monkeypatch.setattr("baton_relay.cli._default_config_path", lambda: conf)
    assert main(["board", "show"]) == 0
    shown = json.loads(capsys.readouterr().out)
    assert shown["entries"][0]["name"] == "Cable Guy"
    assert main(["board"]) == 2
    assert "projector page" in capsys.readouterr().err


def test_peer_url_must_be_a_host_and_port():
    with pytest.raises(ConfigError, match="peers"):
        scoreboard_settings(
            enabled=False,
            board_id="",
            status="live",
            frozen=False,
            message="",
            interval_seconds=60,
            peers=["file:///results"],
        )
    ok = scoreboard_settings(
        enabled=False,
        board_id="",
        status="live",
        frozen=False,
        message="",
        interval_seconds=60,
        peers=["http://10.1.2.3:8765/"],
        machine="lane 2",
    )
    assert ok.peers == ("http://10.1.2.3:8765",)
    assert ok.machine == "lane 2"


def test_two_machines_merge_and_keep_local_standings_separate(config, tmp_path: Path):
    results_a = tmp_path / "results-a"
    results_b = tmp_path / "results-b"
    _summary(results_a, "Alpha", score=10, seconds=30, solved=1, roster=("Ann",))
    _summary(results_b, "Beta", score=20, seconds=40, solved=2, roster=("Bea",))
    cfg_b = _board_config(config, results_b, enabled=False).with_updates(root_dir=tmp_path / "b")
    server_b = make_server(cfg_b, "127.0.0.1", 0, reload=False)
    thread_b = threading.Thread(target=server_b.serve_forever, daemon=True)
    thread_b.start()
    server_a = None
    try:
        port_b = server_b.server_address[1]
        cfg_a = _board_config(
            config,
            results_a,
            enabled=False,
            peers=[f"http://127.0.0.1:{port_b}"],
        ).with_updates(root_dir=tmp_path / "a")
        server_a = make_server(cfg_a, "127.0.0.1", 0, reload=False)
        thread_a = threading.Thread(target=server_a.serve_forever, daemon=True)
        thread_a.start()
        port_a = server_a.server_address[1]
        with urllib.request.urlopen(f"http://127.0.0.1:{port_a}/standings.json") as resp:
            local = json.load(resp)
        with urllib.request.urlopen(f"http://127.0.0.1:{port_a}/board.json") as resp:
            board = json.load(resp)
        with urllib.request.urlopen(f"http://127.0.0.1:{port_a}/") as resp:
            html = resp.read().decode("utf-8")
    finally:
        server_b.shutdown()
        server_b.server_close()
        if server_a is not None:
            server_a.shutdown()
            server_a.server_close()
    assert [row["name"] for row in local["standings"]] == ["Alpha"]
    assert [row["name"] for row in board["entries"]] == ["Beta", "Alpha"]
    assert "Beta" in html and "Alpha" in html


def test_dead_peer_keeps_the_last_standings(config, tmp_path: Path):
    results = tmp_path / "results"
    _summary(results, "Local", score=3, seconds=10, solved=0, roster=("Lou",))
    cfg = _board_config(
        config,
        results,
        enabled=False,
        peers=["http://10.0.0.9:8765"],
    ).with_updates(root_dir=tmp_path / "root")
    calls = {"n": 0}

    def fetch(url, timeout):
        calls["n"] += 1
        if calls["n"] > 1:
            raise OSError("down")
        return {
            "machine": "other",
            "standings": [
                {
                    "name": "Remote",
                    "score": 8,
                    "solved": 1,
                    "live": False,
                    "time_used_seconds": 12,
                    "roster": ["Sam"],
                }
            ],
        }

    first = build_synced_board(cfg, fetch=fetch, now=NOW)
    second = build_synced_board(cfg, fetch=fetch, now=NOW)
    assert {row["name"] for row in first["entries"]} == {"Local", "Remote"}
    assert {row["name"] for row in second["entries"]} == {"Local", "Remote"}


def test_stale_peer_cache_drops_off(config, tmp_path: Path):
    results = tmp_path / "results"
    _summary(results, "Local", score=3, seconds=10, solved=0, roster=("Lou",))
    cfg = _board_config(
        config,
        results,
        enabled=False,
        peers=["http://10.0.0.9:8765"],
    ).with_updates(root_dir=tmp_path / "root")
    old = datetime(2020, 1, 1, tzinfo=timezone.utc)

    def fetch(url, timeout):
        return {"machine": "other", "standings": [{"name": "Remote", "score": 8, "solved": 0, "live": False}]}

    build_synced_board(cfg, fetch=fetch, now=old)

    def down(url, timeout):
        raise OSError("down")

    payload = build_synced_board(cfg, fetch=down, now=NOW)
    assert [row["name"] for row in payload["entries"]] == ["Local"]


def test_same_team_on_two_machines_keeps_the_higher_score(config, tmp_path: Path):
    results = tmp_path / "results"
    _summary(results, "Alpha", score=4, seconds=10, solved=1, roster=("Ann",))
    cfg = _board_config(
        config,
        results,
        enabled=False,
        peers=["http://10.0.0.9:8765"],
    ).with_updates(root_dir=tmp_path / "root")

    def fetch(url, timeout):
        return {
            "machine": "other",
            "standings": [{"name": "Alpha", "score": 9, "solved": 2, "live": True, "game_remaining": 30}],
        }

    payload = build_synced_board(cfg, fetch=fetch, now=NOW)
    assert len(payload["entries"]) == 1
    assert payload["entries"][0]["score"] == 9
    assert payload["entries"][0]["detail"].startswith("live")
