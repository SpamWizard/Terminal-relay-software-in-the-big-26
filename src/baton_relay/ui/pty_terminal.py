"""Real terminal view: ConPTY bytes in/out via pyte screen rendering."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QTimer, Signal, Slot
from PySide6.QtGui import QColor, QFont, QKeyEvent, QMouseEvent, QPainter, QResizeEvent
from PySide6.QtWidgets import QApplication, QMenu, QWidget

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
_SEL = QColor(125, 211, 252, 110)


def shell_paste_text(raw: str) -> str:
    """Clipboard text for the shell. A trailing newline must not press Enter."""
    text = (raw or "").replace("\r\n", "\n").replace("\r", "\n")
    if text.endswith("\n"):
        text = text[:-1]
    return text.replace("\n", "\r")


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
        self._anchor: tuple[int, int] | None = None
        self._caret: tuple[int, int] | None = None
        self._dragging = False
        self._click_same = False
        self._keep_word = False
        self._measure_cells()
        self.setCursor(Qt.CursorShape.IBeamCursor)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.DefaultContextMenu)

        self._raw_output.connect(self._queue_output)
        self._flush_timer = QTimer(self)
        self._flush_timer.setSingleShot(True)
        self._flush_timer.setInterval(16)  # ~60fps coalesce
        self._flush_timer.timeout.connect(self._flush_pending)

    def bind_shell(self, shell: TeamShell | None) -> None:
        self.detach_shell()
        self._shell = shell
        self._pending = ""
        self._anchor = None
        self._caret = None
        self._dragging = False
        self._screen = pyte.HistoryScreen(self._cols, self._rows, history=5000)
        self._stream = pyte.Stream(self._screen)
        if shell is not None:
            # Cross-thread safe: reader calls emit → GUI slot.
            shell.on_output = self._emit_output
            shell.resize(self._cols, self._rows)
            self.update()

    def detach_shell(self) -> None:
        """Drop this widget's output callback without touching a newer terminal."""
        shell = self._shell
        if shell is not None and shell.on_output == self._emit_output:
            shell.on_output = None

    def _emit_output(self, text: str) -> None:
        self._raw_output.emit(text)

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
            if not self._dragging:
                self._anchor = None
                self._caret = None
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
                selected = self._cell_selected(x, y)
                x2 = x + 1
                while x2 < screen.columns:
                    n = screen.buffer[y][x2]
                    if (
                        (n.fg or "default") != fg_name
                        or (n.bg or "default") != bg_name
                        or n.reverse != rev
                        or self._cell_selected(x2, y) != selected
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
                if selected:
                    painter.fillRect(rect_x, rect_y, width, self._cell_h, _SEL)
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

    def _has_selection(self) -> bool:
        return self._anchor is not None and self._caret is not None

    def _selection_bounds(self) -> tuple[int, int, int, int]:
        assert self._anchor is not None and self._caret is not None
        (ax, ay), (bx, by) = self._anchor, self._caret
        if (ay, ax) <= (by, bx):
            return ax, ay, bx, by
        return bx, by, ax, ay

    def _cell_selected(self, x: int, y: int) -> bool:
        if not self._has_selection():
            return False
        x1, y1, x2, y2 = self._selection_bounds()
        if y < y1 or y > y2:
            return False
        if y1 == y2:
            return x1 <= x <= x2
        if y == y1:
            return x >= x1
        if y == y2:
            return x <= x2
        return True

    def _selection_text(self) -> str:
        if not self._has_selection():
            return ""
        x1, y1, x2, y2 = self._selection_bounds()
        display = self._screen.display
        lines: list[str] = []
        for y in range(y1, y2 + 1):
            if y >= len(display):
                break
            line = display[y]
            start = x1 if y == y1 else 0
            end = x2 if y == y2 else len(line) - 1
            start = max(0, min(start, len(line)))
            end = max(-1, min(end, len(line) - 1))
            if end < start:
                lines.append("")
            else:
                lines.append(line[start : end + 1].rstrip())
        return "\n".join(lines)

    def _cell_at(self, pos) -> tuple[int, int]:
        cols = max(1, self._screen.columns)
        rows = max(1, self._screen.lines)
        x = int(pos.x() // max(1, self._cell_w))
        y = int(pos.y() // max(1, self._cell_h))
        return max(0, min(cols - 1, x)), max(0, min(rows - 1, y))

    def _select_word_at(self, x: int, y: int) -> None:
        display = self._screen.display
        if y < 0 or y >= len(display):
            self._anchor = None
            self._caret = None
            return
        line = display[y].rstrip()
        if x >= len(line) or line[x] == " ":
            self._anchor = None
            self._caret = None
            return
        x0 = x
        while x0 > 0 and line[x0 - 1] != " ":
            x0 -= 1
        x1 = x
        while x1 + 1 < len(line) and line[x1 + 1] != " ":
            x1 += 1
        self._anchor = (x0, y)
        self._caret = (x1, y)

    def _copy_selection(self) -> None:
        text = self._selection_text()
        if not text.strip():
            return
        QApplication.clipboard().setText(text)

    def _paste_clipboard(self) -> None:
        if self._locked or self._shell is None:
            return
        text = shell_paste_text(QApplication.clipboard().text())
        if text:
            self.paste_text(text)

    def _copy_requested(self, event: QKeyEvent) -> bool:
        key = event.key()
        mods = event.modifiers()
        ctrl = bool(mods & Qt.KeyboardModifier.ControlModifier)
        shift = bool(mods & Qt.KeyboardModifier.ShiftModifier)
        if key == Qt.Key.Key_C and ctrl and shift:
            return True
        if key == Qt.Key.Key_Insert and ctrl and not shift:
            return True
        return bool(key == Qt.Key.Key_C and ctrl and not shift and self._has_selection())

    def _paste_requested(self, event: QKeyEvent) -> bool:
        key = event.key()
        mods = event.modifiers()
        ctrl = bool(mods & Qt.KeyboardModifier.ControlModifier)
        shift = bool(mods & Qt.KeyboardModifier.ShiftModifier)
        if key == Qt.Key.Key_V and ctrl:
            return True
        return bool(key == Qt.Key.Key_Insert and shift and not ctrl)

    def focusNextPrevChild(self, next: bool) -> bool:  # noqa: N802
        # Tab is bash completion while the shell is live. Qt otherwise uses it
        # to move focus to the flag box, so the shell never sees the key.
        if self._locked or self._shell is None:
            return super().focusNextPrevChild(next)
        return False

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if self._copy_requested(event):
            self._copy_selection()
            event.accept()
            return
        if self._paste_requested(event):
            self._paste_clipboard()
            event.accept()
            return
        if self._locked or self._shell is None:
            return
        seq = _key_to_seq(event)
        if seq is None:
            super().keyPressEvent(event)
            return
        self._shell.write_keys(seq)
        event.accept()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self.setFocus()
        if event.button() == Qt.MouseButton.LeftButton:
            self._keep_word = False
            self._click_same = True
            self._dragging = True
            cell = self._cell_at(event.position())
            self._anchor = cell
            self._caret = cell
            self.update()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._dragging and event.buttons() & Qt.MouseButton.LeftButton:
            cell = self._cell_at(event.position())
            if cell != self._anchor:
                self._click_same = False
            self._caret = cell
            self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self._dragging:
            self._dragging = False
            # A double-click already selected the whole word; don't shrink it.
            if not self._keep_word:
                self._caret = self._cell_at(event.position())
                if self._click_same:
                    self._anchor = None
                    self._caret = None
                elif self._selection_text().strip():
                    self._copy_selection()
            self.update()
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            x, y = self._cell_at(event.position())
            self._select_word_at(x, y)
            self._keep_word = self._has_selection()
            self._click_same = False
            self._dragging = False
            if self._keep_word:
                self._copy_selection()
            self.update()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event) -> None:  # noqa: N802
        menu = QMenu(self)
        copy_act = menu.addAction("Copy")
        copy_act.setEnabled(self._has_selection())
        paste_act = menu.addAction("Paste")
        clip = QApplication.clipboard().text()
        paste_act.setEnabled(bool(clip) and not self._locked and self._shell is not None)
        chosen = menu.exec(event.globalPos())
        if chosen is copy_act:
            self._copy_selection()
        elif chosen is paste_act:
            self._paste_clipboard()


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
