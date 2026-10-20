"""Append-only JSONL event log and end-of-game summary."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


from baton_relay.duration import format_duration


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def team_slug(team_name: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in team_name.strip()) or "team"


class EventLog:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.touch(exist_ok=True)

    def emit(self, event: str, **payload: Any) -> None:
        record = {"ts": _utc_now(), "event": event, **payload}
        line = json.dumps(record, ensure_ascii=False, default=str)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
            fh.flush()

    def write_summary(self, summary_path: Path, summary: dict[str, Any]) -> None:
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary = {"ts": _utc_now(), **summary}
        summary_path.write_text(
            json.dumps(summary, indent=2, ensure_ascii=False, default=str) + "\n",
            encoding="utf-8",
        )


def new_run_dir(results_dir: Path, team_name: str) -> Path:
    safe = team_slug(team_name)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = results_dir / safe / stamp
    path.mkdir(parents=True, exist_ok=True)
    return path


def find_team_folder(results_dir: Path, team_name: str) -> Path | None:
    """Return the results folder for this team name, if any (case-insensitive slug)."""
    if not results_dir.is_dir():
        return None
    want = team_slug(team_name).casefold()
    for child in results_dir.iterdir():
        if child.is_dir() and not child.name.startswith("_") and child.name.casefold() == want:
            return child
    return None


def _events_nonempty(events_path: Path) -> bool:
    """True when the log has at least one record. A touched empty file does not count."""
    if not events_path.is_file():
        return False
    try:
        with events_path.open(encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    return True
    except OSError:
        return False
    return False


def _events_has_game_ended(events_path: Path) -> bool:
    if not events_path.is_file():
        return False
    try:
        with events_path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("event") == "game_ended":
                    return True
    except OSError:
        return False
    return False


def _roster_names_from_run(run_dir: Path) -> list[str]:
    ckpt = run_dir / "checkpoint.json"
    if ckpt.is_file():
        try:
            data = json.loads(ckpt.read_text(encoding="utf-8"))
            roster = data.get("roster") or []
            names = [
                str(e.get("name", "")).strip()
                for e in roster
                if isinstance(e, dict) and str(e.get("name", "")).strip()
            ]
            if names:
                return names
        except (OSError, json.JSONDecodeError, TypeError):
            pass
    events = run_dir / "events.jsonl"
    if events.is_file():
        try:
            with events.open(encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if rec.get("event") == "game_started":
                        roster = rec.get("roster") or []
                        return [
                            str(e.get("name", "")).strip()
                            for e in roster
                            if isinstance(e, dict) and str(e.get("name", "")).strip()
                        ]
        except OSError:
            pass
    return []


@dataclass(frozen=True)
class PriorTeamRun:
    run_dir: Path
    finished: bool
    has_checkpoint: bool
    roster_names: tuple[str, ...]


def list_team_runs(results_dir: Path, team_name: str) -> list[PriorTeamRun]:
    folder = find_team_folder(results_dir, team_name)
    if folder is None:
        return []
    runs: list[PriorTeamRun] = []
    for child in sorted(folder.iterdir()):
        if not child.is_dir():
            continue
        events_path = child / "events.jsonl"
        finished = (child / "summary.json").is_file() or _events_has_game_ended(
            events_path
        )
        has_ckpt = (child / "checkpoint.json").is_file()
        # Ignore empty folders and the empty events file EventLog creates on open.
        # Those are aborted starts, not a team that already played.
        if not _events_nonempty(events_path) and not has_ckpt and not finished:
            continue
        runs.append(
            PriorTeamRun(
                run_dir=child,
                finished=finished,
                has_checkpoint=has_ckpt,
                roster_names=tuple(_roster_names_from_run(child)),
            )
        )
    return runs


def find_resumable_run(results_dir: Path, team_name: str) -> PriorTeamRun | None:
    """Latest unfinished run that has a checkpoint (most recent stamp wins)."""
    unfinished = [
        r for r in list_team_runs(results_dir, team_name) if not r.finished and r.has_checkpoint
    ]
    if not unfinished:
        # Still treat unfinished-without-checkpoint as a name collision, but not resumable
        return None
    return unfinished[-1]


def team_name_taken(results_dir: Path, team_name: str) -> bool:
    """True when this name already has a real run, not just an empty folder."""
    return bool(list_team_runs(results_dir, team_name))


def read_events(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    out: list[dict[str, Any]] = []
    try:
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(rec, dict):
                    out.append(rec)
    except OSError:
        return out
    return out


_ATTEMPT_KEYS = (
    "local_time",
    "time_used",
    "time_used_seconds",
    "player_number",
    "player_name",
    "set_id",
    "set_title",
    "question_id",
    "question_type",
    "question_prompt",
    "question_points",
    "answer",
    "answer_text",
    "expected_text",
    "correct",
    "partial",
    "redo",
    "skipped",
    "points",
    "max_points",
    "total_score",
    "feedback",
    "organizer",
    "phase",
)


def _attempt_row(event: dict[str, Any]) -> dict[str, Any]:
    kind = "skip" if event.get("event") == "skip" else "answer"
    row: dict[str, Any] = {"kind": kind}
    for key in _ATTEMPT_KEYS:
        if key in event:
            row[key] = event[key]
    if kind == "skip":
        row.setdefault("skipped", True)
        row.setdefault("points", 0)
        row.setdefault("correct", False)
    return row


def score_sheet(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Everything needed to score a finished run, taken from the event log."""
    started = next((e for e in events if e.get("event") == "game_started"), {})
    ended = next((e for e in reversed(events) if e.get("event") == "game_ended"), {})
    roster = started.get("roster") if isinstance(started.get("roster"), list) else []
    attempts = [_attempt_row(e) for e in events if e.get("event") in ("answer", "skip")]

    counted: dict[str, dict[str, Any]] = {}
    for row in attempts:
        if row.get("kind") != "answer":
            continue
        qid = str(row.get("question_id") or "")
        if qid:
            counted[qid] = row

    players: dict[Any, dict[str, Any]] = {}
    for person in roster:
        if not isinstance(person, dict):
            continue
        num = person.get("player_number")
        players[num] = {
            "player_number": num,
            "name": person.get("name") or "",
            "points": 0.0,
        }
    for row in counted.values():
        num = row.get("player_number")
        pts = float(row.get("points") or 0)
        bucket = players.get(num)
        if bucket is None:
            bucket = {
                "player_number": num,
                "name": row.get("player_name") or "",
                "points": 0.0,
            }
            players[num] = bucket
        bucket["points"] = round(float(bucket["points"]) + pts, 3)

    limit = ended.get("game_limit_seconds")
    remaining = ended.get("game_remaining")
    used = ended.get("time_used_seconds")
    if used is None and isinstance(limit, (int, float)) and isinstance(remaining, (int, float)):
        used = round(max(0.0, float(limit) - float(remaining)), 2)
    time_used = ended.get("time_used") or ""
    if not time_used and isinstance(used, (int, float)):
        time_used = format_duration(float(used))

    return {
        "team": started.get("team") or ended.get("team") or "",
        "roster": roster,
        "started_at": started.get("local_time") or "",
        "finished_at": ended.get("local_time") or "",
        "reason": ended.get("reason") or "",
        "score": ended.get("score"),
        "time_used": time_used,
        "time_used_seconds": used,
        "game_limit_seconds": limit,
        "game_remaining": remaining,
        "leg_remaining": ended.get("leg_remaining"),
        "players": list(players.values()),
        "counted_answers": list(counted.values()),
        "attempts": attempts,
    }
