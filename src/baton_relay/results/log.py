"""Append-only JSONL event log and end-of-game summary."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


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
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in team_name.strip()) or "team"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = results_dir / safe / stamp
    path.mkdir(parents=True, exist_ok=True)
    return path
