"""PUT the whole board to saintcon.org. The API key never goes anywhere else."""

from __future__ import annotations

import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from baton_relay.config import (
    SCOREBOARD_ID_RE,
    SCOREBOARD_MIN_INTERVAL_SECONDS,
    AppConfig,
    ConfigError,
    load_config,
)
from baton_relay.scoreboard.model import board_signature
from baton_relay.scoreboard.sync import build_synced_board, lan_ip

BODY_MAX = 64 * 1024
_HOST = "https://saintcon.org/api/scoreboards/"
Send = Callable[[str, bytes, dict[str, str]], int]


class ScoreboardError(Exception):
    """The board was not accepted. The message never includes the API key."""


class RejectRedirect(urllib.request.HTTPRedirectHandler):
    """A redirect would send the bearer token to whatever host came back."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        raise ScoreboardError(f"refusing redirect ({code}) from the scoreboard host")


@dataclass
class PushState:
    ever_pushed: bool = False
    last_monotonic: float = 0.0
    signature: str = ""
    warned: str = ""


@dataclass(frozen=True)
class PushAttempt:
    action: str
    detail: str = ""
    status_code: int | None = None
    announce: bool = False


def resolve_api_key(root_dir: Path) -> str:
    """Environment wins. Otherwise the first real line of config/scoreboard.key."""
    env = os.environ.get("SAINTCON_SCOREBOARD_KEY", "").strip()
    if env:
        return env
    path = Path(root_dir) / "config" / "scoreboard.key"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return ""
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            return line
    return ""


def endpoint(board_id: str) -> str:
    if SCOREBOARD_ID_RE.fullmatch(board_id or "") is None:
        raise ScoreboardError("scoreboard id is missing or invalid")
    return f"{_HOST}{board_id}"


def should_push(*, changed: bool, elapsed: float, interval: float, ever_pushed: bool) -> bool:
    if not ever_pushed:
        return True
    if not changed:
        return False
    wait = max(float(SCOREBOARD_MIN_INTERVAL_SECONDS), float(interval))
    return elapsed >= wait


def push_payload(
    url: str,
    key: str,
    payload: dict[str, Any],
    *,
    timeout: float = 10.0,
    send: Send | None = None,
) -> int:
    if not str(key).strip():
        raise ScoreboardError("missing API key")
    if not url.startswith(_HOST):
        raise ScoreboardError("refusing to send the scoreboard key to an unexpected host")
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(body) > BODY_MAX:
        raise ScoreboardError(f"board JSON is {len(body)} bytes; limit is 64 KB")
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "User-Agent": "terminal-relay",
    }
    if send is not None:
        return int(send(url, body, headers))
    request = urllib.request.Request(url, data=body, method="PUT", headers=headers)
    opener = urllib.request.build_opener(RejectRedirect)
    try:
        with opener.open(request, timeout=timeout) as response:
            return int(response.status)
    except ScoreboardError:
        raise
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", errors="replace")
        except OSError:
            detail = ""
        detail = " ".join(detail.split())[:240]
        message = f"HTTP {exc.code}"
        if detail:
            message = f"{message}: {detail}"
        raise ScoreboardError(message) from exc
    except urllib.error.URLError as exc:
        raise ScoreboardError(f"could not reach the scoreboard: {exc.reason}") from exc
    except TimeoutError as exc:
        raise ScoreboardError("scoreboard request timed out") from exc


def attempt_push(
    config: AppConfig,
    state: PushState,
    *,
    now: float,
    require_enabled: bool,
    respect_interval: bool,
    send: Send | None = None,
    key: str | None = None,
) -> PushAttempt:
    """Build the board and maybe PUT it. `state` remembers the last success."""
    board = config.scoreboard
    if require_enabled and not board.enabled:
        state.ever_pushed = False
        state.signature = ""
        state.warned = ""
        return PushAttempt("disabled")
    if not board.board_id:
        return _warn(state, "no_id", "scoreboard id is empty")

    payload = build_synced_board(config)
    signature = board_signature(payload)
    elapsed = now - state.last_monotonic if state.ever_pushed else 0.0
    if respect_interval and not should_push(
        changed=signature != state.signature,
        elapsed=elapsed,
        interval=board.interval_seconds,
        ever_pushed=state.ever_pushed,
    ):
        return PushAttempt("skipped")

    token = resolve_api_key(config.root_dir) if key is None else key.strip()
    if not token:
        return _warn(
            state,
            "no_key",
            "no API key",
        )

    url = endpoint(board.board_id)
    try:
        status = push_payload(url, token, payload, send=send)
    except ScoreboardError as exc:
        state.ever_pushed = True
        state.last_monotonic = now
        return PushAttempt("error", str(exc), announce=True)
    state.ever_pushed = True
    state.last_monotonic = now
    state.signature = signature
    state.warned = ""
    count = len(payload.get("entries") or [])
    noun = "team" if count == 1 else "teams"
    return PushAttempt("pushed", f"{count} {noun}", status_code=status, announce=True)


def push_once(config: AppConfig, *, send: Send | None = None) -> int:
    state = PushState()
    attempt = attempt_push(
        config,
        state,
        now=time.monotonic(),
        require_enabled=False,
        respect_interval=False,
        send=send,
    )
    announce(attempt)
    return 0 if attempt.action == "pushed" else 1


def watch(config: AppConfig) -> int:
    print(
        "Pushing when scores change. Leave the in-game scoreboard switch off "
        "while this is running, or both will push.",
        flush=True,
    )
    state = PushState()
    while True:
        try:
            current = load_config(config.config_path)
        except ConfigError as exc:
            print(f"Scoreboard config error: {exc}", file=sys.stderr, flush=True)
            current = config
        try:
            attempt = attempt_push(
                current,
                state,
                now=time.monotonic(),
                require_enabled=False,
                respect_interval=True,
            )
            announce(attempt)
        except OSError as exc:
            print(f"Scoreboard push failed: {exc}", file=sys.stderr, flush=True)
        time.sleep(5)


def announce(attempt: PushAttempt) -> None:
    if not attempt.announce:
        return
    if attempt.action == "pushed":
        print(
            f"Scoreboard updated ({attempt.status_code}): {attempt.detail}",
            flush=True,
        )
        return
    if attempt.action == "no_key":
        print(
            "Scoreboard is on, but no API key was found. "
            "Set SAINTCON_SCOREBOARD_KEY or create config/scoreboard.key.",
            file=sys.stderr,
            flush=True,
        )
        return
    if attempt.action == "error":
        print(f"Scoreboard push failed: {attempt.detail}", file=sys.stderr, flush=True)


def _warn(state: PushState, code: str, detail: str) -> PushAttempt:
    announce_now = state.warned != code
    state.warned = code
    action = "no_key" if code == "no_key" else "error"
    return PushAttempt(action, detail, announce=announce_now)


class ScoreboardPusher:
    """Background push for the game window. Wakes every few seconds, pushes rarely."""

    def __init__(self, config: AppConfig) -> None:
        self._path = config.config_path
        self._fallback = config
        self._state = PushState()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._announced = False
        self._httpd: threading.Thread | None = None
        self._server = None
        self._listen_failed = False

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop,
            name="scoreboard-push",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        server = self._server
        if server is not None:
            server.shutdown()
            server.server_close()
            self._server = None

    def _load(self) -> AppConfig:
        try:
            return load_config(self._path)
        except (ConfigError, OSError):
            return self._fallback

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                config = self._load()
                self._ensure_listener(config)
                self._note(config)
                attempt = attempt_push(
                    config,
                    self._state,
                    now=time.monotonic(),
                    require_enabled=True,
                    respect_interval=True,
                )
                announce(attempt)
            except Exception as exc:  # noqa: BLE001 — the game keeps running
                print(f"Scoreboard push failed: {exc}", file=sys.stderr, flush=True)
            self._stop.wait(5.0)

    def _note(self, config: AppConfig) -> None:
        if not config.scoreboard.enabled:
            self._announced = False
            return
        if self._announced:
            return
        wait = max(SCOREBOARD_MIN_INTERVAL_SECONDS, config.scoreboard.interval_seconds)
        ident = config.scoreboard.board_id or "(no id yet)"
        peers = ", ".join(config.scoreboard.peers)
        extra = f" Peers: {peers}." if peers else ""
        print(
            f"Scoreboard: {ident} — pushing when scores change (at most every {wait}s). "
            f"Room display: http://127.0.0.1:{config.scoreboard.listen_port}.{extra}",
            flush=True,
        )
        self._announced = True

    def _ensure_listener(self, config: AppConfig) -> None:
        board = config.scoreboard
        if self._server is not None:
            return
        if not board.enabled and not board.peers:
            return
        from baton_relay.scoreboard.display import make_server

        try:
            server = make_server(config, board.listen_host, board.listen_port)
        except OSError as exc:
            if not self._listen_failed:
                print(f"Scoreboard sync is not listening: {exc}", file=sys.stderr, flush=True)
                self._listen_failed = True
            return
        self._server = server
        thread = threading.Thread(
            target=server.serve_forever,
            name="scoreboard-listen",
            daemon=True,
        )
        thread.start()
        self._httpd = thread
        port = server.server_address[1]
        print(
            f"Scoreboard sync: http://{board.listen_host}:{port}/standings.json",
            flush=True,
        )
        address = lan_ip()
        if address and board.listen_host in ("0.0.0.0", "::"):
            print(
                f"On the other machines set peers = [\"http://{address}:{port}\"]",
                flush=True,
            )
