"""Clean correct-answer toast."""

from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    QSequentialAnimationGroup,
    Qt,
    Signal,
)
from PySide6.QtWidgets import QFrame, QGraphicsOpacityEffect, QLabel, QVBoxLayout, QWidget


class CorrectBurst(QWidget):
    """Soft centered toast: fade in, hold, fade out."""

    finished = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
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
        self.card.setObjectName("correctToast")
        card_l = QVBoxLayout(self.card)
        card_l.setContentsMargins(56, 32, 56, 32)
        card_l.setSpacing(8)

        self.label = QLabel("CORRECT")
        self.label.setObjectName("correctTitle")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_l.addWidget(self.label)

        self.sub = QLabel("")
        self.sub.setObjectName("correctSub")
        self.sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_l.addWidget(self.sub)

        outer.addWidget(self.card, alignment=Qt.AlignmentFlag.AlignHCenter)
        outer.addStretch(3)
        self.hide()

    def play(
        self,
        points_text: str = "",
        *,
        fade_in_ms: int = 160,
        hold_ms: int = 480,
        fade_out_ms: int = 200,
    ) -> None:
        if self._seq is not None:
            self._seq.stop()
            try:
                self._seq.finished.disconnect(self._done)
            except (TypeError, RuntimeError):
                pass

        self.sub.setText(points_text)
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
