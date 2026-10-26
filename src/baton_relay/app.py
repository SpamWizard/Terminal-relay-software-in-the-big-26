"""Application bootstrap."""

from __future__ import annotations

import sys
from pathlib import Path

from baton_relay.config import ConfigError, load_config
from baton_relay.desk.shell import ShellError, require_desk_runtime
from baton_relay.questions.loader import QuestionLoadError, load_all_question_files
from baton_relay.questions.types import Desk


def run_app(*, config_path: Path, fake_device: bool = False, quick: bool = False) -> int:
    try:
        config = load_config(config_path)
    except ConfigError as exc:
        print(f"ERROR: bad config: {exc}", file=sys.stderr)
        return 1

    try:
        sets = load_all_question_files(config.questions.files)
    except QuestionLoadError as exc:
        print(f"ERROR: bad question file: {exc}", file=sys.stderr)
        return 1

    needs_desk = any(isinstance(q, Desk) for s in sets for q in s.questions)
    if needs_desk:
        repo_root = config.paths.results_dir.parent
        try:
            require_desk_runtime(repo_root)
        except ShellError as exc:
            print(f"ERROR: desk challenges need a working WSL setup:\n{exc}", file=sys.stderr)
            return 1

    from PySide6.QtWidgets import QApplication

    from baton_relay.ui.main_window import MainWindow

    if quick:
        fake_device = True
        names = ", ".join(person.label for person in config.people)
        print(f"Quick start: team Quick, players {names}.")
        print("Category selection is up. No baton, ever.")

    app = QApplication(sys.argv)
    app.setApplicationName("Terminal Relay")
    if fake_device:
        print("Baton input: fake-device (keyboard 1–6 / P / U)")
    else:
        port = config.serial.port
        print(f"Baton input: RP2040 serial (port={port!r}, baud={config.serial.baud})")
        print("Use --fake-device if no board is connected.")
    window = MainWindow(config, sets, fake_device=fake_device, quick=quick)
    window.showFullScreen()
    return app.exec()
