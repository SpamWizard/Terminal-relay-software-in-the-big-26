"""Application bootstrap."""

from __future__ import annotations

import sys
from pathlib import Path

from baton_relay.config import ConfigError, load_config
from baton_relay.questions.loader import QuestionLoadError, load_all_question_files


def run_app(*, config_path: Path, fake_device: bool = False) -> int:
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

    # Default to fake device when no serial hardware path is ready
    if not fake_device:
        # Until serial lands, fall back to fake so the app is playable
        print("Note: serial RP2040 mode not implemented yet; enabling --fake-device.")
        fake_device = True

    from PySide6.QtWidgets import QApplication

    from baton_relay.ui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("Terminal Relay")
    window = MainWindow(config, sets, fake_device=fake_device)
    window.showFullScreen()
    return app.exec()
