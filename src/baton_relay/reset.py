"""Prepare the machine for the next team."""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path

from baton_relay.config import ConfigError, load_config


def _archive_file(path: Path, archive_dir: Path, prefix: str) -> Path | None:
    if not path.is_file():
        return None
    archive_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = archive_dir / f"{prefix}_{stamp}_{path.name}"
    # Avoid collisions if reset is called twice in the same second
    n = 1
    while dest.exists():
        dest = archive_dir / f"{prefix}_{stamp}_{n}_{path.name}"
        n += 1
    shutil.move(str(path), str(dest))
    return dest


def reset_machine(config_path: Path) -> int:
    try:
        config = load_config(config_path)
    except ConfigError as exc:
        print(f"ERROR: {exc}")
        return 1

    archive_dir = config.paths.results_dir / "_archived_checkpoints"
    moved = 0

    mirror = _archive_file(config.paths.checkpoint_path, archive_dir, "mirror")
    if mirror is not None:
        print(f"Archived active checkpoint → {mirror}")
        moved += 1

    results = config.paths.results_dir
    if results.is_dir():
        for team_dir in sorted(results.iterdir()):
            if not team_dir.is_dir() or team_dir.name.startswith("_"):
                continue
            for run_dir in sorted(team_dir.iterdir()):
                if not run_dir.is_dir():
                    continue
                ckpt = run_dir / "checkpoint.json"
                finished = (run_dir / "summary.json").is_file()
                if finished and ckpt.is_file():
                    # Stale checkpoint after a finished run
                    archived = _archive_file(ckpt, archive_dir, "stale")
                    if archived is not None:
                        print(f"Archived stale checkpoint → {archived}")
                        moved += 1
                elif not finished and ckpt.is_file():
                    archived = _archive_file(ckpt, archive_dir, "unfinished")
                    if archived is not None:
                        print(f"Archived unfinished run checkpoint → {archived}")
                        moved += 1

    if moved == 0:
        print("No checkpoints to archive.")

    print("Container cleanup: skipped (not implemented yet).")
    print("Reset complete. Ready for next team.")
    return 0
