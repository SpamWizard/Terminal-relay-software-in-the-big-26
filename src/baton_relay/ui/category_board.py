"""Jeopardy-style category pick board (mouse)."""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class CategoryBoard(QWidget):
    """Grid of category buttons. Emits set_id when a category is clicked."""

    category_chosen = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._handler: Callable[[str], None] | None = None
        self._shown: tuple[tuple[str, str], ...] | None = None
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(16)

        self.heading = QLabel("SELECT A CATEGORY")
        self.heading.setObjectName("headline")
        self.heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self.heading)

        self.hint = QLabel("Timers are paused while you choose.")
        self.hint.setObjectName("muted")
        self.hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self.hint)

        self._grid_host = QWidget()
        self._grid = QGridLayout(self._grid_host)
        self._grid.setSpacing(12)
        root.addWidget(self._grid_host, 1)
        root.addStretch(0)

    def set_choose_handler(self, handler: Callable[[str], None]) -> None:
        self._handler = handler

    def show_categories(self, categories: list[tuple[str, str]]) -> None:
        """categories: list of (set_id, title)."""
        shown = tuple((sid, title) for sid, title in categories)
        # The game view re-renders many times a second. Rebuilding the buttons
        # each time deletes the one under the cursor, so the click never lands.
        if shown == self._shown:
            return
        self._shown = shown

        while self._grid.count():
            item = self._grid.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()

        if not categories:
            empty = QLabel("No categories left.")
            empty.setObjectName("muted")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._grid.addWidget(empty, 0, 0)
            return

        cols = min(4, max(1, len(categories)))
        for i, (set_id, title) in enumerate(categories):
            btn = QPushButton(title)
            btn.setObjectName("categoryTile")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setMinimumHeight(96)
            btn.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
            )
            btn.clicked.connect(lambda _=False, sid=set_id: self._on_click(sid))
            self._grid.addWidget(btn, i // cols, i % cols)

    def _on_click(self, set_id: str) -> None:
        self.category_chosen.emit(set_id)
        if self._handler:
            self._handler(set_id)
