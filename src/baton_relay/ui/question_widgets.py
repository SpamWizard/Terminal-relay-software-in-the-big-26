"""Question answer widgets hosted inside the active game screen."""

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from baton_relay.desk.shell import TeamShell
from baton_relay.questions.base import Question
from baton_relay.questions.images import pictures_for
from baton_relay.questions.types import Desk, MultipleChoice
from baton_relay.ui.desk_widget import DeskSessionStore, DeskWidget, build_desk_widget
from baton_relay.ui.image_gallery import ImageGallery


class _QuestionScroll(QScrollArea):
    """Scrolls the picture area and answer controls while Submit stays put."""

    def __init__(self, inner: QWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("questionScroll")
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setWidget(inner)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setMinimumHeight(140)
        viewport = self.viewport()
        viewport.setAutoFillBackground(False)
        viewport.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        viewport.setObjectName("questionScrollViewport")

    def sizeHint(self) -> QSize:
        inner = self.widget()
        if inner is None:
            return super().sizeHint()
        hint = inner.sizeHint()
        return QSize(max(hint.width(), 280), hint.height())

    def minimumSizeHint(self) -> QSize:
        return QSize(200, 140)


class QuestionHost(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("questionHost")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAutoFillBackground(False)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._body: QWidget | None = None
        self._gallery: ImageGallery | None = None
        self._scroll: _QuestionScroll | None = None
        self._desk: DeskWidget | None = None
        self._desk_store = DeskSessionStore()
        self._team_shell: TeamShell | None = None
        self._collect: Callable[[], Any] | None = None
        self._on_submit: Callable[[Any], None] | None = None
        self._locked = True
        self._current_qid: str | None = None

        self._layout.setSpacing(10)

        self.prompt = QLabel("")
        self.prompt.setWordWrap(True)
        self.prompt.setObjectName("challengePrompt")
        self._layout.addWidget(self.prompt)

        self._slot = QVBoxLayout()
        self._slot.setContentsMargins(0, 0, 0, 0)
        self._layout.addLayout(self._slot, 1)

        self._btn_row = QHBoxLayout()
        self.submit_btn = QPushButton("SUBMIT")
        self.submit_btn.setObjectName("primary")
        self.submit_btn.clicked.connect(self._submit)
        self._btn_row.addWidget(self.submit_btn)
        self._btn_row.addStretch(1)
        self._layout.addLayout(self._btn_row)

        self.feedback = QLabel("")
        self.feedback.setObjectName("challengeFeedback")
        self._layout.addWidget(self.feedback)

    def set_team_shell(self, shell: TeamShell | None) -> None:
        self._team_shell = shell

    def set_submit_handler(self, handler: Callable[[Any], None]) -> None:
        self._on_submit = handler

    def set_locked(self, locked: bool) -> None:
        was_locked = self._locked
        self._locked = locked
        self.submit_btn.setEnabled(not locked)
        if self._desk is not None:
            self._desk.set_desk_locked(locked)
            if was_locked and not locked:
                # After baton seat / unlock — don't make them click the shell.
                QTimer.singleShot(0, self.focus_answer)
            return
        if self._body is not None:
            self._body.setEnabled(not locked)
        if self._scroll is not None:
            self._scroll.setEnabled(not locked)

    def focus_answer(self) -> bool:
        """Focus the desk shell when unlocked. Returns True if focus moved there."""
        if self._locked or self._desk is None:
            return False
        self._desk.focus_shell()
        return True

    def clear(self) -> None:
        if self._desk is not None:
            # Snapshot this challenge's terminal before the widget is destroyed.
            self._desk.detach_shell()
        if self._scroll is not None:
            self._scroll.setParent(None)
            self._scroll.deleteLater()
            self._scroll = None
            self._body = None
            self._gallery = None
        elif self._body is not None:
            self._body.setParent(None)
            self._body.deleteLater()
            self._body = None
            self._gallery = None
        self._desk = None
        self._collect = None
        self.prompt.setText("")
        self.feedback.setText("")
        self.submit_btn.show()

    def clear_desk_sessions(self) -> None:
        self._desk_store.clear()

    def show_question(self, question: Question | None) -> None:
        # Same desk challenge still mounted (board miss-click → same tile):
        # keep the live terminal instead of wiping and rebuilding.
        if (
            question is not None
            and isinstance(question, Desk)
            and self._desk is not None
            and self._current_qid == question.id
        ):
            self.prompt.setText(question.prompt)
            self._desk.set_desk_locked(self._locked)
            self.submit_btn.hide()
            if not self._locked:
                QTimer.singleShot(0, self.focus_answer)
            return

        self.clear()
        if question is None:
            self._current_qid = None
            self.prompt.setText("No more questions.")
            return
        # Keep per-challenge flag + terminal_feed for the whole team run so
        # gate/steghide each restore their own scrollback when re-opened.
        self._current_qid = question.id
        self.prompt.setText(question.prompt)

        if isinstance(question, Desk):
            self.prompt.setObjectName("challengePrompt")
            state = self._desk_store.get(question.id)
            body, collect, desk = build_desk_widget(
                question,
                state,
                shell=self._team_shell,
                on_submit=self._submit,
            )
            body.setObjectName("questionBody")
            body.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            self._body = body
            self._desk = desk
            self._collect = collect
            self._slot.addWidget(body)
            desk.set_desk_locked(self._locked)
            self.submit_btn.hide()
            if not self._locked:
                QTimer.singleShot(0, self.focus_answer)
            return

        self.prompt.setObjectName("challengePrompt")
        self.submit_btn.show()
        body, collect = build_answer_widget(question)
        body.setObjectName("questionBody")
        body.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._body = body
        self._collect = collect
        pictures = pictures_for(question.images)
        if pictures:
            gallery = ImageGallery(pictures)
            self._gallery = gallery
            wrap = QWidget()
            wrap.setObjectName("questionScrollBody")
            wrap_layout = QVBoxLayout(wrap)
            wrap_layout.setContentsMargins(0, 0, 0, 0)
            wrap_layout.setSpacing(12)
            wrap_layout.addWidget(gallery)
            wrap_layout.addWidget(body)
            wrap_layout.addStretch(1)
            scroll = _QuestionScroll(wrap)
            self._scroll = scroll
            self._slot.addWidget(scroll)
        else:
            self._slot.addWidget(body)

    def _submit(self) -> None:
        if self._locked or not self._collect or not self._on_submit:
            return
        try:
            answer = self._collect()
        except ValueError as exc:
            self.feedback.setText(str(exc))
            return
        self._on_submit(answer)

    def show_feedback(self, text: str) -> None:
        self.feedback.setText(text)


def build_answer_widget(question: Question) -> tuple[QWidget, Callable[[], Any]]:
    if isinstance(question, MultipleChoice):
        return _mc(question)
    w = QLabel(f"Unsupported widget for type {question.type}")
    return w, lambda: None


def _mc(q: MultipleChoice) -> tuple[QWidget, Callable[[], Any]]:
    root = QWidget()
    layout = QVBoxLayout(root)
    layout.setSpacing(10)
    group = QButtonGroup(root)
    group.setExclusive(True)
    for i, choice in enumerate(q.choices or []):
        btn = QPushButton(f"{chr(65 + i)}.  {choice}")
        btn.setObjectName("choice")
        btn.setCheckable(True)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setMinimumHeight(48)
        group.addButton(btn, i)
        layout.addWidget(btn)

    def collect() -> int:
        id_ = group.checkedId()
        if id_ < 0:
            raise ValueError("Select an answer")
        return id_

    return root, collect
