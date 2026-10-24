"""Tiled picture area shown with a question's prompt text."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from baton_relay.questions.images import QuestionImage, gallery_rows


class ImageTile(QFrame):
    """One picture, centered on a dark mat, with an optional caption."""

    def __init__(
        self,
        image: QuestionImage,
        parent: QWidget | None = None,
        *,
        reserve_caption: bool = False,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("imageTile")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumWidth(0)
        self._pixmap = QPixmap(image.path)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self.picture = QLabel()
        self.picture.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.picture.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.picture.setMinimumSize(0, 0)
        layout.addWidget(self.picture, 1)

        self.caption = QLabel(image.caption)
        self.caption.setObjectName("imageCaption")
        self.caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.caption.setWordWrap(True)
        # Keep picture bottoms aligned when only some tiles have a caption.
        self.caption.setVisible(reserve_caption)
        if reserve_caption:
            self.caption.setFixedHeight(36)
        layout.addWidget(self.caption)

        if self._pixmap.isNull():
            self.picture.setObjectName("muted")
            self.picture.setText("Couldn't read this picture")
            self.picture.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._fit()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        QTimer.singleShot(0, self._fit)

    def _fit(self) -> None:
        if self._pixmap.isNull():
            return
        # showEvent defers _fit with a 0ms timer; the tile may already be gone.
        try:
            picture = self.picture
            target = picture.size()
        except RuntimeError:
            return
        if target.width() < 8 or target.height() < 8:
            return
        dpr = self.devicePixelRatioF()
        scaled = self._pixmap.scaled(
            max(1, int(target.width() * dpr)),
            max(1, int(target.height() * dpr)),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        scaled.setDevicePixelRatio(dpr)
        try:
            picture.setPixmap(scaled)
        except RuntimeError:
            return


class ImageGallery(QFrame):
    """One framed area. Pictures tile 1–8 across balanced, centered rows."""

    def __init__(self, images: list[QuestionImage], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("imageGallery")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        rows = gallery_rows(len(images))
        max_cols = max(rows)
        has_caption = any(image.caption for image in images)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(10)

        self.tiles: list[ImageTile] = []
        index = 0
        solo = len(images) == 1
        for count in rows:
            row = QHBoxLayout()
            row.setSpacing(10)
            side = 0 if solo else max_cols - count
            if side:
                row.addStretch(side)
            for _ in range(count):
                tile = ImageTile(images[index], reserve_caption=has_caption)
                if solo:
                    # One picture uses the outer frame only, so it doesn't sit in a second card.
                    tile.setObjectName("imageTileFlat")
                index += 1
                self.tiles.append(tile)
                row.addWidget(tile, 1)
            if side:
                row.addStretch(side)
            outer.addLayout(row, 1)

        row_h = 236 if len(rows) == 1 else 148
        if has_caption:
            row_h += 32
        height = 24 + len(rows) * row_h + 10 * (len(rows) - 1)
        self.setFixedHeight(height)
