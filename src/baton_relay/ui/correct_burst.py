"""Centered toasts: correct / wrong / partial answer bursts."""

from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    QSequentialAnimationGroup,
    Qt,
    Signal,
)
from PySide6.QtWidgets import QFrame, QGraphicsOpacityEffect, QLabel, QVBoxLayout, QWidget


class _ToastBase(QWidget):
    """Fade in / hold / fade out banner. Subclasses set object names."""

    finished = Signal()

    def __init__(
        self,
        parent: QWidget | None,
        *,
        card_name: str,
        title_name: str,
        sub_name: str,
        default_title: str,
    ) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._seq: QSequentialAnimationGroup | None = None

        self._fx = QGraphicsOpacityEffect(self)
        self._fx.setOpacity(0.0)
        self.setGraphicsEffect(self._fx)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 24, 24, 24)
        outer.addStretch(2)

        self.card = QFrame()
        self.card.setObjectName(card_name)
        card_l = QVBoxLayout(self.card)
        card_l.setContentsMargins(56, 32, 56, 32)
        card_l.setSpacing(8)

        self.label = QLabel(default_title)
        self.label.setObjectName(title_name)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_l.addWidget(self.label)

        self.sub = QLabel("")
        self.sub.setObjectName(sub_name)
        self.sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_l.addWidget(self.sub)

        outer.addWidget(self.card, alignment=Qt.AlignmentFlag.AlignHCenter)
        outer.addStretch(3)
        self.hide()

    def _play_anim(
        self,
        title: str,
        sub: str,
        *,
        fade_in_ms: int,
        hold_ms: int,
        fade_out_ms: int,
    ) -> None:
        if self._seq is not None:
            self._seq.stop()
            try:
                self._seq.finished.disconnect(self._done)
            except (TypeError, RuntimeError):
                pass

        self.label.setText(title)
        self.sub.setText(sub)
        if self.parentWidget() is not None:
            self.setGeometry(self.parentWidget().rect())
        self.raise_()
        self.show()
        self._fx.setOpacity(0.0)

        fade_in_ms = max(0, int(fade_in_ms))
        hold_ms = max(0, int(hold_ms))
        fade_out_ms = max(0, int(fade_out_ms))

        fade_in = QPropertyAnimation(self._fx, b"opacity")
        fade_in.setDuration(fade_in_ms)
        fade_in.setStartValue(0.0)
        fade_in.setEndValue(1.0)
        fade_in.setEasingCurve(QEasingCurve.Type.OutCubic)

        hold = QPropertyAnimation(self._fx, b"opacity")
        hold.setDuration(hold_ms)
        hold.setStartValue(1.0)
        hold.setEndValue(1.0)

        fade_out = QPropertyAnimation(self._fx, b"opacity")
        fade_out.setDuration(fade_out_ms)
        fade_out.setStartValue(1.0)
        fade_out.setEndValue(0.0)
        fade_out.setEasingCurve(QEasingCurve.Type.InCubic)

        self._seq = QSequentialAnimationGroup(self)
        self._seq.addAnimation(fade_in)
        self._seq.addAnimation(hold)
        self._seq.addAnimation(fade_out)
        self._seq.finished.connect(self._done)
        self._seq.start()

    def _done(self) -> None:
        self.hide()
        self.finished.emit()


class CorrectBurst(_ToastBase):
    """Soft centered toast: fade in, hold, fade out."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            parent,
            card_name="correctToast",
            title_name="correctTitle",
            sub_name="correctSub",
            default_title="CORRECT",
        )

    def play(
        self,
        points_text: str = "",
        *,
        fade_in_ms: int = 160,
        hold_ms: int = 480,
        fade_out_ms: int = 200,
    ) -> None:
        self._play_anim(
            "CORRECT",
            points_text,
            fade_in_ms=fade_in_ms,
            hold_ms=hold_ms,
            fade_out_ms=fade_out_ms,
        )


class WrongBurst(_ToastBase):
    """Same fade as a correct answer, in red — or amber when the answer was only partial."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            parent,
            card_name="wrongToast",
            title_name="wrongTitle",
            sub_name="wrongSub",
            default_title="WRONG",
        )

    def play(
        self,
        points_text: str = "",
        *,
        partial: bool = False,
        fade_in_ms: int = 160,
        hold_ms: int = 480,
        fade_out_ms: int = 200,
    ) -> None:
        if partial:
            card, title_name, sub_name, title = (
                "partialToast",
                "partialTitle",
                "partialSub",
                "PARTIAL",
            )
        else:
            card, title_name, sub_name, title = (
                "wrongToast",
                "wrongTitle",
                "wrongSub",
                "WRONG",
            )
        self.card.setObjectName(card)
        self.label.setObjectName(title_name)
        self.sub.setObjectName(sub_name)
        for widget in (self.card, self.label, self.sub):
            widget.style().unpolish(widget)
            widget.style().polish(widget)
        self._play_anim(
            title,
            points_text,
            fade_in_ms=fade_in_ms,
            hold_ms=hold_ms,
            fade_out_ms=fade_out_ms,
        )
