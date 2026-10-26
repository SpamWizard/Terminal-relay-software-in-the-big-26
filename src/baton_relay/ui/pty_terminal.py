"""Real terminal view: ConPTY bytes in/out via pyte screen rendering."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QTimer, Signal, Slot
from PySide6.QtGui import QColor, QFont, QKeyEvent, QPainter, QResizeEvent
from PySide6.QtWidgets import QWidget

import pyte

if TYPE_CHECKING:
    from baton_relay.desk.shell import TeamShell


def _mono(size: int = 13) -> QFont:
    font = QFont("Cascadia Mono", size)
    if not font.exactMatch():
        font = QFont("Consolas", size)
    font.setStyleHint(QFont.StyleHint.Monospace)
    return font


_FG = {
    "black": QColor("#0b1220"),
    "red": QColor("#f87171"),
    "green": QColor("#4ade80"),
    "brown": QColor("#fbbf24"),
    "yellow": QColor("#fbbf24"),
    "blue": QColor("#60a5fa"),
    "magenta": QColor("#e879f9"),
    "cyan": QColor("#22d3ee"),
    "white": QColor("#e2e8f0"),
    "default": QColor("#e2e8f0"),
}
_BG = {
    "black": QColor("#020617"),
    "red": QColor("#7f1d1d"),
    "green": QColor("#14532d"),
    "brown": QColor("#78350f"),
    "yellow": QColor("#78350f"),
    "blue": QColor("#1e3a8a"),
    "magenta": QColor("#701a75"),
    "cyan": QColor("#155e75"),
    "white": QColor("#334155"),
    "default": QColor("#020617"),
}


class PtyTerminalWidget(QWidget):
    """Focusable terminal that talks to TeamShell's ConPTY."""

    # Emitted from the PTY reader thread; Qt queues this onto the GUI thread.
    _raw_output = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("deskPtyTerminal")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFont(_mono(13))
        self._shell: TeamShell | None = None
        self._locked = False
        self._cols = 80
        self._rows = 24
        self._screen = pyte.HistoryScreen(self._cols, self._rows, history=5000)
        self._stream = pyte.Stream(self._screen)
        self._cell_w = 8
        self._cell_h = 16
        self._pending = ""
        self._measure_cells()

        self._raw_output.connect(self._queue_output)
        self._flush_timer = QTimer(self)
        self._flush_timer.setSingleShot(True)
        self._flush_timer.setInterval(16)  # ~60fps coalesce
        self._flush_timer.timeout.connect(self._flush_pending)

    def bind_shell(self, shell: TeamShell | None) -> None:
        if self._shell is not None:
            self._shell.on_output = None
        self._shell = shell
        self._pending = ""
        self._screen = pyte.HistoryScreen(self._cols, self._rows, history=5000)
        self._stream = pyte.Stream(self._screen)
        if shell is not None:
            # Cross-thread safe: reader calls emit → GUI slot.
            shell.on_output = lambda text: self._raw_output.emit(text)
            shell.resize(self._cols, self._rows)
            self.update()

    def set_locked(self, locked: bool) -> None:
        self._locked = locked
        if self._shell is not None:
            self._shell.set_locked(locked)

    def paste_text(self, text: str) -> None:
        if self._locked or not text or self._shell is None:
            return
        self._shell.write_keys(text)
        self.setFocus()

    @Slot(str)
    def _queue_output(self, text: str) -> None:
        if not text:
            return
        self._pending += text
        if not self._flush_timer.isActive():
            self._flush_timer.start()

    @Slot()
    def _flush_pending(self) -> None:
        data, self._pending = self._pending, ""
        if data:
            self._stream.feed(data)
        self.update()

    def _measure_cells(self) -> None:
        metrics = self.fontMetrics()
        self._cell_w = max(6, metrics.horizontalAdvance("M"))
        self._cell_h = max(12, metrics.height())

    def _fit_size(self) -> None:
        self._measure_cells()
        cols = max(20, self.width() // self._cell_w)
        rows = max(8, self.height() // self._cell_h)
        if cols == self._cols and rows == self._rows:
            return
        self._cols = cols
        self._rows = rows
        self._screen.resize(rows, cols)
        if self._shell is not None:
            self._shell.resize(cols, rows)

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._fit_size()
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), _BG["default"])
        painter.setFont(self.font())
        ascent = self.fontMetrics().ascent()
        screen = self._screen
        # Draw runs of same colors (much faster than per-cell drawText).
        for y in range(screen.lines):
            x = 0
            while x < screen.columns:
                cell = screen.buffer[y][x]
                fg_name = cell.fg or "default"
                bg_name = cell.bg or "default"
                rev = cell.reverse
                run = cell.data or " "
                x2 = x + 1
                while x2 < screen.columns:
                    n = screen.buffer[y][x2]
                    if (
                        (n.fg or "default") != fg_name
                        or (n.bg or "default") != bg_name
                        or n.reverse != rev
                    ):
                        break
                    run += n.data or " "
                    x2 += 1
                fg = _FG.get(fg_name, _FG["default"])
                bg = _BG.get(bg_name, _BG["default"])
                if rev:
                    fg, bg = bg, fg
                rect_x = x * self._cell_w
                rect_y = y * self._cell_h
                width = (x2 - x) * self._cell_w
                if bg != _BG["default"] or rev:
                    painter.fillRect(rect_x, rect_y, width, self._cell_h, bg)
                painter.setPen(fg)
                painter.drawText(rect_x, rect_y + ascent, run)
                x = x2
        cx, cy = screen.cursor.x, screen.cursor.y
        if 0 <= cy < screen.lines and 0 <= cx < screen.columns:
            painter.fillRect(
                cx * self._cell_w,
                cy * self._cell_h,
                self._cell_w,
                self._cell_h,
                QColor(125, 211, 252, 180),
            )

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if self._locked or self._shell is None:
            return
        seq = _key_to_seq(event)
        if seq is None:
            super().keyPressEvent(event)
            return
        self._shell.write_keys(seq)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        self.setFocus()
        super().mousePressEvent(event)


