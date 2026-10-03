"""Color helpers and person-tint stylesheets."""

from __future__ import annotations

from baton_relay.config import ThemeConfig


def parse_hex(color: str) -> tuple[int, int, int]:
    c = color.strip().lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    if len(c) != 6:
        return (0, 245, 212)
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def to_hex(r: int, g: int, b: int) -> str:
    return f"#{max(0, min(255, r)):02x}{max(0, min(255, g)):02x}{max(0, min(255, b)):02x}"


def mix(a: str, b: str, t: float) -> str:
    """Blend hex colors; t=0 → a, t=1 → b."""
    ar, ag, ab = parse_hex(a)
    br, bg, bb = parse_hex(b)
    return to_hex(
        int(ar + (br - ar) * t),
        int(ag + (bg - ag) * t),
        int(ab + (bb - ab) * t),
    )


def rgba(color: str, alpha: float) -> str:
    r, g, b = parse_hex(color)
    a = max(0.0, min(1.0, alpha))
    return f"rgba({r}, {g}, {b}, {a:.3f})"


def build_stylesheet(theme: ThemeConfig, *, accent: str | None = None) -> str:
    """Full app stylesheet. Optional accent overrides theme accent (person color)."""
    bg = theme.background
    fg = theme.foreground
    ac = accent or theme.accent
    # Keep panels nearly the same as the window bg so scanlines don't band on teal fills
    panel = mix(bg, ac, 0.05)
    panel_border = mix(bg, ac, 0.40)
    input_bg = mix(bg, "#000000", 0.25)
    hover = mix(bg, ac, 0.18)
    muted = mix(fg, bg, 0.45)
    return f"""
    QWidget {{
        background-color: {bg};
        color: {fg};
        font-family: "Cascadia Mono", "Consolas", "Courier New", monospace;
        font-size: 16px;
    }}
    QMainWindow, QDialog {{
        background-color: {bg};
    }}
    QLabel {{
        background-color: transparent;
    }}
    QLabel#brand {{
        color: {ac};
        font-size: 64px;
        font-weight: 700;
        letter-spacing: 6px;
        background-color: transparent;
    }}
    QLabel#headline {{
        color: {fg};
        font-size: 32px;
        font-weight: 600;
        background-color: transparent;
    }}
    QLabel#timerBig {{
        color: {ac};
        font-size: 64px;
        font-weight: 700;
        background-color: transparent;
    }}
    QLabel#muted {{
        color: {muted};
        font-size: 14px;
        background-color: transparent;
    }}
    QLabel#warn {{
        color: #ff6b6b;
        font-size: 20px;
        font-weight: 600;
        background-color: transparent;
    }}
    QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox {{
        background-color: {input_bg};
        border: 1px solid {ac};
        border-radius: 2px;
        padding: 14px 16px;
        color: {fg};
        font-size: 20px;
        min-height: 28px;
        selection-background-color: {ac};
        selection-color: {bg};
    }}
    QPushButton {{
        background-color: transparent;
        border: 1px solid {ac};
        color: {ac};
        padding: 14px 28px;
        border-radius: 2px;
        font-size: 18px;
        font-weight: 600;
    }}
    QPushButton:hover {{
        background-color: {ac};
        color: {bg};
    }}
    QPushButton:disabled {{
        border-color: #334155;
        color: #475569;
    }}
    QPushButton#primary {{
        background-color: {ac};
        color: {bg};
        font-size: 20px;
        padding: 16px 36px;
    }}
    QPushButton#primary:hover {{
        background-color: {mix(ac, "#ffffff", 0.25)};
    }}
    QPushButton#choice {{
        background-color: {input_bg};
        border: 1px solid {panel_border};
        color: {fg};
        text-align: left;
        padding: 14px 18px;
        font-size: 18px;
        font-weight: 500;
    }}
    QPushButton#choice:hover {{
        border-color: {ac};
        color: {fg};
        background-color: {hover};
    }}
    QPushButton#choice:checked {{
        background-color: {ac};
        border-color: {ac};
        color: {bg};
        font-weight: 700;
    }}
    QPushButton#choice:disabled {{
        border-color: #334155;
        color: #475569;
        background-color: {panel};
    }}
    QFrame#panel {{
        background-color: {panel};
        border: 2px solid {panel_border};
        border-radius: 4px;
    }}
    QFrame#startupPanel {{
        background-color: {mix(bg, "#000000", 0.15)};
        border: 1px solid {ac};
        border-radius: 4px;
        min-width: 480px;
        max-width: 640px;
    }}
    QFrame#frozenOverlay {{
        background-color: {rgba(bg, 0.86)};
        border: 2px solid {ac};
    }}
    QFrame#switchOverlay {{
        background-color: {rgba(mix(bg, ac, 0.35), 0.92)};
    }}
    QFrame#switchBox {{
        background-color: {mix(bg, ac, 0.18)};
        border: 5px solid {ac};
        border-radius: 10px;
    }}
    QLabel#switchTitle {{
        color: {ac};
        font-size: 110px;
        font-weight: 800;
        letter-spacing: 14px;
    }}
    QLabel#switchPerson {{
        font-size: 160px;
        font-weight: 800;
    }}
    QLabel#switchSub {{
        color: {fg};
        font-size: 28px;
        font-weight: 600;
    }}
    QListWidget, QComboBox {{
        background-color: {input_bg};
        border: 1px solid {panel_border};
        color: {fg};
        font-size: 18px;
        padding: 6px;
    }}
    QRadioButton, QCheckBox {{
        spacing: 12px;
        color: {fg};
        font-size: 18px;
    }}
    QRadioButton::indicator, QCheckBox::indicator {{
        width: 20px;
        height: 20px;
        border: 1px solid {ac};
        background: {input_bg};
    }}
    QProgressBar {{
        border: 1px solid {panel_border};
        background: {input_bg};
        text-align: center;
        color: {fg};
        height: 18px;
    }}
    QProgressBar::chunk {{
        background-color: {ac};
    }}
    QFrame#correctToast {{
        background-color: {rgba(mix(bg, ac, 0.2), 0.95)};
        border: 2px solid {ac};
        border-radius: 8px;
        min-width: 320px;
    }}
    QLabel#correctTitle {{
        color: {ac};
        background: transparent;
        font-family: "Cascadia Mono", "Consolas", "Courier New", monospace;
        font-size: 56px;
        font-weight: 800;
        letter-spacing: 8px;
    }}
    QLabel#correctSub {{
        color: {fg};
        background: transparent;
        font-family: "Cascadia Mono", "Consolas", "Courier New", monospace;
        font-size: 20px;
        font-weight: 600;
    }}
    QListWidget#orderList {{
        background-color: {input_bg};
        border: 1px solid {panel_border};
        color: {fg};
        font-size: 18px;
        padding: 8px;
        outline: none;
    }}
    QListWidget#orderList::item {{
        padding: 14px 16px;
        margin: 4px 2px;
        border: 1px solid {panel_border};
        border-radius: 4px;
        background: {panel};
    }}
    QListWidget#orderList::item:selected {{
        border-color: {ac};
        background: {hover};
        color: {fg};
    }}
    QListWidget#orderList::item:hover {{
        border-color: {ac};
    }}
    """


def soften(color: str, theme: ThemeConfig, *, amount: float = 0.18) -> str:
    """Calm a person color for chrome without collapsing hues toward one accent."""
    # Mix toward foreground (light) so dark-safe Okabe–Ito colors stay distinguishable
    return mix(color, theme.foreground, amount)


def display_color(color: str, theme: ThemeConfig) -> str:
    """Brighten slightly for big numbers / titles on dark backgrounds."""
    return mix(color, "#ffffff", 0.18)


def game_screen_wash(theme: ThemeConfig, person_color: str) -> str:
    """Subtle room tint — keep hues distinct; borders carry most of the signal."""
    soft = soften(person_color, theme, amount=0.12)
    bg = mix(theme.background, soft, 0.10)
    edge = mix(theme.background, soft, 0.38)
    return f"""
    QWidget#gameScreen {{
        background-color: {bg};
    }}
    QWidget#gameScreen QFrame#panel {{
        background-color: {mix(theme.background, "#000000", 0.18)};
        border: 2px solid {edge};
    }}
    """
