"""Desk challenge: file rail, real PTY terminal, optional page, flag bar."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from baton_relay.desk.sandbox import list_public_files, resolve_in_public
from baton_relay.desk.shell import TeamShell
from baton_relay.questions.types import Desk
from baton_relay.ui.pty_terminal import PtyTerminalWidget


@dataclass
class DeskSessionState:
    """Per-challenge UI bits. Each desk keeps its own terminal scrollback."""

    selected_file: str | None = None
    flag_text: str = ""
    terminal_feed: str = ""


@dataclass
class DeskSessionStore:
    """Survives baton freeze rebuilds and wrong-flag flashes for the same challenge."""

    by_id: dict[str, DeskSessionState] = field(default_factory=dict)

    def get(self, qid: str) -> DeskSessionState:
        if qid not in self.by_id:
            self.by_id[qid] = DeskSessionState()
        return self.by_id[qid]

    def clear(self, qid: str | None = None) -> None:
        if qid is None:
            self.by_id.clear()
        else:
            self.by_id.pop(qid, None)


def _mono(size: int = 12) -> QFont:
    font = QFont("Cascadia Mono", size)
    if not font.exactMatch():
        font = QFont("Consolas", size)
    font.setStyleHint(QFont.StyleHint.Monospace)
    return font


class _TerminalPane(QFrame):
    """Full interactive Linux terminal (ConPTY) — nano/vim/apt TUIs work."""

    def __init__(
        self,
        public_dir: Path,
        shell: TeamShell | None,
        *,
        restore: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("deskPanel")
        self.setAutoFillBackground(False)
        self._public = public_dir
        self._shell = shell
        self._locked = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        label = QLabel("Terminal")
        label.setObjectName("deskSection")
        layout.addWidget(label)

        self.term = PtyTerminalWidget()
        self.term.setMinimumHeight(220)
        layout.addWidget(self.term, 1)
        self.bind_shell(shell, restore=restore)

    def bind_shell(self, shell: TeamShell | None, *, restore: str = "") -> None:
        self._shell = shell
        self.term.bind_shell(shell, restore=restore)

    def focus_shell(self) -> None:
        """Put keyboard into the PTY so typing works without a click first."""
        if self._locked:
            return
        self.term.setFocus(Qt.FocusReason.OtherFocusReason)

    def set_locked(self, locked: bool) -> None:
        was_locked = self._locked
        self._locked = locked
        self.term.set_locked(locked)
        if was_locked and not locked:
            self.focus_shell()

    def terminal_feed(self) -> str:
        return self.term.feed_log()

    def detach_shell(self) -> None:
        self.term.detach_shell()

    def paste_filename(self, name: str) -> None:
        if self._locked or not name:
            return
        # Paste the path as typed text so bash/nano receive it like a real keyboard.
        self.term.paste_text(name)
        self.term.setFocus()


class _FilesPane(QFrame):
    """Names only — no free preview of file contents."""

    def __init__(
        self,
        public_dir: Path,
        state: DeskSessionState,
        on_pick: Callable[[str], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("deskRail")
        self.setAutoFillBackground(False)
        self._state = state
        self._on_pick = on_pick

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        label = QLabel("Files")
        label.setObjectName("deskSection")
        layout.addWidget(label)

        self.list = QListWidget()
        self.list.setObjectName("deskFileList")
        self.list.setFont(_mono(11))
        for name in list_public_files(public_dir):
            self.list.addItem(QListWidgetItem(name))
        if state.selected_file:
            matches = self.list.findItems(state.selected_file, Qt.MatchFlag.MatchExactly)
            if matches:
                self.list.setCurrentItem(matches[0])
        self.list.itemClicked.connect(self._clicked)
        layout.addWidget(self.list, 1)

    def _clicked(self, item: QListWidgetItem) -> None:
        name = item.text()
        self._state.selected_file = name
        self._on_pick(name)

    def set_locked(self, locked: bool) -> None:
        self.list.setEnabled(not locked)


class _PagePane(QFrame):
    def __init__(self, public_dir: Path, page_file: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("deskPanel")
        self.setAutoFillBackground(False)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)
        label = QLabel("Page")
        label.setObjectName("deskSection")
        layout.addWidget(label)
        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(False)
        self.browser.setObjectName("deskPage")
        self.browser.setFrameShape(QFrame.Shape.NoFrame)
        path = resolve_in_public(public_dir, page_file)
        self.browser.setSearchPaths([str(public_dir)])
        self.browser.setSource(QUrl.fromLocalFile(str(path)))
        layout.addWidget(self.browser, 1)

    def set_locked(self, locked: bool) -> None:
        self.browser.setEnabled(not locked)


class DeskWidget(QWidget):
    def __init__(
        self,
        question: Desk,
        state: DeskSessionState,
        *,
        shell: TeamShell | None = None,
        on_submit: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("deskRoot")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAutoFillBackground(False)
        self._state = state
        self._on_submit = on_submit
        self._panes: list[Any] = []
        self._term_pane: _TerminalPane | None = None
        public = Path(question.public_dir)
        panes = list(question.panes or ["files", "terminal"])

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        main = QSplitter(Qt.Orientation.Horizontal)
        main.setObjectName("deskSplitter")
        main.setChildrenCollapsible(False)
        main.setHandleWidth(8)
        term: _TerminalPane | None = None

        if "terminal" in panes:
            # Restore this challenge's scrollback before cd so gate ≠ steghide.
            term = _TerminalPane(public, shell, restore=state.terminal_feed)
            self._term_pane = term
            self._panes.append(term)

        # Bind the terminal first so the folder switch is visible, then cd.
        # Doing it the other way round prints the cd into the dying widget.
        if shell is not None:
            try:
                shell.ensure_challenge(question.id, public)
            except Exception as exc:
                if shell.transcript == "":
                    shell.transcript = f"error preparing challenge: {exc}\n"

        if "files" in panes:
            files = _FilesPane(
                public,
                state,
                on_pick=(term.paste_filename if term is not None else lambda _n: None),
            )
            files.setMinimumWidth(160)
            files.setMaximumWidth(240)
            self._panes.append(files)
            main.addWidget(files)

        work = QSplitter(Qt.Orientation.Vertical)
        work.setObjectName("deskSplitter")
        work.setChildrenCollapsible(False)
        work.setHandleWidth(8)
        if "page" in panes and question.page_file:
            page = _PagePane(public, question.page_file)
            self._panes.append(page)
            work.addWidget(page)
        if term is not None:
            work.addWidget(term)
        if work.count() == 1:
            main.addWidget(work.widget(0))
        else:
            work.setStretchFactor(0, 1)
            work.setStretchFactor(work.count() - 1, 2)
            main.addWidget(work)

        if main.count() >= 2:
            main.setStretchFactor(0, 0)
            main.setStretchFactor(1, 1)
            main.setSizes([200, 900])
        layout.addWidget(main, 1)

        flag_bar = QFrame()
        flag_bar.setObjectName("deskFlagBar")
        flag_bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        flag_bar.setAutoFillBackground(False)
        flag_row = QHBoxLayout(flag_bar)
        flag_row.setContentsMargins(4, 4, 4, 0)
        flag_row.setSpacing(14)
        flag_label = QLabel("Flag")
        flag_label.setObjectName("deskSection")
        flag_row.addWidget(flag_label)
        self.flag_edit = QLineEdit()
        self.flag_edit.setObjectName("deskFlagIn")
        self.flag_edit.setPlaceholderText("TR{…}")
        self.flag_edit.setFont(_mono(13))
        self.flag_edit.setText(state.flag_text)
        self.flag_edit.textChanged.connect(self._save_flag)
        self.flag_edit.returnPressed.connect(self._submit_clicked)
        self.submit_btn = QPushButton("SUBMIT")
        self.submit_btn.setObjectName("deskSubmit")
        self.submit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.submit_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.submit_btn.setFlat(True)
        self.submit_btn.clicked.connect(self._submit_clicked)
        field = QWidget()
        field.setObjectName("deskFlagField")
        field.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        field.setAutoFillBackground(False)
        field_row = QHBoxLayout(field)
        field_row.setContentsMargins(0, 0, 0, 0)
        field_row.setSpacing(0)
        field_row.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        field_row.addWidget(self.flag_edit, 1)
        field_row.addWidget(self.submit_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        flag_row.addWidget(field, 1)
        layout.addWidget(flag_bar)

    def _save_flag(self, text: str) -> None:
        self._state.flag_text = text

    def _submit_clicked(self) -> None:
        if self._on_submit:
            self._on_submit()

    def set_desk_locked(self, locked: bool) -> None:
        # Do not focus_shell here: GameSession ticks re-render ~10×/s and would
        # yank focus out of the flag field every time. Unlock focus is handled by
        # QuestionHost.set_locked / _TerminalPane.set_locked on locked→unlocked.
        self.flag_edit.setEnabled(not locked)
        self.submit_btn.setEnabled(not locked)
        for pane in self._panes:
            pane.set_locked(locked)

    def focus_shell(self) -> None:
        if self._term_pane is not None:
            self._term_pane.focus_shell()

    def persist_terminal(self) -> None:
        """Save scrollback onto the session state before this desk is torn down."""
        if self._term_pane is not None:
            self._state.terminal_feed = self._term_pane.terminal_feed()

    def detach_shell(self) -> None:
        self.persist_terminal()
        for pane in self._panes:
            detach = getattr(pane, "detach_shell", None)
            if detach is not None:
                detach()

    def collect_flag(self) -> str:
        text = self.flag_edit.text()
        if not text.strip():
            raise ValueError("Enter a flag")
        return text


def build_desk_widget(
    question: Desk,
    state: DeskSessionState,
    *,
    shell: TeamShell | None = None,
    on_submit: Callable[[], None] | None = None,
) -> tuple[QWidget, Callable[[], Any], DeskWidget]:
    desk = DeskWidget(question, state, shell=shell, on_submit=on_submit)
    return desk, desk.collect_flag, desk
