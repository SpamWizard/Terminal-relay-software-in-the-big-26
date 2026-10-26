"""Share standings between game PCs, then push one combined board.

SaintCon keeps only the latest PUT. Each machine therefore publishes its own
teams at /standings.json and pulls the other machines before it builds the
board. The public /board.json is the merge. Standings are scores and names,
not answer keys.
"""

from __future__ import annotations

import hashlib
import json
import socket
import sys
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from baton_relay.config import AppConfig
from baton_relay.scoreboard.model import (
    TeamStanding,
    build_board,
    collect_standings,
    standing_from_dict,
    standing_to_dict,
    utc_stamp,
)

MAX_PEER_BYTES = 256 * 1024
PEER_CACHE_HOURS = 8
Fetch = Callable[[str, float], dict[str, Any]]

_peer_errors: dict[str, str] = {}


def peer_cache_dir(config: AppConfig) -> Path:
    return config.root_dir / "data" / "scoreboard-peers"


def machine_label(config: AppConfig) -> str:
    name = config.scoreboard.machine.strip()
    if name:
        return name[:40]
    try:
        return socket.gethostname()[:40] or "machine"
    except OSError:
        return "machine"


def local_standings_payload(config: AppConfig, *, now: datetime | None = None) -> dict[str, Any]:
    """This PC only. Peers must fetch this, never the already-merged board."""
    standings = collect_standings(
        config.paths.results_dir,
        game_limit_seconds=float(config.timers.game_seconds),
    )
    return {
        "machine": machine_label(config),
        "updated_at": utc_stamp(now),
        "standings": [standing_to_dict(item) for item in standings[:200]],
    }


def build_synced_board(
    config: AppConfig,
    *,
    now: datetime | None = None,
    fetch: Fetch | None = None,
    timeout: float = 2.0,
) -> dict[str, Any]:
    extra: list[TeamStanding] = []
    if config.scoreboard.peers:
        sync_peers(config, fetch=fetch, timeout=timeout, now=now)
        extra = load_peer_standings(config, now=now)
    return build_board(config, now=now, also=extra)


def sync_peers(
    config: AppConfig,
    *,
    fetch: Fetch | None = None,
    timeout: float = 2.0,
    now: datetime | None = None,
) -> list[str]:
    """Refresh the on-disk copy of each peer. A failure keeps the previous copy."""
    moment = now or datetime.now(timezone.utc)
    getter = fetch or _fetch_standings
    problems: list[str] = []
    cache_dir = peer_cache_dir(config)
    for peer in config.scoreboard.peers:
        try:
            payload = getter(peer, timeout)
        except (OSError, json.JSONDecodeError, UnicodeError, TimeoutError, ValueError) as exc:
            message = f"{peer}: {exc}"
            problems.append(message)
            _announce_peer(peer, message)
            continue
        if not isinstance(payload, dict):
            message = f"{peer}: standings were not a JSON object"
            problems.append(message)
            _announce_peer(peer, message)
            continue
        _write_cache(cache_dir, peer, payload, moment)
        _clear_peer_warning(peer)
    return problems


def load_peer_standings(
    config: AppConfig,
    *,
    now: datetime | None = None,
) -> list[TeamStanding]:
    cache_dir = peer_cache_dir(config)
    if not cache_dir.is_dir():
        return []
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    cutoff = moment.astimezone(timezone.utc) - timedelta(hours=PEER_CACHE_HOURS)
    found: list[TeamStanding] = []
    try:
        files = list(cache_dir.glob("*.json"))
    except OSError:
        return []
    for path in files:
        payload = _read_cache(path, cutoff)
        if payload is None:
            continue
        rows = payload.get("standings")
        if not isinstance(rows, list):
            continue
        for row in rows[:200]:
            standing = standing_from_dict(row)
            if standing is not None:
                found.append(standing)
    return found


def lan_ip() -> str:
    """Best-effort address to print for the other PC. Empty when it can't be known."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        address = sock.getsockname()[0]
    except OSError:
        return ""
    finally:
        sock.close()
    if not address or address.startswith("127."):
        return ""
    return address


def _fetch_standings(url: str, timeout: float) -> dict[str, Any]:
    target = url.rstrip("/") + "/standings.json"
    request = urllib.request.Request(
        target,
        headers={"Accept": "application/json", "User-Agent": "terminal-relay"},
    )
    opener = urllib.request.build_opener(_NoRedirect())
    try:
        with opener.open(request, timeout=timeout) as response:
            raw = response.read(MAX_PEER_BYTES + 1)
    except urllib.error.HTTPError as exc:
        raise OSError(f"HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise OSError(str(exc.reason)) from exc
    if len(raw) > MAX_PEER_BYTES:
        raise OSError("peer standings are too large")
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise OSError("peer standings were not a JSON object")
    return data


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        raise OSError(f"peer redirected ({code})")


def _write_cache(cache_dir: Path, peer: str, payload: dict[str, Any], moment: datetime) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = _cache_path(cache_dir, peer)
    body = {
        "peer": peer,
        "fetched_at": utc_stamp(moment),
        "payload": payload,
    }
    text = json.dumps(body, ensure_ascii=False)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def _read_cache(path: Path, cutoff: datetime) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return None
    if not isinstance(data, dict):
        return None
    fetched = _parse_stamp(str(data.get("fetched_at") or ""))
    if fetched is None or fetched < cutoff:
        return None
    payload = data.get("payload")
    if not isinstance(payload, dict):
        return None
    return payload


def _cache_path(cache_dir: Path, peer: str) -> Path:
    digest = hashlib.sha256(peer.encode("utf-8")).hexdigest()[:12]
    safe = "".join(ch if ch.isalnum() else "_" for ch in peer)[:40]
    return cache_dir / f"{safe}-{digest}.json"


def _parse_stamp(value: str) -> datetime | None:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def _announce_peer(peer: str, message: str) -> None:
    if _peer_errors.get(peer) == message:
        return
    _peer_errors[peer] = message
    print(f"Scoreboard peer unavailable: {message}", file=sys.stderr, flush=True)


def _clear_peer_warning(peer: str) -> None:
    if peer not in _peer_errors:
        return
    _peer_errors.pop(peer, None)
    print(f"Scoreboard peer back: {peer}", flush=True)
