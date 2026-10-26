"""Question answer widgets hosted inside the active game screen."""

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QKeyEvent, QPalette
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from baton_relay.questions.base import Question
from baton_relay.questions.images import pictures_for
from baton_relay.questions.types import (
    Desk,
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
        # Stay as tall as the pictures and answers. Extra panel space stays below Submit.
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
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._body: QWidget | None = None
        self._gallery: ImageGallery | None = None
        self._scroll: _QuestionScroll | None = None
        self._desk: DeskWidget | None = None
        self._desk_store = DeskSessionStore()
        self._collect: Callable[[], Any] | None = None
        self._on_submit: Callable[[Any], None] | None = None
        self._locked = True
        self._current_qid: str | None = None

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
        # Keep the host enabled so the freeze overlay is the gate; still disable controls.
        self.submit_btn.setEnabled(not locked)
        if self._desk is not None:
            self._desk.set_desk_locked(locked)
            return
        if self._body is not None:
            self._body.setEnabled(not locked)
        if self._scroll is not None:
            self._scroll.setEnabled(not locked)

    def clear(self) -> None:
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

    def clear_desk_sessions(self) -> None:
        self._desk_store.clear()

    def show_question(self, question: Question | None) -> None:
        prev = self._current_qid
        self.clear()
        if question is None:
            self._current_qid = None
            if prev:
                self._desk_store.clear(prev)
            self.prompt.setText("No more questions.")
            return
        if prev and prev != question.id:
            self._desk_store.clear(prev)
        self._current_qid = question.id
        self.prompt.setText(question.prompt)

        if isinstance(question, Desk):
            state = self._desk_store.get(question.id)
            body, collect, desk = build_desk_widget(question, state)
            body.setObjectName("questionBody")
            body.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            self._body = body
            self._desk = desk
            self._collect = collect
            self._slot.addWidget(body)
            desk.set_desk_locked(self._locked)
            return

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


class OrderListWidget(QListWidget):
    """Drag-and-drop reorder; Up/Down keys move the selected row."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("orderList")
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setMinimumHeight(220)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down) and self.currentRow() >= 0:
            delta = -1 if event.key() == Qt.Key.Key_Up else 1
            row = self.currentRow()
            new_row = row + delta
            if 0 <= new_row < self.count():
                item = self.takeItem(row)
                self.insertItem(new_row, item)
                self.setCurrentRow(new_row)
            event.accept()
            return
        super().keyPressEvent(event)


def _order(q: PutInOrder) -> tuple[QWidget, Callable[[], Any]]:
    root = QWidget()
    layout = QVBoxLayout(root)
    hint = QLabel("Drag rows to reorder, or select one and press ↑ / ↓  (top = first)")
    hint.setObjectName("muted")
    hint.setWordWrap(True)
    layout.addWidget(hint)
    lst = OrderListWidget()
    for i, item in enumerate(q.items or []):
        li = QListWidgetItem(f"  ≡  {item}")
        li.setData(Qt.ItemDataRole.UserRole, i)
        lst.addItem(li)
    if lst.count():
        lst.setCurrentRow(0)
    layout.addWidget(lst)

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
                "Container challenges are not available yet. "
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
    edit.setObjectName("numberAnswer")
    edit.setPlaceholderText("Type a number")
    edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
    palette = edit.palette()
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor("#d5e4f5"))
    edit.setPalette(palette)
    layout.addWidget(edit)

    def collect() -> float:
        text = edit.text().strip()
        try:
            return float(text)
        except ValueError as exc:
            raise ValueError("Enter a number") from exc

    return root, collect
