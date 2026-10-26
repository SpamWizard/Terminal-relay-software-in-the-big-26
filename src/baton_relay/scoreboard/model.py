"""Turn results/ into the JSON body SaintCon expects.

Points rank a team. Less time used orders teams that have the same score,
and those teams share a rank. A checkpoint with no summary is a live run.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from baton_relay.config import SCOREBOARD_STATUSES, AppConfig
from baton_relay.duration import format_duration

NAME_MAX = 40
DETAIL_MAX = 60
TEAM_MAX = 40
MESSAGE_MAX = 140
ENTRY_MAX = 200


@dataclass(frozen=True)
class TeamStanding:
    name: str
    score: float
    time_used_seconds: float | None
    game_remaining: float | None
    solved: int
    live: bool
    roster: tuple[str, ...]


def collect_standings(
    results_dir: Path,
    *,
    game_limit_seconds: float | None = None,
) -> list[TeamStanding]:
    """One standing per team folder. A live checkpoint wins over an old summary."""
    if not results_dir.is_dir():
        return []
    found: list[TeamStanding] = []
    try:
        children = list(results_dir.iterdir())
    except OSError:
        return []
    for team_dir in children:
        if not team_dir.is_dir() or team_dir.name.startswith((".", "_")):
            continue
        standing = _standing_for_team(team_dir, game_limit_seconds)
        if standing is not None and standing.name.strip():
            found.append(standing)
    return _dedupe(found)


def build_board(config: AppConfig, *, now: datetime | None = None) -> dict[str, Any]:
    standings = collect_standings(
        config.paths.results_dir,
        game_limit_seconds=float(config.timers.game_seconds),
    )
    board = config.scoreboard
    return payload_from_standings(
        standings,
        status=board.status,
        frozen=board.frozen,
        message=board.message,
        now=now,
    )


def payload_from_standings(
    standings: list[TeamStanding],
    *,
    status: str,
    frozen: bool,
    message: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    for rank, standing in rank_standings(standings):
        name = clip(standing.name, NAME_MAX)
        if not name:
            continue
        entry: dict[str, Any] = {
            "rank": rank,
            "name": name,
            "score": json_number(standing.score),
        }
        detail = clip(_detail(standing), DETAIL_MAX)
        if detail:
            entry["detail"] = detail
        roster = clip(", ".join(standing.roster), TEAM_MAX)
        if roster:
            entry["team"] = roster
        entries.append(entry)
    board_status = status if status in SCOREBOARD_STATUSES else "live"
    return {
        "status": board_status,
        "frozen": bool(frozen),
        "updated_at": utc_stamp(now),
        "message": clip(message, MESSAGE_MAX),
        "entries": entries,
    }


def rank_standings(standings: list[TeamStanding]) -> list[tuple[int, TeamStanding]]:
    """Higher score first. Same score shares a rank; faster time is listed first."""
    ordered = sorted(standings, key=_sort_key)
    ranked: list[tuple[int, TeamStanding]] = []
    last_score: float | None = None
    rank = 0
    for index, standing in enumerate(ordered, start=1):
        score = round(standing.score, 3)
        if last_score is None or score != last_score:
            rank = index
            last_score = score
        ranked.append((rank, standing))
    return ranked[:ENTRY_MAX]


def board_signature(payload: dict[str, Any]) -> str:
    """Identity of a board, ignoring updated_at so a quiet room does not re-push."""
    slim = {
        "status": payload.get("status"),
        "frozen": payload.get("frozen"),
        "message": payload.get("message"),
        "entries": payload.get("entries"),
    }
    return json.dumps(slim, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def clip(text: str, limit: int) -> str:
    cleaned = "".join(ch if ch >= " " else " " for ch in str(text))
    return " ".join(cleaned.split())[:limit]


def json_number(value: float) -> int | float:
    rounded = round(float(value), 3)
    nearest = round(rounded)
    if abs(rounded - nearest) < 1e-9:
        return int(nearest)
    return rounded


def utc_stamp(now: datetime | None = None) -> str:
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    moment = moment.astimezone(timezone.utc).replace(microsecond=0)
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def _sort_key(standing: TeamStanding) -> tuple[float, float, int, str]:
    elapsed = standing.time_used_seconds
    if elapsed is None:
        elapsed = float("inf")
    return (
        -round(standing.score, 3),
        elapsed,
        1 if standing.live else 0,
        standing.name.casefold(),
    )


def _detail(standing: TeamStanding) -> str:
    bits: list[str] = []
    if standing.live:
        bits.append("live")
        if standing.game_remaining is not None:
            bits.append(f"{format_duration(standing.game_remaining)} left")
    elif standing.time_used_seconds is not None:
        bits.append(format_duration(standing.time_used_seconds))
    if standing.solved:
        word = "solve" if standing.solved == 1 else "solves"
        bits.append(f"{standing.solved} {word}")
    return " · ".join(bits)


def _dedupe(standings: list[TeamStanding]) -> list[TeamStanding]:
    best: dict[str, TeamStanding] = {}
    for standing in standings:
        key = standing.name.casefold()
        current = best.get(key)
        if current is None or _better(standing, current):
            best[key] = standing
    return list(best.values())


def _better(challenger: TeamStanding, incumbent: TeamStanding) -> bool:
    left = round(challenger.score, 3)
    right = round(incumbent.score, 3)
    if left != right:
        return left > right
    if challenger.live != incumbent.live:
        return challenger.live
    left_time = challenger.time_used_seconds
    right_time = incumbent.time_used_seconds
    if left_time is None:
        return False
    if right_time is None:
        return True
    return left_time < right_time


def _standing_for_team(team_dir: Path, game_limit: float | None) -> TeamStanding | None:
    live: list[tuple[float, Path]] = []
    finished: list[Path] = []
    try:
        runs = list(team_dir.iterdir())
    except OSError:
        return None
    for run in runs:
        if not run.is_dir():
            continue
        summary = run / "summary.json"
        checkpoint = run / "checkpoint.json"
        try:
            has_summary = summary.is_file()
            has_checkpoint = checkpoint.is_file()
        except OSError:
            continue
        if has_checkpoint and not has_summary:
            try:
                live.append((checkpoint.stat().st_mtime, checkpoint))
            except OSError:
                continue
        elif has_summary:
            finished.append(summary)
    if live:
        live.sort(key=lambda item: item[0])
        return _from_checkpoint(live[-1][1], team_dir.name, game_limit)
    best: TeamStanding | None = None
    for path in finished:
        standing = _from_summary(path, team_dir.name)
        if standing is None:
            continue
        if best is None or _better(standing, best):
            best = standing
    return best


def _from_summary(path: Path, folder_name: str) -> TeamStanding | None:
    data = _load_json(path)
    if data is None:
        return None
    score = _number(data.get("score"))
    if score is None:
        return None
    name = str(data.get("team") or "").strip() or folder_name
    return TeamStanding(
        name=name,
        score=score,
        time_used_seconds=_number(data.get("time_used_seconds")),
        game_remaining=_number(data.get("game_remaining")),
        solved=_solved_rows(data.get("counted_answers")),
        live=False,
        roster=_roster(data.get("roster")),
    )


def _from_checkpoint(
    path: Path,
    folder_name: str,
    game_limit: float | None,
) -> TeamStanding | None:
    data = _load_json(path)
    if data is None:
        return None
    progress = data.get("progress") if isinstance(data.get("progress"), dict) else {}
    score = _number(progress.get("total_score"))
    if score is None:
        score = 0.0
    remaining = _number(data.get("game_remaining"))
    used: float | None = None
    if game_limit is not None and remaining is not None:
        used = round(max(0.0, float(game_limit) - remaining), 2)
    name = str(data.get("team_name") or "").strip() or folder_name
    return TeamStanding(
        name=name,
        score=score,
        time_used_seconds=used,
        game_remaining=remaining,
        solved=_solved_map(progress.get("answered")),
        live=True,
        roster=_roster(data.get("roster")),
    )


def _solved_rows(rows: Any) -> int:
    if not isinstance(rows, list):
        return 0
    return sum(1 for row in rows if isinstance(row, dict) and row.get("correct") is True)


def _solved_map(answered: Any) -> int:
    if not isinstance(answered, dict):
        return 0
    return sum(
        1
        for value in answered.values()
        if isinstance(value, dict) and value.get("correct") is True
    )


def _roster(raw: Any) -> tuple[str, ...]:
    if not isinstance(raw, list):
        return ()
    names: list[str] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name") or "").strip()
        if name:
            names.append(name)
    return tuple(names)


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return None
    if not isinstance(data, dict):
        return None
    return data


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None
