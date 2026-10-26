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
    QWidget#questionBody, QWidget#questionScrollBody,
    QWidget#questionHost, QWidget#deskRoot, QFrame#challengeStage {{
        background-color: transparent;
        border: none;
    }}
    QStackedWidget#challengeStack {{
        background-color: transparent;
        border: none;
    }}
    QScrollArea#questionScroll, QWidget#questionScrollViewport {{
        background: transparent;
        border: none;
    }}
    QFrame#imageGallery {{
        background-color: #ffffff;
        border: 1px solid {mix(bg, ac, 0.50)};
        border-radius: 14px;
    }}
    QFrame#imageTile {{
        background-color: #ffffff;
        border: 1px solid {mix("#ffffff", "#000000", 0.12)};
        border-radius: 10px;
    }}
    QFrame#imageTileFlat {{
        background-color: transparent;
        border: none;
    }}
    QLabel#imageCaption {{
        color: #1a1a1a;
        font-size: 14px;
        font-weight: 600;
        background-color: transparent;
    }}
    QScrollArea#questionScroll QScrollBar:vertical {{
        background: transparent;
        width: 10px;
        margin: 6px 2px 6px 0;
    }}
    QScrollArea#questionScroll QScrollBar::handle:vertical {{
        background: {mix(bg, ac, 0.55)};
        border-radius: 4px;
        min-height: 28px;
    }}
    QScrollArea#questionScroll QScrollBar::add-line:vertical,
    QScrollArea#questionScroll QScrollBar::sub-line:vertical {{
        height: 0;
        background: transparent;
    }}
    QScrollArea#questionScroll QScrollBar::add-page:vertical,
    QScrollArea#questionScroll QScrollBar::sub-page:vertical {{
        background: transparent;
    }}
    QLabel#brand {{
        color: {ac};
        font-size: 58px;
        font-weight: 700;
        letter-spacing: 10px;
        background-color: transparent;
    }}
    QLabel#tagline {{
        color: {muted};
        font-size: 16px;
        letter-spacing: 4px;
        background-color: transparent;
    }}
    QLabel#headline {{
        color: {fg};
        font-size: 22px;
        font-weight: 600;
        background-color: transparent;
        padding: 4px 2px 10px 2px;
    }}
    QFrame#statusStrip {{
        background-color: {rgba(mix(bg, "#000000", 0.40), 0.55)};
        border: none;
        border-radius: 8px;
        max-height: 48px;
    }}
    QLabel#statusTeam {{
        color: {fg};
        font-size: 15px;
        font-weight: 600;
        background-color: transparent;
    }}
    QLabel#statusPlayer, QLabel#statusLeg, QLabel#statusGame, QLabel#statusScore {{
        color: {fg};
        font-size: 15px;
        font-weight: 600;
        font-family: "Cascadia Mono", "Consolas", monospace;
        background-color: transparent;
        padding: 0 4px;
    }}
    QLabel#statusState {{
        color: {muted};
        font-size: 12px;
        font-weight: 600;
        letter-spacing: 1px;
        background-color: transparent;
        padding: 0 6px;
    }}
    QPushButton#boardBack {{
        background-color: transparent;
        color: {fg};
        border: 1px solid {mix(fg, bg, 0.45)};
        border-radius: 6px;
        font-size: 13px;
        font-weight: 700;
        letter-spacing: 0.5px;
        padding: 4px 12px;
        max-height: 30px;
    }}
    QPushButton#boardBack:hover {{
        border-color: {ac};
        color: {ac};
    }}
    QLabel#statusStateWarn {{
        color: #ff6b6b;
        font-size: 12px;
        font-weight: 700;
        letter-spacing: 1px;
        background-color: transparent;
        padding: 0 6px;
    }}
    QLabel#statusRoster {{
        color: {muted};
        font-size: 12px;
        background-color: transparent;
        padding: 0 4px 2px 4px;
    }}
    QLabel#statusMessage {{
        color: {muted};
        font-size: 13px;
        background-color: transparent;
        padding: 0 4px;
    }}
    QFrame#challengeStage {{
        background-color: transparent;
        border: none;
    }}
    QLabel#challengePrompt {{
        color: {fg};
        font-size: 17px;
        font-weight: 500;
        background-color: transparent;
        border: none;
        padding: 2px 4px 10px 4px;
    }}
    QLabel#challengeFeedback {{
        color: {muted};
        font-size: 13px;
        background-color: transparent;
        border: none;
        padding: 2px 4px 0 4px;
    }}
    QPushButton#deskSubmit {{
        background-color: {mix(fg, bg, 0.12)};
        color: {fg};
        border: 1px solid {mix(fg, bg, 0.55)};
        border-radius: 8px;
        font-size: 14px;
        font-weight: 600;
        padding: 10px 20px;
        min-width: 96px;
    }}
    QPushButton#deskSubmit:hover {{
        background-color: {mix(fg, bg, 0.22)};
        border-color: {mix(fg, bg, 0.35)};
    }}
    QPushButton#deskSubmit:disabled {{
        background-color: {mix(bg, "#000000", 0.25)};
        color: {muted};
        border-color: {mix(bg, fg, 0.12)};
    }}
    QFrame#deskRail, QFrame#deskPanel, QFrame#deskFlagBar {{
        background-color: transparent;
        border: none;
    }}
    QLabel#deskSection {{
        color: {muted};
        font-size: 11px;
        font-weight: 600;
        letter-spacing: 1.5px;
        background-color: transparent;
    }}
    QLabel#deskHint {{
        color: {mix(fg, bg, 0.55)};
        font-size: 11px;
        background-color: transparent;
    }}
    QLabel#deskPrompt {{
        color: {muted};
        font-size: 16px;
        font-weight: 600;
        background-color: transparent;
        padding: 0 2px;
    }}
    QListWidget#deskFileList {{
        background-color: transparent;
        border: none;
        color: {fg};
        font-size: 14px;
        font-family: "Cascadia Mono", "Consolas", monospace;
        outline: none;
        padding: 2px;
    }}
    QListWidget#deskFileList::item {{
        padding: 8px 10px;
        border-radius: 6px;
        margin: 1px 0;
        border: none;
    }}
    QListWidget#deskFileList::item:selected {{
        background-color: {mix(bg, "#ffffff", 0.10)};
        color: {fg};
    }}
    QListWidget#deskFileList::item:hover {{
        background-color: {mix(bg, "#ffffff", 0.06)};
    }}
    QPlainTextEdit#deskTerminalOut {{
        background-color: {mix(bg, "#000000", 0.42)};
        border: none;
        border-radius: 8px;
        color: {fg};
        padding: 12px 14px;
        font-size: 13px;
        selection-background-color: {mix(bg, "#ffffff", 0.18)};
    }}
    QLineEdit#deskTerminalIn {{
        background-color: {mix(bg, "#000000", 0.38)};
        border: 1px solid {mix(fg, bg, 0.78)};
        border-radius: 8px;
        padding: 10px 14px;
        font-size: 15px;
        min-height: 22px;
        color: {fg};
    }}
    QLineEdit#deskTerminalIn:focus {{
        border: 1px solid {mix(fg, bg, 0.45)};
        background-color: {mix(bg, "#000000", 0.48)};
    }}
    QLineEdit#deskFlagIn {{
        background-color: transparent;
        border: none;
        border-bottom: 1px solid {mix(fg, bg, 0.65)};
        border-radius: 0px;
        padding: 8px 4px;
        font-size: 15px;
        min-height: 22px;
        color: {fg};
    }}
    QLineEdit#deskFlagIn:focus {{
        background-color: transparent;
        border: none;
        border-bottom: 1px solid {mix(fg, bg, 0.35)};
    }}
    QTextBrowser#deskPage {{
        background-color: transparent;
        border: none;
        color: {fg};
        padding: 4px;
    }}
    QSplitter#deskSplitter::handle {{
        background: transparent;
    }}
    QSplitter#deskSplitter::handle:horizontal {{
        width: 8px;
    }}
    QSplitter#deskSplitter::handle:vertical {{
        height: 8px;
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
    QLabel#playerBadge {{
        color: {bg};
        background-color: {ac};
        border-radius: 18px;
        font-size: 18px;
        font-weight: 800;
        min-width: 36px;
        max-width: 48px;
        min-height: 36px;
        padding: 4px 8px;
        qproperty-alignment: AlignCenter;
    }}
    QLabel#rosterLine {{
        color: {fg};
        font-size: 20px;
        font-weight: 600;
        background-color: transparent;
    }}
    QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox {{
        background-color: {input_bg};
        border: 1px solid {ac};
        border-radius: 6px;
        padding: 12px 14px;
        color: {fg};
        font-size: 18px;
        min-height: 26px;
        selection-background-color: {ac};
        selection-color: {bg};
    }}
    QLineEdit#numberAnswer {{
        font-size: 42px;
        font-weight: 700;
        min-height: 84px;
        padding: 18px 24px;
        border: 2px solid {ac};
        border-radius: 10px;
        qproperty-alignment: AlignCenter;
    }}
    QPushButton {{
        background-color: transparent;
        border: 1px solid {ac};
        color: {ac};
        padding: 12px 24px;
        border-radius: 6px;
        font-size: 17px;
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
    QPushButton#ghost {{
        border-color: {panel_border};
        color: {muted};
        font-size: 15px;
        padding: 10px 18px;
    }}
    QPushButton#bindButton {{
        background-color: {input_bg};
        border: 1px solid {panel_border};
        color: {fg};
        padding: 8px 14px;
        font-size: 15px;
        font-weight: 700;
        min-width: 64px;
    }}
    QPushButton#bindButton:hover {{
        border-color: {ac};
        color: {ac};
        background-color: {hover};
    }}
    QPushButton#bindButton:checked {{
        background-color: {ac};
        border-color: {ac};
        color: {bg};
    }}
    QPushButton#bindListening {{
        background-color: {mix(bg, ac, 0.35)};
        border: 2px solid {ac};
        color: {fg};
        padding: 8px 14px;
        font-size: 14px;
        font-weight: 700;
    }}
    QTabWidget::pane {{
        border: 1px solid {panel_border};
        background: {panel};
        border-radius: 6px;
    }}
    QTabBar::tab {{
        background: {input_bg};
        color: {muted};
        border: 1px solid {panel_border};
        padding: 10px 16px;
        margin-right: 4px;
        border-top-left-radius: 6px;
        border-top-right-radius: 6px;
    }}
    QTabBar::tab:selected {{
        color: {bg};
        background: {ac};
        border-color: {ac};
    }}
    QGroupBox {{
        border: 1px solid {panel_border};
        border-radius: 6px;
        margin-top: 14px;
        padding-top: 12px;
        color: {fg};
        font-weight: 600;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 12px;
        padding: 0 6px;
        color: {ac};
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
    QPushButton#categoryTile {{
        background-color: {input_bg};
        border: 2px solid {panel_border};
        border-radius: 10px;
        color: {fg};
        font-size: 22px;
        font-weight: 700;
        letter-spacing: 1px;
        padding: 18px 12px;
    }}
    QPushButton#categoryTile:hover {{
        border-color: {ac};
        background-color: {hover};
        color: {ac};
    }}
    QPushButton#categoryTile:pressed {{
        background-color: {ac};
        color: {bg};
        border-color: {ac};
    }}
    QFrame#panel {{
        background-color: {panel};
        border: 2px solid {panel_border};
        border-radius: 8px;
    }}
    QFrame#startupPanel {{
        background-color: {mix(bg, "#000000", 0.22)};
        border: 1px solid {ac};
        border-radius: 12px;
        min-width: 560px;
        max-width: 720px;
    }}
    QFrame#playerRow {{
        background-color: {mix(bg, "#000000", 0.12)};
        border: 1px solid {panel_border};
        border-radius: 8px;
    }}
    QFrame#frozenOverlay {{
        background-color: {rgba(bg, 0.86)};
        border: 2px solid {ac};
    }}
    QFrame#switchOverlay {{
        background-color: {rgba(mix(bg, ac, 0.28), 0.93)};
    }}
    QFrame#switchBox {{
        background-color: {mix(bg, ac, 0.16)};
        border: 4px solid {ac};
        border-radius: 14px;
    }}
    QLabel#switchTitle {{
        color: {ac};
        font-size: 72px;
        font-weight: 800;
        letter-spacing: 10px;
    }}
    QLabel#switchPerson {{
        font-size: 84px;
        font-weight: 800;
    }}
    QLabel#switchSub {{
        color: {fg};
        font-size: 22px;
        font-weight: 600;
    }}
    QLabel#switchRoster {{
        color: {muted};
        font-size: 16px;
        font-weight: 500;
    }}
    QListWidget, QComboBox {{
        background-color: {input_bg};
        border: 1px solid {panel_border};
        color: {fg};
        font-size: 16px;
        padding: 6px;
        border-radius: 6px;
    }}
    QPlainTextEdit#activityLog {{
        background-color: {mix(bg, "#000000", 0.22)};
        border: 1px solid {mix(bg, ac, 0.22)};
        border-radius: 4px;
        color: {fg};
        font-family: "Segoe UI", "Segoe UI Variable", sans-serif;
        font-size: 15px;
        padding: 10px 12px;
        selection-background-color: {mix(bg, ac, 0.25)};
        selection-color: {fg};
    }}
    QRadioButton, QCheckBox {{
        spacing: 12px;
        color: {fg};
        font-size: 18px;
    }}
    QRadioButton::indicator, QCheckBox::indicator {{
        width: 22px;
        height: 22px;
        border: 2px solid {ac};
        border-radius: 4px;
        background: {input_bg};
    }}
    QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
        background-color: {ac};
        border-color: {ac};
        image: none;
    }}
    QCheckBox::indicator:unchecked:hover, QRadioButton::indicator:unchecked:hover {{
        background-color: {hover};
    }}
    QPushButton#xboxToggle {{
        background-color: {input_bg};
        border: 2px solid {panel_border};
        color: {muted};
        padding: 12px 20px;
        font-size: 18px;
        font-weight: 800;
        letter-spacing: 1px;
        min-width: 220px;
    }}
    QPushButton#xboxToggle:checked {{
        background-color: {ac};
        border-color: {ac};
        color: {bg};
    }}
    QPushButton#xboxToggle:hover {{
        border-color: {ac};
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
    QFrame#wrongToast {{
        background-color: {rgba(mix(bg, "#ff6b6b", 0.22), 0.95)};
        border: 2px solid #ff6b6b;
        border-radius: 8px;
        min-width: 320px;
    }}
    QLabel#wrongTitle {{
        color: #ff6b6b;
        background: transparent;
        font-family: "Cascadia Mono", "Consolas", "Courier New", monospace;
        font-size: 56px;
        font-weight: 800;
        letter-spacing: 8px;
    }}
    QLabel#wrongSub {{
        color: {fg};
        background: transparent;
        font-family: "Cascadia Mono", "Consolas", "Courier New", monospace;
        font-size: 20px;
        font-weight: 600;
    }}
    QFrame#partialToast {{
        background-color: {rgba(mix(bg, "#ff9f1a", 0.22), 0.95)};
        border: 2px solid #ff9f1a;
        border-radius: 8px;
        min-width: 320px;
    }}
    QLabel#partialTitle {{
        color: #ff9f1a;
        background: transparent;
        font-family: "Cascadia Mono", "Consolas", "Courier New", monospace;
        font-size: 56px;
        font-weight: 800;
        letter-spacing: 8px;
    }}
    QLabel#partialSub {{
        color: {fg};
        background: transparent;
        font-family: "Cascadia Mono", "Consolas", "Courier New", monospace;
        font-size: 20px;
        font-weight: 600;
    }}
    QFrame#overrideToast {{
        background-color: rgba(40, 18, 8, 0.96);
        border: 3px solid #ff9f1a;
        border-radius: 8px;
        min-width: 420px;
    }}
    QLabel#overrideTitle {{
        color: #ff9f1a;
        background: transparent;
        font-family: "Cascadia Mono", "Consolas", "Courier New", monospace;
        font-size: 44px;
        font-weight: 800;
        letter-spacing: 4px;
    }}
    QLabel#overrideSub {{
        color: #ffe0b0;
        background: transparent;
        font-family: "Cascadia Mono", "Consolas", "Courier New", monospace;
        font-size: 18px;
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
    """Subtle person wash — background only, no neon panel outlines."""
    soft = soften(person_color, theme, amount=0.10)
    bg = mix(theme.background, soft, 0.18)
    return f"""
    QWidget#gameScreen {{
        background-color: {bg};
    }}
    QWidget#gameScreen QLabel {{
        background-color: transparent;
    }}
    """


def person_window_stylesheet(theme: ThemeConfig, person_color: str) -> str:
    """Base app stylesheet + quiet window wash (keep theme accent, don't neon everything)."""
    soft = soften(person_color, theme, amount=0.12)
    bg = mix(theme.background, soft, 0.16)
    # Keep the configured theme accent for rare CTAs — not the baton person color.
    base = build_stylesheet(theme)
    return (
        base
        + f"""
    QMainWindow, QStackedWidget {{
        background-color: {bg};
    }}
    """
    )
