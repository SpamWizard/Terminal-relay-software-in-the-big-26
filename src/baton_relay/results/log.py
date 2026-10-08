"""Append-only JSONL event log and end-of-game summary."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


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
        finished = (child / "summary.json").is_file() or _events_has_game_ended(
            child / "events.jsonl"
        )
        has_ckpt = (child / "checkpoint.json").is_file()
        # A run that only has an empty folder isn't useful
        if not (child / "events.jsonl").is_file() and not has_ckpt and not finished:
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
    return bool(list_team_runs(results_dir, team_name)) or find_team_folder(
        results_dir, team_name
    ) is not None
