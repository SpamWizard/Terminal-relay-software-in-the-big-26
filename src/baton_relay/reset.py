"""Prepare the machine for the next team."""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path

from baton_relay.config import ConfigError, load_config


def reset_machine(config_path: Path) -> int:
    try:
        config = load_config(config_path)
    except ConfigError as exc:
        print(f"ERROR: {exc}")
        return 1

    # Archive checkpoint if present
    ckpt = config.paths.checkpoint_path
    if ckpt.is_file():
        archive_dir = config.paths.results_dir / "_archived_checkpoints"
        archive_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        dest = archive_dir / f"checkpoint_{stamp}.json"
        shutil.move(str(ckpt), str(dest))
        print(f"Archived checkpoint → {dest}")
    else:
        print("No active checkpoint.")

    # Container cleanup hook (no-op until phase 5)
    print("Container cleanup: skipped (not enabled in MVP).")
    print("Reset complete. Ready for next team.")
    return 0
