"""HC-style challenge desk: file rail, terminal, optional page, flag bar."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QEvent, Qt, QUrl
from PySide6.QtGui import QFont, QKeyEvent, QTextCursor
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from baton_relay.desk.complete import complete_line
from baton_relay.desk.sandbox import list_public_files, resolve_in_public
from baton_relay.desk.terminal import run_desk_command
from baton_relay.questions.types import Desk


@dataclass
class DeskSessionState:
    scrollback: str = ""
    selected_file: str | None = None
    flag_text: str = ""


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


class _TerminalInput(QLineEdit):
    """Line edit that uses Tab for autocomplete instead of focus change."""

    def __init__(self, on_tab: Callable[[], None], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._on_tab = on_tab

    def event(self, event: QEvent) -> bool:  # noqa: N802
        # Steal Tab before Qt uses it to move focus.
        if (
            event.type() == QEvent.Type.KeyPress
            and isinstance(event, QKeyEvent)
            and event.key() == Qt.Key.Key_Tab
            and not event.modifiers()
        ):
            self._on_tab()
            return True
        return super().event(event)


class _TerminalPane(QFrame):
    def __init__(self, public_dir: Path, state: DeskSessionState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("deskPanel")
        self.setAutoFillBackground(False)
        self._public = public_dir
        self._state = state
        self._locked = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        head = QHBoxLayout()
        label = QLabel("Terminal")
        label.setObjectName("deskSection")
        head.addWidget(label)
        head.addStretch(1)
        tip = QLabel("Tab completes · help · cat · grep · b64 · sha256 · python")
        tip.setObjectName("deskHint")
        head.addWidget(tip)
        layout.addLayout(head)

        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setObjectName("deskTerminalOut")
        self.output.setFont(_mono(12))
        self.output.setFrameShape(QFrame.Shape.NoFrame)
        if state.scrollback:
            self.output.setPlainText(state.scrollback)
            self.output.moveCursor(QTextCursor.MoveOperation.End)
        else:
            self.output.setPlainText("Ready. Click a file on the left, or type a command.\n")
            state.scrollback = self.output.toPlainText()
        layout.addWidget(self.output, 1)

        row = QHBoxLayout()
        row.setSpacing(8)
        prompt = QLabel("›")
        prompt.setObjectName("deskPrompt")
        row.addWidget(prompt)
        self.input = _TerminalInput(self._complete)
        self.input.setObjectName("deskTerminalIn")
        self.input.setPlaceholderText("command  (Tab to complete)")
        self.input.setFont(_mono(13))
        self.input.returnPressed.connect(self._run)
        row.addWidget(self.input, 1)
        layout.addLayout(row)

    def set_locked(self, locked: bool) -> None:
        self._locked = locked
        self.input.setEnabled(not locked)

    def paste_filename(self, name: str) -> None:
        if self._locked or not name:
            return
        current = self.input.text()
        if not current.strip():
            self.input.setText(f"cat {name}")
        else:
            self.input.setText(current.rstrip() + " " + name)
        self.input.setFocus()
        self.input.end(False)

    def _append(self, text: str) -> None:
        self.output.appendPlainText(text)
        self._state.scrollback = self.output.toPlainText()

    def _complete(self) -> None:
        if self._locked:
            return
        result = complete_line(self._public, self.input.text())
        if result.text != self.input.text():
            self.input.setText(result.text)
            self.input.end(False)
        elif len(result.matches) > 1:
            self._append("  ".join(result.matches))

    def _run(self) -> None:
        if self._locked:
            return
        line = self.input.text()
        self.input.clear()
        self._append(f"› {line}")
        result = run_desk_command(self._public, line)
        if result.output:
            self._append(result.output)
        elif result.exit_code != 0:
            self._append(f"(exit {result.exit_code})")
        self._state.scrollback = self.output.toPlainText()


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

        hint = QLabel("Click to paste")
        hint.setObjectName("deskHint")
        layout.addWidget(hint)

        self.list = QListWidget()
        self.list.setObjectName("deskFileList")
        self.list.setSpacing(2)
        self.list.setFrameShape(QFrame.Shape.NoFrame)
        for name in list_public_files(public_dir):
            item = QListWidgetItem(name)
            self.list.addItem(item)
        self.list.itemClicked.connect(self._clicked)
        layout.addWidget(self.list, 1)

        if state.selected_file:
            matches = self.list.findItems(state.selected_file, Qt.MatchFlag.MatchExactly)
            if matches:
                self.list.setCurrentItem(matches[0])

    def set_locked(self, locked: bool) -> None:
        self.list.setEnabled(not locked)

    def _clicked(self, item: QListWidgetItem) -> None:
        name = item.text()
        self._state.selected_file = name
        self._on_pick(name)


class _PagePane(QFrame):
    def __init__(self, public_dir: Path, page_file: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("deskPanel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
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
            term = _TerminalPane(public, state)
            self._panes.append(term)

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
        flag_row.setSpacing(10)
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
        flag_row.addWidget(self.flag_edit, 1)
        self.submit_btn = QPushButton("Submit")
        self.submit_btn.setObjectName("deskSubmit")
        self.submit_btn.clicked.connect(self._submit_clicked)
        flag_row.addWidget(self.submit_btn)
        layout.addWidget(flag_bar)

    def _save_flag(self, text: str) -> None:
        self._state.flag_text = text

    def _submit_clicked(self) -> None:
        if self._on_submit:
            self._on_submit()

    def set_desk_locked(self, locked: bool) -> None:
        self.flag_edit.setEnabled(not locked)
        self.submit_btn.setEnabled(not locked)
        for pane in self._panes:
            pane.set_locked(locked)

    def collect_flag(self) -> str:
        text = self.flag_edit.text()
        if not text.strip():
            raise ValueError("Enter a flag")
        return text


def build_desk_widget(
    question: Desk,
    state: DeskSessionState,
    *,
    on_submit: Callable[[], None] | None = None,
) -> tuple[QWidget, Callable[[], Any], DeskWidget]:
    desk = DeskWidget(question, state, on_submit=on_submit)
    return desk, desk.collect_flag, desk
