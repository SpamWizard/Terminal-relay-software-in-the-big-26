"""Dense sky map painted edge-to-edge (equirectangular), not a circular dome."""

from __future__ import annotations

import math
import random

from PySide6.QtCore import QPointF, QTimer, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QRadialGradient
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

_FIELD_COUNT = 16000
_TOP_EXTRA = 6000  # denser band toward the top of the screen (high Dec)


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
            # Bias slightly toward the upper half of the sky map
            dec = math.degrees(math.asin(2.0 * (rng.random() ** 0.75) - 1.0))
        _add(ra, dec)

    # Extra pack for the top of the screen (northern Dec → top in our projection)
    for _ in range(_TOP_EXTRA):
        ra = rng.uniform(0.0, 24.0)
        dec = 25.0 + rng.random() ** 0.55 * 65.0  # ~25° … 90°
        _add(ra, dec)

    return tuple(out)


_FIELD = _build_field()

# Full horizontal wrap period (seconds of wall time) — visible, not nauseating.
_ROTATION_PERIOD_S = 110.0


class StarfieldOverlay(QWidget):
    """Full-bleed rectangular sky; mouse-transparent over solid UI."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._by_name = {n: (ra, dec, mag) for n, ra, dec, mag in _STARS}
        self._t = 0.0
        self._holes: list = []  # QRect regions where stars must not paint (solid UI)
        self._timer = QTimer(self)
        self._timer.setInterval(50)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def set_holes(self, rects: list) -> None:
        """Screen-space rects (in this widget's coords) to keep clear of stars."""
        self._holes = list(rects)
        self.update()

    def _tick(self) -> None:
        self._t += self._timer.interval() / 1000.0
        self.update()

    def _project(
        self, ra_h: float, dec_d: float, lst_h: float, w: float, h: float
    ) -> tuple[float, float]:
        """Equirectangular map — fills the whole rectangle to every edge."""
        lon = ((ra_h - lst_h) % 24.0) / 24.0
        lat = (dec_d + 90.0) / 180.0  # -90..90 → 0..1 (south at bottom)
        sx = lon * w
        sy = (1.0 - lat) * h
        return sx, sy

    def paintEvent(self, event) -> None:  # noqa: N802
        from PySide6.QtGui import QRegion

        painter = QPainter(self)
        w, h = float(self.width()), float(self.height())
        if w < 2 or h < 2:
            return

        # Keep solid menus (e.g. crew entry) free of star sparkle
        if self._holes:
            clip = QRegion(self.rect())
            for hole in self._holes:
                clip = clip.subtracted(QRegion(hole))
            painter.setClipRegion(clip)

        # Soft nebula only (no opaque fill — UI stays solid underneath)
        for cx, cy, r, color in (
            (w * 0.18, h * 0.12, min(w, h) * 0.55, QColor(55, 35, 120, 32)),
            (w * 0.78, h * 0.18, min(w, h) * 0.60, QColor(18, 70, 140, 26)),
            (w * 0.50, h * 0.85, min(w, h) * 0.48, QColor(90, 30, 70, 18)),
        ):
            grad = QRadialGradient(cx, cy, r)
            grad.setColorAt(0.0, color)
            grad.setColorAt(1.0, QColor(0, 0, 0, 0))
            painter.fillRect(self.rect(), grad)

        lst_h = (self._t * (24.0 / _ROTATION_PERIOD_S)) % 24.0

        # Constellation sticks (skip segments that wrap across the seam)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        line_pen = QPen(QColor(150, 190, 255, 38))
        line_pen.setWidthF(1.0)
        painter.setPen(line_pen)
        for a, b in _LINES:
            sa = self._by_name.get(a)
            sb = self._by_name.get(b)
            if not sa or not sb:
                continue
            ax, ay = self._project(sa[0], sa[1], lst_h, w, h)
            bx, by = self._project(sb[0], sb[1], lst_h, w, h)
            if abs(ax - bx) > w * 0.45:
                continue
            painter.drawLine(QPointF(ax, ay), QPointF(bx, by))

        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.setPen(Qt.PenStyle.NoPen)
        hues = (
            (220, 230, 255),
            (255, 245, 230),
            (200, 215, 255),
            (255, 220, 200),
            (230, 238, 255),
        )
        for ra, dec, mag, hue in _FIELD:
            sx, sy = self._project(ra, dec, lst_h, w, h)
            tw = 0.78 + 0.22 * (0.5 + 0.5 * math.sin(self._t * 0.9 + ra * 3.0 + dec))
            alpha = int(min(220, max(16, (175 - mag * 16) * tw)))
            r, g, b = hues[hue]
            painter.setBrush(QColor(r, g, b, alpha))
            if mag < 4.5:
                size = max(1.0, 2.5 - (mag - 3.0) * 0.35)
                painter.drawEllipse(QPointF(sx, sy), size, size)
            else:
                painter.drawRect(int(sx), int(sy), 1, 1)

        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        for name, ra, dec, mag in _STARS:
            sx, sy = self._project(ra, dec, lst_h, w, h)
            size = max(1.2, 4.8 - mag * 0.9)
            twinkle = 0.75 + 0.25 * (
                0.5 + 0.5 * math.sin(self._t * (1.1 + abs(mag) * 0.15) + ra)
            )
            alpha = int(min(255, (215 - mag * 24) * twinkle))
            if mag < 0.2:
                color = QColor(210, 230, 255, alpha)
            elif name in ("Betelgeuse", "Antares", "Aldebaran"):
                color = QColor(255, 190, 150, alpha)
            elif name in ("Rigel", "Spica", "Regulus"):
                color = QColor(190, 210, 255, alpha)
            else:
                color = QColor(230, 238, 255, alpha)
            if mag < 0.8:
                glow = QColor(color.red(), color.green(), color.blue(), max(14, alpha // 6))
                painter.setBrush(glow)
                painter.drawEllipse(QPointF(sx, sy), size * 2.4, size * 2.4)
            painter.setBrush(color)
            painter.drawEllipse(QPointF(sx, sy), size, size)
