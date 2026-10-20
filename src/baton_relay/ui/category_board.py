"""Jeopardy-style category pick board (mouse)."""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import (
    QGridLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QStyle,
    QStyleOptionButton,
    QVBoxLayout,
    QWidget,
)

from baton_relay.config import MAX_BOARD_SLOTS

# (row, column, column_span) inside a grid of `columns` equal tracks.
# Every row is full, so the tiles cover the board with no empty hole.
_PLACEMENTS: dict[int, tuple[int, tuple[tuple[int, int, int], ...]]] = {
    1: (1, ((0, 0, 1),)),
    2: (2, ((0, 0, 1), (0, 1, 1))),
    3: (3, ((0, 0, 1), (0, 1, 1), (0, 2, 1))),
    4: (2, ((0, 0, 1), (0, 1, 1), (1, 0, 1), (1, 1, 1))),
    # 3 on top, 2 below, both rows the full width.
    5: (
        6,
        (
            (0, 0, 2),
            (0, 2, 2),
            (0, 4, 2),
            (1, 0, 3),
            (1, 3, 3),
        ),
    ),
    6: (
        3,
        (
            (0, 0, 1),
            (0, 1, 1),
            (0, 2, 1),
            (1, 0, 1),
            (1, 1, 1),
            (1, 2, 1),
        ),
    ),
    # 4 on top, 3 below, both rows the full width.
    7: (
        12,
        (
            (0, 0, 3),
            (0, 3, 3),
            (0, 6, 3),
            (0, 9, 3),
            (1, 0, 4),
            (1, 4, 4),
            (1, 8, 4),
        ),
    ),
    8: (
        4,
        (
            (0, 0, 1),
            (0, 1, 1),
            (0, 2, 1),
            (0, 3, 1),
            (1, 0, 1),
            (1, 1, 1),
            (1, 2, 1),
            (1, 3, 1),
        ),
    ),
}


def board_placements(count: int) -> tuple[int, tuple[tuple[int, int, int], ...]]:
    """Return (column_count, placements) for the tiles that fill the board."""
    n = max(1, min(count, MAX_BOARD_SLOTS))
    return _PLACEMENTS[n]


class _CategoryTile(QPushButton):
    """Button chrome from the theme, with the title wrapped in the same color."""

    def __init__(self, title: str) -> None:
        super().__init__()
        self._title = title
        self.setObjectName("categoryTile")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.setMinimumSize(0, 72)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        option = QStyleOptionButton()
        self.initStyleOption(option)
        option.text = ""
        self.style().drawControl(QStyle.ControlElement.CE_PushButton, option, painter, self)
        rect = self.style().subElementRect(
            QStyle.SubElement.SE_PushButtonContents, option, self
        )
        painter.setPen(option.palette.buttonText().color())
        painter.setFont(self.font())
        painter.drawText(
            rect,
            int(Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap),
            self._title,
        )
        painter.end()


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
        self._grid_host.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._grid = QGridLayout(self._grid_host)
        self._grid.setSpacing(12)
        self._grid.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self._grid_host, 1)

    def set_choose_handler(self, handler: Callable[[str], None]) -> None:
        self._handler = handler

    def show_categories(self, categories: list[tuple[str, str]]) -> None:
        """categories: list of (set_id, title). At most 8 are shown."""
        visible = list(categories)[:MAX_BOARD_SLOTS]
        shown = tuple((sid, title) for sid, title in visible)
        # The game view re-renders many times a second. Rebuilding the buttons
        # each time deletes the one under the cursor, so the click never lands.
        if shown == self._shown:
            return
        self._shown = shown
        self._clear_grid()

        if not visible:
            empty = QLabel("No categories left.")
            empty.setObjectName("muted")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._grid.addWidget(empty, 0, 0)
            return

        columns, placements = board_placements(len(visible))
        rows = 0
        for i, (set_id, title) in enumerate(visible):
            row, col, span = placements[i]
            rows = max(rows, row + 1)
            self._grid.addWidget(self._make_tile(set_id, title), row, col, 1, span)
        for c in range(columns):
            self._grid.setColumnStretch(c, 1)
        for r in range(rows):
            self._grid.setRowStretch(r, 1)

    def _clear_grid(self) -> None:
        while self._grid.count():
            item = self._grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        for i in range(12):
            self._grid.setColumnStretch(i, 0)
            self._grid.setRowStretch(i, 0)

    def _make_tile(self, set_id: str, title: str) -> QPushButton:
        btn = _CategoryTile(title)
        btn.clicked.connect(lambda _=False, sid=set_id: self._on_click(sid))
        return btn

    def _on_click(self, set_id: str) -> None:
        self.category_chosen.emit(set_id)
        if self._handler:
            self._handler(set_id)