def _key_to_seq(event: QKeyEvent) -> str | None:
    key = event.key()
    mods = event.modifiers()
    text = event.text()

    if mods & Qt.KeyboardModifier.ControlModifier:
        if Qt.Key.Key_A <= key <= Qt.Key.Key_Z:
            return chr(key - Qt.Key.Key_A + 1)
        if key in (Qt.Key.Key_BracketLeft,):
            return "\x1b"
        if key == Qt.Key.Key_Backslash:
            return "\x1c"
        if key == Qt.Key.Key_Slash:
            return "\x1f"
        return None

    mapping = {
        Qt.Key.Key_Return: "\r",
        Qt.Key.Key_Enter: "\r",
        Qt.Key.Key_Backspace: "\x7f",
        Qt.Key.Key_Tab: "\t",
        Qt.Key.Key_Escape: "\x1b",
        Qt.Key.Key_Up: "\x1b[A",
        Qt.Key.Key_Down: "\x1b[B",
        Qt.Key.Key_Right: "\x1b[C",
        Qt.Key.Key_Left: "\x1b[D",
        Qt.Key.Key_Home: "\x1b[H",
        Qt.Key.Key_End: "\x1b[F",
        Qt.Key.Key_PageUp: "\x1b[5~",
        Qt.Key.Key_PageDown: "\x1b[6~",
        Qt.Key.Key_Insert: "\x1b[2~",
        Qt.Key.Key_Delete: "\x1b[3~",
        Qt.Key.Key_F1: "\x1bOP",
        Qt.Key.Key_F2: "\x1bOQ",
        Qt.Key.Key_F3: "\x1bOR",
        Qt.Key.Key_F4: "\x1bOS",
        Qt.Key.Key_F5: "\x1b[15~",
        Qt.Key.Key_F6: "\x1b[17~",
        Qt.Key.Key_F7: "\x1b[18~",
        Qt.Key.Key_F8: "\x1b[19~",
        Qt.Key.Key_F9: "\x1b[20~",
        Qt.Key.Key_F10: "\x1b[21~",
        Qt.Key.Key_F11: "\x1b[23~",
        Qt.Key.Key_F12: "\x1b[24~",
    }
    if key in mapping:
        return mapping[key]
    if text:
        return text
    return None
