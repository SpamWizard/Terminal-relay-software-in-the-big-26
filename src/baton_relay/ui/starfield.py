"""Dense sky map — cached pixmap, scrolled each frame (no per-frame star redraw)."""

from __future__ import annotations

import math
import random

from PySide6.QtCore import QPointF, QRect, QTimer, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap, QRadialGradient, QRegion
from PySide6.QtWidgets import QWidget

# Bright stars: name, RA (hours), Dec (deg), visual magnitude (J2000 approx)
_STARS: tuple[tuple[str, float, float, float], ...] = (
    ("Sirius", 6.7525, -16.7161, -1.46),
    ("Canopus", 6.3992, -52.6956, -0.74),
    ("Rigil Kentaurus", 14.6601, -60.8339, -0.27),
    ("Arcturus", 14.2610, 19.1824, -0.05),
    ("Vega", 18.6156, 38.7837, 0.03),
    ("Capella", 5.2782, 45.9980, 0.08),
    ("Rigel", 5.2423, -8.2016, 0.13),
    ("Procyon", 7.6550, 5.2250, 0.34),
    ("Betelgeuse", 5.9195, 7.4071, 0.42),
    ("Achernar", 1.6286, -57.2367, 0.46),
    ("Hadar", 14.0637, -60.3730, 0.61),
    ("Altair", 19.8464, 8.8683, 0.76),
    ("Acrux", 12.4433, -63.0991, 0.77),
    ("Aldebaran", 4.5987, 16.5093, 0.85),
    ("Antares", 16.4901, -26.4319, 0.96),
    ("Spica", 13.4199, -11.1613, 0.97),
    ("Pollux", 7.7553, 28.0262, 1.14),
    ("Fomalhaut", 22.9608, -29.6222, 1.16),
    ("Deneb", 20.6905, 45.2803, 1.25),
    ("Mimosa", 12.7954, -59.6888, 1.25),
    ("Regulus", 10.1395, 11.9672, 1.35),
    ("Adhara", 6.9771, -28.9721, 1.50),
    ("Castor", 7.5766, 31.8883, 1.58),
    ("Gacrux", 12.5194, -57.1132, 1.63),
    ("Shaula", 17.5601, -37.1038, 1.62),
    ("Bellatrix", 5.4188, 6.3497, 1.64),
    ("Elnath", 5.4382, 28.6079, 1.65),
    ("Miaplacidus", 9.2200, -69.7172, 1.67),
    ("Alnilam", 5.6036, -1.2019, 1.69),
    ("Alnitak", 5.6793, -1.9426, 1.74),
    ("Alioth", 12.9003, 55.9598, 1.76),
    ("Dubhe", 11.0621, 61.7510, 1.79),
    ("Mirfak", 3.4054, 49.8612, 1.79),
    ("Wezen", 7.1399, -26.3932, 1.83),
    ("Sadr", 20.3705, 40.2567, 2.23),
    ("Avior", 8.3752, -59.5095, 1.86),
    ("Alkaid", 13.7923, 49.3133, 1.85),
    ("Menkalinan", 5.9910, 44.9474, 1.90),
    ("Atria", 16.8111, -69.0277, 1.91),
    ("Alhena", 6.6286, 16.3993, 1.93),
    ("Peacock", 20.4275, -56.7351, 1.94),
    ("Alsephina", 8.7450, -54.7086, 1.95),
    ("Mirzam", 6.3783, -17.9559, 1.98),
    ("Polaris", 2.5303, 89.2641, 1.98),
    ("Alphard", 9.4598, -8.6586, 1.99),
    ("Hamal", 2.1195, 23.4628, 2.01),
    ("Diphda", 0.7265, -17.9866, 2.04),
    ("Nunki", 18.9211, -26.2967, 2.05),
    ("Menkent", 14.1110, -36.3681, 2.06),
    ("Alpheratz", 0.1398, 29.0906, 2.07),
    ("Mirach", 1.1622, 35.6206, 2.07),
    ("Kochab", 14.8451, 74.1555, 2.07),
    ("Saiph", 5.7959, -9.6696, 2.07),
    ("Denebola", 11.8177, 14.5720, 2.14),
    ("Algieba", 10.3328, 19.8416, 2.01),
    ("Aspidiske", 9.1333, -43.4326, 2.21),
    ("Eltanin", 17.9434, 51.4889, 2.24),
    ("Mintaka", 5.5334, -0.2991, 2.25),
    ("Schedar", 0.6751, 56.5373, 2.24),
    ("Caph", 0.1529, 59.1498, 2.28),
    ("Merak", 11.0307, 56.3824, 2.37),
    ("Phecda", 11.8972, 53.6948, 2.41),
    ("Megrez", 12.2571, 57.0326, 3.30),
    ("Mizar", 13.3987, 54.9254, 2.23),
    ("Alcyone", 3.7914, 24.1051, 2.85),
    ("Enif", 21.7364, 9.8750, 2.38),
    ("Scheat", 23.0629, 28.0828, 2.44),
    ("Markab", 23.0793, 15.2053, 2.49),
    ("Algenib", 0.2206, 15.1836, 2.83),
    ("Ruchbah", 1.4302, 60.2353, 2.66),
    ("Segin", 1.9066, 63.6700, 3.35),
    ("Naos", 8.0597, -40.0031, 2.21),
    ("Albireo", 19.5120, 27.9597, 3.05),
    ("Gienah", 12.2634, -17.5419, 2.58),
    ("Zubeneschamali", 15.2827, -9.3829, 2.61),
    ("Zubenelgenubi", 14.8478, -16.0418, 2.75),
    ("Rasalhague", 17.5822, 12.5600, 2.08),
    ("Kaus Australis", 18.4029, -34.3843, 1.79),
    ("Nashira", 21.6680, -16.6623, 3.68),
    ("Deneb Algedi", 21.7840, -16.1273, 2.85),
)

