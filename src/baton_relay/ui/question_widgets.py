"""Question answer widgets hosted inside the active game screen."""

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from baton_relay.questions.base import Question
from baton_relay.questions.types import (
    FillBlank,
    Flag,
    HandsOn,
    MatchUp,
    MultipleChoice,
    Numeric,
    PutInOrder,
    SelectAll,
    ShortAnswer,
)


class QuestionHost(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._body: QWidget | None = None
        self._collect: Callable[[], Any] | None = None
        self._on_submit: Callable[[Any], None] | None = None
        self._locked = True

        self.prompt = QLabel("")
        self.prompt.setWordWrap(True)
        self.prompt.setObjectName("headline")
        self._layout.addWidget(self.prompt)

        self._slot = QVBoxLayout()
        self._layout.addLayout(self._slot)

        btn_row = QHBoxLayout()
        self.submit_btn = QPushButton("SUBMIT")
        self.submit_btn.setObjectName("primary")
        self.submit_btn.clicked.connect(self._submit)
        btn_row.addWidget(self.submit_btn)
        btn_row.addStretch(1)
        self._layout.addLayout(btn_row)

        self.feedback = QLabel("")
        self.feedback.setObjectName("muted")
        self._layout.addWidget(self.feedback)

    def set_submit_handler(self, handler: Callable[[Any], None]) -> None:
        self._on_submit = handler

    def set_locked(self, locked: bool) -> None:
        self._locked = locked
        self.setEnabled(not locked)
        self.submit_btn.setEnabled(not locked)

    def clear(self) -> None:
        if self._body is not None:
            self._body.setParent(None)
            self._body.deleteLater()
            self._body = None
        self._collect = None
        self.prompt.setText("")
        self.feedback.setText("")

    def show_question(self, question: Question | None) -> None:
        self.clear()
        if question is None:
            self.prompt.setText("No more questions.")
            return
        self.prompt.setText(question.prompt)
        body, collect = build_answer_widget(question)
        self._body = body
        self._collect = collect
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
    if isinstance(question, SelectAll):
        return _select_all(question)
    if isinstance(question, PutInOrder):
        return _order(question)
    if isinstance(question, MatchUp):
        return _match(question)
    if isinstance(question, (ShortAnswer, FillBlank, Flag, HandsOn)):
        return _text(question)
    if isinstance(question, Numeric):
        return _numeric(question)
    # Fallback
    w = QLabel(f"Unsupported widget for type {question.type}")
    return w, lambda: None


def _mc(q: MultipleChoice) -> tuple[QWidget, Callable[[], Any]]:
    root = QWidget()
    layout = QVBoxLayout(root)
    layout.setSpacing(10)
    group = QButtonGroup(root)
    group.setExclusive(True)
    buttons: list[QPushButton] = []
    for i, choice in enumerate(q.choices or []):
        btn = QPushButton(f"{chr(65 + i)}.  {choice}")
        btn.setObjectName("choice")
        btn.setCheckable(True)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setMinimumHeight(48)
        group.addButton(btn, i)
        buttons.append(btn)
        layout.addWidget(btn)

    def collect() -> int:
        id_ = group.checkedId()
        if id_ < 0:
            raise ValueError("Select an answer")
        return id_

    return root, collect


def _select_all(q: SelectAll) -> tuple[QWidget, Callable[[], Any]]:
    root = QWidget()
    layout = QVBoxLayout(root)
    layout.setSpacing(10)
    buttons: list[QPushButton] = []
    for i, choice in enumerate(q.choices or []):
        btn = QPushButton(f"{chr(65 + i)}.  {choice}")
        btn.setObjectName("choice")
        btn.setCheckable(True)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setMinimumHeight(48)
        buttons.append(btn)
        layout.addWidget(btn)

    def collect() -> list[int]:
        return [i for i, b in enumerate(buttons) if b.isChecked()]

    return root, collect


def _order(q: PutInOrder) -> tuple[QWidget, Callable[[], Any]]:
    root = QWidget()
    layout = QVBoxLayout(root)
    layout.addWidget(QLabel("Use Up/Down to arrange (first = top):"))
    lst = QListWidget()
    # Store original index in UserRole
    for i, item in enumerate(q.items or []):
        li = QListWidgetItem(item)
        li.setData(Qt.ItemDataRole.UserRole, i)
        lst.addItem(li)
    layout.addWidget(lst)
    row = QHBoxLayout()
    up = QPushButton("Up")
    down = QPushButton("Down")

    def move(delta: int) -> None:
        row_i = lst.currentRow()
        if row_i < 0:
            return
        new_i = row_i + delta
        if new_i < 0 or new_i >= lst.count():
            return
        item = lst.takeItem(row_i)
        lst.insertItem(new_i, item)
        lst.setCurrentRow(new_i)

    up.clicked.connect(lambda: move(-1))
    down.clicked.connect(lambda: move(1))
    row.addWidget(up)
    row.addWidget(down)
    row.addStretch(1)
    layout.addLayout(row)

    def collect() -> list[int]:
        return [lst.item(i).data(Qt.ItemDataRole.UserRole) for i in range(lst.count())]

    return root, collect


def _match(q: MatchUp) -> tuple[QWidget, Callable[[], Any]]:
    root = QWidget()
    layout = QVBoxLayout(root)
    combos: list[QComboBox] = []
    right = q.right or []
    for i, left in enumerate(q.left or []):
        row = QHBoxLayout()
        row.addWidget(QLabel(left), 1)
        combo = QComboBox()
        combo.addItem("—", None)
        for j, r in enumerate(right):
            combo.addItem(r, j)
        combos.append(combo)
        row.addWidget(combo, 1)
        layout.addLayout(row)

    def collect() -> dict[str, int]:
        out: dict[str, int] = {}
        for i, combo in enumerate(combos):
            val = combo.currentData()
            if val is None:
                raise ValueError("Match all items")
            out[str(i)] = int(val)
        return out

    return root, collect


def _text(q: Question) -> tuple[QWidget, Callable[[], Any]]:
    root = QWidget()
    layout = QVBoxLayout(root)
    if isinstance(q, HandsOn):
        layout.addWidget(
            QLabel(
                "Hands-on containers ship in a later phase. "
                "If a practice flag is configured, enter it below."
            )
        )
    edit = QLineEdit()
    edit.setPlaceholderText("Answer…")
    layout.addWidget(edit)

    def collect() -> str:
        text = edit.text()
        if not text.strip():
            raise ValueError("Enter an answer")
        return text

    return root, collect


def _numeric(q: Numeric) -> tuple[QWidget, Callable[[], Any]]:
    root = QWidget()
    layout = QVBoxLayout(root)
    edit = QLineEdit()
    edit.setPlaceholderText("Number…")
    layout.addWidget(edit)

    def collect() -> float:
        text = edit.text().strip()
        try:
            return float(text)
        except ValueError as exc:
            raise ValueError("Enter a number") from exc

    return root, collect
