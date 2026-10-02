"""Terminal-neon QSS theme sized for fullscreen / kiosk displays."""

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
        font-size: 16px;
    }}
    QMainWindow, QDialog {{
        background-color: {bg};
    }}
    QLabel#brand {{
        color: {accent};
        font-size: 64px;
        font-weight: 700;
        letter-spacing: 6px;
    }}
    QLabel#headline {{
        color: {fg};
        font-size: 32px;
        font-weight: 600;
    }}
    QLabel#timerBig {{
        color: {accent};
        font-size: 64px;
        font-weight: 700;
    }}
    QLabel#muted {{
        color: #8b9bb4;
        font-size: 14px;
    }}
    QLabel#warn {{
        color: #ff6b6b;
        font-size: 20px;
        font-weight: 600;
    }}
    QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox {{
        background-color: #121826;
        border: 1px solid {accent};
        border-radius: 2px;
        padding: 14px 16px;
        color: {fg};
        font-size: 20px;
        min-height: 28px;
        selection-background-color: {accent};
        selection-color: {bg};
    }}
    QPushButton {{
        background-color: transparent;
        border: 1px solid {accent};
        color: {accent};
        padding: 14px 28px;
        border-radius: 2px;
        font-size: 18px;
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
        font-size: 20px;
        padding: 16px 36px;
    }}
    QPushButton#primary:hover {{
        background-color: #7af8e4;
    }}
    QPushButton#choice {{
        background-color: #121826;
        border: 1px solid #1f2a3d;
        color: {fg};
        text-align: left;
        padding: 14px 18px;
        font-size: 18px;
        font-weight: 500;
    }}
    QPushButton#choice:hover {{
        border-color: {accent};
        color: {fg};
        background-color: #182033;
    }}
    QPushButton#choice:checked {{
        background-color: {accent};
        border-color: {accent};
        color: {bg};
        font-weight: 700;
    }}
    QPushButton#choice:disabled {{
        border-color: #334155;
        color: #475569;
        background-color: #0d121c;
    }}
    QFrame#panel {{
        background-color: #0d121c;
        border: 1px solid #1f2a3d;
        border-radius: 4px;
    }}
    QFrame#startupPanel {{
        background-color: #0d121c;
        border: 1px solid #1f2a3d;
        border-radius: 4px;
        min-width: 480px;
        max-width: 640px;
    }}
    QFrame#frozenOverlay {{
        background-color: rgba(10, 14, 20, 220);
        border: 2px solid {accent};
    }}
    QFrame#switchOverlay {{
        background-color: rgba(6, 10, 16, 242);
    }}
    QFrame#switchBox {{
        background-color: #0d121c;
        border: 5px solid {accent};
        border-radius: 10px;
    }}
    QLabel#switchTitle {{
        color: {accent};
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
        background-color: #121826;
        border: 1px solid #1f2a3d;
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