_LINES: tuple[tuple[str, str], ...] = (
    ("Betelgeuse", "Bellatrix"),
    ("Bellatrix", "Mintaka"),
    ("Mintaka", "Alnilam"),
    ("Alnilam", "Alnitak"),
    ("Alnitak", "Saiph"),
    ("Saiph", "Rigel"),
    ("Rigel", "Mintaka"),
    ("Betelgeuse", "Alnitak"),
    ("Dubhe", "Merak"),
    ("Merak", "Phecda"),
    ("Phecda", "Megrez"),
    ("Megrez", "Alioth"),
    ("Alioth", "Mizar"),
    ("Mizar", "Alkaid"),
    ("Megrez", "Dubhe"),
    ("Caph", "Schedar"),
    ("Schedar", "Ruchbah"),
    ("Ruchbah", "Segin"),
    ("Vega", "Deneb"),
    ("Deneb", "Altair"),
    ("Altair", "Vega"),
    ("Deneb", "Sadr"),
    ("Sadr", "Albireo"),
    ("Regulus", "Algieba"),
    ("Algieba", "Denebola"),
    ("Antares", "Shaula"),
    ("Acrux", "Mimosa"),
    ("Mimosa", "Gacrux"),
    ("Gacrux", "Acrux"),
    ("Rigil Kentaurus", "Hadar"),
    ("Markab", "Scheat"),
    ("Scheat", "Alpheratz"),
    ("Alpheratz", "Algenib"),
    ("Algenib", "Markab"),
    ("Alpheratz", "Mirach"),
    ("Aldebaran", "Elnath"),
    ("Aldebaran", "Alcyone"),
    ("Castor", "Pollux"),
    ("Pollux", "Alhena"),
    ("Deneb Algedi", "Nashira"),
    ("Zubenelgenubi", "Zubeneschamali"),
    ("Kaus Australis", "Nunki"),
    ("Capella", "Menkalinan"),
    ("Sirius", "Mirzam"),
    ("Sirius", "Adhara"),
)

_FIELD_COUNT = 14000
_TOP_EXTRA = 5000
_ROTATION_PERIOD_S = 110.0
_HUES = (
    (220, 230, 255),
    (255, 245, 230),
    (200, 215, 255),
    (255, 220, 200),
    (230, 238, 255),
)


def _build_field() -> tuple[tuple[float, float, float, int], ...]:
    rng = random.Random(0x57415253)
    out: list[tuple[float, float, float, int]] = []

    def _add(ra: float, dec: float) -> None:
        u = rng.random()
        mag = 3.2 + (u**0.45) * 5.5
        hue = rng.randint(0, 4)
        out.append((ra, dec, mag, hue))

    for _ in range(_FIELD_COUNT):
        if rng.random() < 0.55:
            ra = rng.uniform(0.0, 24.0)
            ridge = 20.0 * math.sin(ra * 0.55) - 5.0 * math.cos(ra * 1.1)
            dec = max(-90.0, min(90.0, ridge + rng.gauss(0.0, 12.0)))
        else:
            ra = rng.uniform(0.0, 24.0)
            dec = math.degrees(math.asin(2.0 * (rng.random() ** 0.75) - 1.0))
        _add(ra, dec)

    for _ in range(_TOP_EXTRA):
        ra = rng.uniform(0.0, 24.0)
        dec = 25.0 + rng.random() ** 0.55 * 65.0
        _add(ra, dec)

    return tuple(out)


_FIELD = _build_field()


def _project(ra_h: float, dec_d: float, w: float, h: float) -> tuple[float, float]:
    """Equirectangular at LST=0 — scrolling provides rotation."""
    lon = (ra_h % 24.0) / 24.0
    lat = (dec_d + 90.0) / 180.0
    return lon * w, (1.0 - lat) * h


