"""Terminal-neon QSS theme."""

from __future__ import annotations

from baton_relay.config import ThemeConfig


def build_stylesheet(theme: ThemeConfig) -> str:
    bg = theme.background
    fg = theme.foreground
    accent = theme.accent
    return f"""
    QWidget {{
        background-color: {bg};
        color: {fg};
        font-family: "Cascadia Mono", "Consolas", "Courier New", monospace;
        font-size: 14px;
    }}
    QMainWindow, QDialog {{
        background-color: {bg};
    }}
    QLabel#brand {{
        color: {accent};
        font-size: 42px;
        font-weight: 700;
        letter-spacing: 4px;
    }}
    QLabel#headline {{
        color: {fg};
        font-size: 28px;
        font-weight: 600;
    }}
    QLabel#timerBig {{
        color: {accent};
        font-size: 48px;
        font-weight: 700;
    }}
    QLabel#muted {{
        color: #8b9bb4;
        font-size: 12px;
    }}
    QLabel#warn {{
        color: #ff6b6b;
        font-size: 18px;
        font-weight: 600;
    }}
    QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox {{
        background-color: #121826;
        border: 1px solid {accent};
        border-radius: 2px;
        padding: 8px;
        color: {fg};
        selection-background-color: {accent};
        selection-color: {bg};
    }}
    QPushButton {{
        background-color: transparent;
        border: 1px solid {accent};
        color: {accent};
        padding: 10px 18px;
        border-radius: 2px;
        font-weight: 600;
    }}
    QPushButton:hover {{
        background-color: {accent};
        color: {bg};
    }}
    QPushButton:disabled {{
        border-color: #334155;
        color: #475569;
    }}
    QPushButton#primary {{
        background-color: {accent};
        color: {bg};
    }}
    QPushButton#primary:hover {{
        background-color: #7af8e4;
    }}
    QFrame#panel {{
        background-color: #0d121c;
        border: 1px solid #1f2a3d;
        border-radius: 4px;
    }}
    QFrame#frozenOverlay {{
        background-color: rgba(10, 14, 20, 220);
        border: 2px solid {accent};
    }}
    QListWidget, QComboBox {{
        background-color: #121826;
        border: 1px solid #1f2a3d;
        color: {fg};
    }}
    QRadioButton, QCheckBox {{
        spacing: 10px;
        color: {fg};
    }}
    QRadioButton::indicator, QCheckBox::indicator {{
        width: 16px;
        height: 16px;
        border: 1px solid {accent};
        background: #121826;
    }}
    QProgressBar {{
        border: 1px solid #1f2a3d;
        background: #121826;
        text-align: center;
        color: {fg};
        height: 18px;
    }}
    QProgressBar::chunk {{
        background-color: {accent};
    }}
    """