class StarfieldOverlay(QWidget):
    """Full-bleed sky rendered once to a pixmap, then scrolled smoothly."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._by_name = {n: (ra, dec, mag) for n, ra, dec, mag in _STARS}
        self._t = 0.0
        self._holes: list[QRect] = []
        self._subtle = False
        self._scrolling = True
        self._cache: QPixmap | None = None
        self._cache_key: tuple[int, int, bool, float] | None = None
        self._timer = QTimer(self)
        # ~30 fps is plenty when each frame is just two blits
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def set_holes(self, rects: list) -> None:
        self._holes = list(rects)
        self.update()

    def set_subtle(self, subtle: bool) -> None:
        if subtle == self._subtle:
            return
        self._subtle = subtle
        self._cache = None  # rebuild at new opacity
        self.update()

    def set_scrolling(self, enabled: bool) -> None:
        """Freeze sky drift during the relay so panels stay still."""
        if enabled == self._scrolling:
            return
        self._scrolling = enabled
        if not enabled:
            self.update()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._cache = None

    def _tick(self) -> None:
        if not self._scrolling:
            return
        self._t += self._timer.interval() / 1000.0
        self.update()

    def _ensure_cache(self) -> QPixmap | None:
        w, h = self.width(), self.height()
        if w < 2 or h < 2:
            return None
        dpr = float(self.devicePixelRatioF())
        key = (w, h, self._subtle, dpr)
        if self._cache is not None and self._cache_key == key:
            return self._cache

        pm = QPixmap(max(1, int(w * dpr)), max(1, int(h * dpr)))
        pm.setDevicePixelRatio(dpr)
        pm.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pm)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        dim = 0.35 if self._subtle else 1.0
        fw, fh = float(w), float(h)

        for cx, cy, r, color in (
            (fw * 0.18, fh * 0.12, min(fw, fh) * 0.55, QColor(55, 35, 120, int(32 * dim))),
            (fw * 0.78, fh * 0.18, min(fw, fh) * 0.60, QColor(18, 70, 140, int(26 * dim))),
            (fw * 0.50, fh * 0.85, min(fw, fh) * 0.48, QColor(90, 30, 70, int(18 * dim))),
        ):
            grad = QRadialGradient(cx, cy, r)
            grad.setColorAt(0.0, color)
            grad.setColorAt(1.0, QColor(0, 0, 0, 0))
            painter.fillRect(0, 0, w, h, grad)

        line_a = int(38 * dim)
        if line_a > 0:
            line_pen = QPen(QColor(150, 190, 255, line_a))
            line_pen.setWidthF(1.0)
            painter.setPen(line_pen)
            for a, b in _LINES:
                sa = self._by_name.get(a)
                sb = self._by_name.get(b)
                if not sa or not sb:
                    continue
                ax, ay = _project(sa[0], sa[1], fw, fh)
                bx, by = _project(sb[0], sb[1], fw, fh)
                if abs(ax - bx) > fw * 0.45:
                    continue
                painter.drawLine(QPointF(ax, ay), QPointF(bx, by))

        painter.setPen(Qt.PenStyle.NoPen)
        step = 3 if self._subtle else 1
        for i, (ra, dec, mag, hue) in enumerate(_FIELD):
            if i % step:
                continue
            sx, sy = _project(ra, dec, fw, fh)
            alpha = int(min(200, max(14, 175 - mag * 16)) * dim)
            if alpha < 8:
                continue
            r, g, b = _HUES[hue]
            painter.setBrush(QColor(r, g, b, alpha))
            if mag < 4.5:
                size = max(1.0, 2.4 - (mag - 3.0) * 0.35)
                painter.drawEllipse(QPointF(sx, sy), size, size)
            else:
                painter.drawRect(int(sx), int(sy), 1, 1)

        for name, ra, dec, mag in _STARS:
            sx, sy = _project(ra, dec, fw, fh)
            size = max(1.0, (4.8 - mag * 0.9) * (0.75 if self._subtle else 1.0))
            alpha = int(min(240, max(20, 215 - mag * 24)) * dim)
            if mag < 0.2:
                color = QColor(210, 230, 255, alpha)
            elif name in ("Betelgeuse", "Antares", "Aldebaran"):
                color = QColor(255, 190, 150, alpha)
            elif name in ("Rigel", "Spica", "Regulus"):
                color = QColor(190, 210, 255, alpha)
            else:
                color = QColor(230, 238, 255, alpha)
            if mag < 0.8 and not self._subtle:
                glow = QColor(color.red(), color.green(), color.blue(), max(12, alpha // 6))
                painter.setBrush(glow)
                painter.drawEllipse(QPointF(sx, sy), size * 2.4, size * 2.4)
            painter.setBrush(color)
            painter.drawEllipse(QPointF(sx, sy), size, size)

        painter.end()
        self._cache = pm
        self._cache_key = key
        return pm

    def paintEvent(self, event) -> None:  # noqa: N802
        cache = self._ensure_cache()
        if cache is None:
            return
        w, h = self.width(), self.height()
        painter = QPainter(self)
        if self._holes:
            clip = QRegion(self.rect())
            for hole in self._holes:
                clip = clip.subtracted(QRegion(hole))
            painter.setClipRegion(clip)

        # Horizontal wrap scroll — two blits, no per-frame star math
        offset = int((self._t / _ROTATION_PERIOD_S) * w) % max(1, w)
        painter.drawPixmap(-offset, 0, cache)
        painter.drawPixmap(-offset + w, 0, cache)
