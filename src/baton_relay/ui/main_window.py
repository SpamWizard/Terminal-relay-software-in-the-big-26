"""Main window and screen flow."""

from __future__ import annotations

from datetime import datetime
from typing import Callable

from PySide6.QtCore import QPoint, QRect, Qt, QTimer, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from baton_relay.audio import play_switch_chime
from baton_relay.config import AppConfig, load_config
from baton_relay.input.base import BatonReading, ReadingKind
from baton_relay.input.fake import FakeBatonSource
from baton_relay.input.xbox import XboxController
from baton_relay.questions.base import QuestionSet
from baton_relay.questions.loader import load_all_question_files
from baton_relay.results.checkpoint import (
    checkpoint_path_for,
    load_checkpoint,
    save_checkpoint,
)
from baton_relay.results.log import (
    EventLog,
    find_resumable_run,
    new_run_dir,
    team_name_taken,
)
from baton_relay.state.machine import GameSession, GameSnapshot, PlayerSlot, RelayState
from baton_relay.ui.config_dialog import ConfigDialog
from baton_relay.ui.correct_burst import CorrectBurst, OverrideFlash
from baton_relay.ui.question_widgets import QuestionHost
from baton_relay.ui.starfield import StarfieldOverlay
from baton_relay.ui.team_name_dialog import TeamNameConflictDialog
from baton_relay.ui.theme import (
    build_stylesheet,
    display_color,
    game_screen_wash,
    person_window_stylesheet,
    soften,
)


def _rect_in(widget: QWidget, target: QWidget) -> QRect:
    """Map widget geometry into target coords without requiring an ancestor link."""
    top_left = target.mapFromGlobal(widget.mapToGlobal(QPoint(0, 0)))
    return QRect(top_left, widget.size())


def _fmt_time(seconds: float) -> str:
    s = max(0, int(seconds))
    m, sec = divmod(s, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h:d}:{m:02d}:{sec:02d}"
    return f"{m:02d}:{sec:02d}"


def _player_label(slot: PlayerSlot) -> str:
    if slot.name.strip() == str(slot.player_number):
        return f"#{slot.player_number}"
    return f"#{slot.player_number} {slot.name}"


def _roster_text(roster: tuple[PlayerSlot, ...], *, highlight: int | None = None) -> str:
    parts: list[str] = []
    for slot in roster:
        label = _player_label(slot)
        if highlight is not None and slot.person_index == highlight:
            parts.append(f"▸ {label} ◂")
        else:
            parts.append(label)
    return "   ".join(parts)


class StartupScreen(QWidget):
    started = Signal(str, list)  # team_name, handles
    open_config = Signal()

    def __init__(self, config: AppConfig, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.config = config
        self.setObjectName("startupScreen")
        self._player_edits: list[QLineEdit] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 24)
        root.setSpacing(0)

        top = QHBoxLayout()
        self.config_btn = QPushButton("CONFIG")
        self.config_btn.setObjectName("ghost")
        self.config_btn.clicked.connect(self.open_config.emit)
        top.addWidget(self.config_btn, 0, Qt.AlignmentFlag.AlignLeft)
        top.addStretch(1)
        root.addLayout(top)

        root.addStretch(1)

        brand = QLabel("TERMINAL RELAY")
        brand.setObjectName("brand")
        brand.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(brand)

        root.addSpacing(24)

        self.panel = QFrame()
        self.panel.setObjectName("startupPanel")
        self.panel.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.panel.setAutoFillBackground(True)
        panel_layout = QVBoxLayout(self.panel)
        panel_layout.setContentsMargins(28, 24, 28, 24)
        panel_layout.setSpacing(12)

        title = QLabel("TEAM")
        title.setObjectName("muted")
        panel_layout.addWidget(title)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Team name…")
        self.name_edit.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.name_edit.returnPressed.connect(self._focus_first_player)
        panel_layout.addWidget(self.name_edit)

        self.crew_label = QLabel("Player names — badges show entry order")
        self.crew_label.setObjectName("muted")
        panel_layout.addWidget(self.crew_label)

        self.players_host = QVBoxLayout()
        self.players_host.setSpacing(8)
        panel_layout.addLayout(self.players_host)

        self.start_btn = QPushButton("START")
        self.start_btn.setObjectName("primary")
        self.start_btn.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.start_btn.clicked.connect(self._go)
        panel_layout.addWidget(self.start_btn)

        # After start_btn exists so tab-order wiring is safe
        self._rebuild_player_rows()

        root.addWidget(self.panel, alignment=Qt.AlignmentFlag.AlignCenter)
        root.addStretch(2)

    def apply_config(self, config: AppConfig) -> None:
        """Update seat count/colors without wiping typed team/handles."""
        team_text = self.name_edit.text()
        handle_texts = [edit.text() for edit in self._player_edits]
        self.config = config
        self._rebuild_player_rows(preserve_handles=handle_texts)
        self.name_edit.setText(team_text)

    def _rebuild_player_rows(self, preserve_handles: list[str] | None = None) -> None:
        while self.players_host.count():
            item = self.players_host.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._player_edits.clear()
        for i, person in enumerate(self.config.people):
            row = QFrame()
            row.setObjectName("playerRow")
            row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            row.setAutoFillBackground(True)
            hl = QHBoxLayout(row)
            hl.setContentsMargins(12, 8, 12, 8)
            badge = QLabel(f"#{i + 1}")
            badge.setObjectName("playerBadge")
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setStyleSheet(
                f"QLabel#playerBadge {{ background-color: {person.color}; color: #041018; }}"
            )
            hl.addWidget(badge)
            edit = QLineEdit()
            edit.setPlaceholderText("Player name…")
            edit.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            if preserve_handles is not None and i < len(preserve_handles):
                edit.setText(preserve_handles[i])
            if i + 1 < len(self.config.people):
                edit.returnPressed.connect(
                    lambda _=False, nxt=i + 1: self._player_edits[nxt].setFocus()
                )
            else:
                edit.returnPressed.connect(self._go)
            hl.addWidget(edit, 1)
            swatch = QLabel("●")
            swatch.setStyleSheet(f"color: {person.color}; font-size: 22px;")
            hl.addWidget(swatch)
            self.players_host.addWidget(row)
            self._player_edits.append(edit)
        self._apply_tab_order()

    def _apply_tab_order(self) -> None:
        chain: list[QWidget] = [self.name_edit, *self._player_edits, self.start_btn]
        for a, b in zip(chain, chain[1:]):
            QWidget.setTabOrder(a, b)

    def _focus_first_player(self) -> None:
        if self._player_edits:
            self._player_edits[0].setFocus()

    def _go(self) -> None:
        name = self.name_edit.text().strip()
        if not name:
            self.name_edit.setPlaceholderText("Team name required")
            self.name_edit.setFocus()
            return
        handles: list[str] = []
        for i, edit in enumerate(self._player_edits):
            handle = edit.text().strip()
            if not handle:
                edit.setPlaceholderText(f"Name for #{i + 1} required")
                edit.setFocus()
                return
            handles.append(handle)
        self.started.emit(name, handles)

    def reset(self) -> None:
        self.name_edit.clear()
        for edit in self._player_edits:
            edit.clear()
        self.name_edit.setFocus()

    def solid_panel_rect_in(self, target: QWidget) -> QRect:
        """Rect of the solid crew panel, mapped into `target` coords."""
        return _rect_in(self.panel, target)


class ScoreScreen(QWidget):
    next_team = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("scoreScreen")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(48, 48, 48, 48)
        layout.addStretch(1)
        self.title = QLabel("SCORE")
        self.title.setObjectName("brand")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title)
        self.team = QLabel("")
        self.team.setObjectName("headline")
        self.team.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.team)
        self.roster = QLabel("")
        self.roster.setObjectName("muted")
        self.roster.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.roster.setWordWrap(True)
        layout.addWidget(self.roster)
        self.score = QLabel("0")
        self.score.setObjectName("timerBig")
        self.score.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.score)
        self.detail = QLabel("")
        self.detail.setObjectName("muted")
        self.detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.detail)
        layout.addSpacing(28)
        btn = QPushButton("NEXT TEAM")
        btn.setObjectName("primary")
        btn.clicked.connect(self.next_team.emit)
        layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addStretch(2)

    def show_score(
        self, team: str, points: float, message: str, roster: tuple[PlayerSlot, ...]
    ) -> None:
        self.team.setText(team)
        self.roster.setText(_roster_text(roster))
        self.score.setText(f"{points:.1f}" if points % 1 else f"{int(points)}")
        self.detail.setText(message)


class SwitchOverlay(QFrame):
    """Full-screen takeover when a baton swap / plug-in is required."""

    def __init__(self, theme, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.theme = theme
        self.setObjectName("switchOverlay")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(40, 32, 40, 32)
        outer.addStretch(1)

        self.box = QFrame()
        self.box.setObjectName("switchBox")
        box_l = QVBoxLayout(self.box)
        box_l.setContentsMargins(48, 36, 48, 36)
        box_l.setSpacing(12)

        self.title = QLabel("SWITCH")
        self.title.setObjectName("switchTitle")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        box_l.addWidget(self.title)

        self.team_label = QLabel("")
        self.team_label.setObjectName("switchSub")
        self.team_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        box_l.addWidget(self.team_label)

        self.person = QLabel("—")
        self.person.setObjectName("switchPerson")
        self.person.setAlignment(Qt.AlignmentFlag.AlignCenter)
        box_l.addWidget(self.person)

        self.subtitle = QLabel("")
        self.subtitle.setObjectName("switchSub")
        self.subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.subtitle.setWordWrap(True)
        box_l.addWidget(self.subtitle)

        self.roster_label = QLabel("")
        self.roster_label.setObjectName("switchRoster")
        self.roster_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.roster_label.setWordWrap(True)
        box_l.addWidget(self.roster_label)

        outer.addWidget(self.box, alignment=Qt.AlignmentFlag.AlignCenter)
        outer.addStretch(1)
        self.hide()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        w = max(520, int(self.width() * 0.58))
        h = max(360, int(self.height() * 0.55))
        self.box.setMinimumSize(w, h)
        self.box.setMaximumWidth(int(self.width() * 0.88))

    def show_switch(
        self,
        person_label: str,
        color: str,
        *,
        mode: str,
        detail: str = "",
        team_name: str = "",
        roster: tuple[PlayerSlot, ...] = (),
        highlight: int | None = None,
        resume_bonus: float = 0.0,
    ) -> None:
        if mode == "switch":
            self.title.setText("SWITCH")
            self.subtitle.setText(detail or f"{person_label} — plug in now")
        elif mode == "resume":
            self.title.setText("RESUME")
            bonus = f"  ·  +{resume_bonus:g}s on reconnect" if resume_bonus else ""
            self.subtitle.setText(
                detail or f"{person_label} — plug back in to continue{bonus}"
            )
        elif mode == "wrong":
            self.title.setText("WRONG")
            self.subtitle.setText(detail or f"Need {person_label}")
        else:
            self.title.setText("WAIT")
            self.subtitle.setText(detail or person_label)
        self.team_label.setText(f"TEAM {team_name}" if team_name else "")
        self.person.setText(person_label)
        self.roster_label.setText(
            _roster_text(roster, highlight=highlight) if roster else ""
        )
        show = display_color(color, self.theme)
        border = soften(color, self.theme, amount=0.25)
        self.person.setStyleSheet(f"color: {show}; background: transparent;")
        self.title.setStyleSheet(f"color: {border}; background: transparent;")
        self.box.setStyleSheet(
            f"QFrame#switchBox {{ border: 3px solid {border}; "
            f"background-color: rgba(5, 8, 22, 236); border-radius: 14px; }}"
        )
        self.show()
        self.raise_()

    def clear(self) -> None:
        self.hide()


class GameScreen(QWidget):
    def __init__(self, config: AppConfig, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.config = config
        self.setObjectName("gameScreen")
        self._person_accent = config.theme.accent
        self._prev_switch_key: tuple[str, int] | None = None
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 20)
        root.setSpacing(12)

        header = QHBoxLayout()
        self.team_label = QLabel("TEAM")
        self.team_label.setObjectName("headline")
        header.addWidget(self.team_label, 2)
        self.score_label = QLabel("SCORE 0")
        self.score_label.setObjectName("headline")
        header.addWidget(self.score_label, 1)
        self.game_timer = QLabel("00:00")
        self.game_timer.setObjectName("headline")
        header.addWidget(self.game_timer, 1, Qt.AlignmentFlag.AlignRight)
        root.addLayout(header)

        self.roster_bar = QLabel("")
        self.roster_bar.setObjectName("muted")
        self.roster_bar.setWordWrap(True)
        root.addWidget(self.roster_bar)

        self.stage = QWidget()
        stage_l = QVBoxLayout(self.stage)
        stage_l.setContentsMargins(0, 0, 0, 0)
        stage_l.setSpacing(12)

        body = QHBoxLayout()

        self.left_panel = QFrame()
        self.left_panel.setObjectName("panel")
        self.left_panel.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.left_panel.setAutoFillBackground(True)
        left_l = QVBoxLayout(self.left_panel)
        left_l.addWidget(QLabel("NEXT / LEG"))
        self.next_big = QLabel("—")
        self.next_big.setObjectName("timerBig")
        self.next_big.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.next_big.setWordWrap(True)
        left_l.addWidget(self.next_big)
        self.leg_timer = QLabel("00:00")
        self.leg_timer.setObjectName("headline")
        self.leg_timer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_l.addWidget(self.leg_timer)
        self.state_label = QLabel("WAITING")
        self.state_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_l.addWidget(self.state_label)
        self.message = QLabel("")
        self.message.setWordWrap(True)
        self.message.setObjectName("muted")
        left_l.addWidget(self.message)
        log_label = QLabel("Log")
        log_label.setObjectName("muted")
        left_l.addWidget(log_label)
        self.activity_log = QPlainTextEdit()
        self.activity_log.setObjectName("activityLog")
        self.activity_log.setReadOnly(True)
        self.activity_log.setMaximumBlockCount(120)
        self.activity_log.setMinimumHeight(120)
        self.activity_log.setUndoRedoEnabled(False)
        left_l.addWidget(self.activity_log, 1)
        body.addWidget(self.left_panel, 1)

        self.right_panel = QFrame()
        self.right_panel.setObjectName("panel")
        self.right_panel.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.right_panel.setAutoFillBackground(True)
        right_l = QVBoxLayout(self.right_panel)
        self.question_host = QuestionHost()
        right_l.addWidget(self.question_host)
        body.addWidget(self.right_panel, 2)

        stage_l.addLayout(body, 1)

        root.addWidget(self.stage, 1)

        # Full-screen takeover (covers header + stage, not just the middle band)
        self.switch_overlay = SwitchOverlay(config.theme, self)
        self.correct_burst = CorrectBurst(self)

    def clear_activity(self) -> None:
        self.activity_log.clear()

    def append_activity(self, line: str) -> None:
        self.activity_log.appendPlainText(line)
        bar = self.activity_log.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _fit_switch_overlay(self) -> None:
        self.switch_overlay.setGeometry(self.rect())
        self.switch_overlay.raise_()
        self.correct_burst.setGeometry(self.rect())
        if self.correct_burst.isVisible():
            self.correct_burst.raise_()

    def panel_rects_in(self, target: QWidget) -> list[QRect]:
        """Opaque game boxes — stars stay in the gaps around them."""
        return [_rect_in(self.left_panel, target), _rect_in(self.right_panel, target)]

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._fit_switch_overlay()

    def bind_submit(self, handler: Callable) -> None:
        self.question_host.set_submit_handler(handler)

    def play_correct(self, points_text: str = "") -> None:
        ui = self.config.ui
        self.correct_burst.setGeometry(self.rect())
        self.correct_burst.raise_()
        self.correct_burst.play(
            points_text,
            fade_in_ms=ui.correct_fade_in_ms,
            hold_ms=ui.correct_hold_ms,
            fade_out_ms=ui.correct_fade_out_ms,
        )

    def apply_person_color(self, color: str, window: QMainWindow | None = None) -> None:
        if color == self._person_accent:
            return
        self._person_accent = color
        theme = self.config.theme
        self.setStyleSheet(game_screen_wash(theme, color))
        if window is not None:
            window.setStyleSheet(person_window_stylesheet(theme, color))

    def render(
        self,
        snap: GameSnapshot,
        question_changed: bool,
        question,
        *,
        window: QMainWindow | None = None,
        resume_bonus_cfg: float = 10.0,
    ) -> None:
        self.team_label.setText(snap.team_name or "TEAM")
        score = snap.progress.total_score
        self.score_label.setText(f"SCORE {score:.1f}" if score % 1 else f"SCORE {int(score)}")
        self.game_timer.setText(f"GAME {_fmt_time(snap.game_remaining)}")
        self.leg_timer.setText(_fmt_time(snap.leg_remaining))
        self.roster_bar.setText(_roster_text(snap.roster, highlight=snap.expected_person_index))

        expected = snap.roster[snap.expected_person_index]
        if snap.state == RelayState.ACTIVE and snap.current_person_index is not None:
            accent_slot = snap.roster[snap.current_person_index]
        elif snap.state == RelayState.FROZEN and snap.current_person_index is not None:
            accent_slot = snap.roster[snap.current_person_index]
        else:
            accent_slot = expected
        self.apply_person_color(accent_slot.color, window=window)

        if expected.name.strip() == str(expected.player_number):
            self.next_big.setText(f"#{expected.player_number}")
        else:
            self.next_big.setText(f"#{expected.player_number}\n{expected.name}")
        show = display_color(accent_slot.color, self.config.theme)
        self.next_big.setStyleSheet(f"color: {show}; background: transparent;")
        self.leg_timer.setStyleSheet(f"color: {show}; background: transparent;")
        self.game_timer.setStyleSheet(f"color: {show}; background: transparent;")
        self.score_label.setStyleSheet(f"color: {show}; background: transparent;")

        state_names = {
            RelayState.WAITING_FOR_BATON: "WAITING",
            RelayState.ACTIVE: "ACTIVE",
            RelayState.FROZEN: "FROZEN",
            RelayState.DISCONNECTED: "DISCONNECTED",
            RelayState.PAUSED_SCORE: "SCORE",
        }
        self.state_label.setText(state_names.get(snap.state, snap.state.name))
        if snap.wrong_baton or snap.state == RelayState.DISCONNECTED:
            self.state_label.setObjectName("warn")
        else:
            self.state_label.setObjectName("")
        self.state_label.style().unpolish(self.state_label)
        self.state_label.style().polish(self.state_label)

        self.message.setText(snap.last_message)

        locked = snap.state != RelayState.ACTIVE
        self.question_host.set_locked(locked)
        if question_changed:
            self.question_host.show_question(question)

        person_label = _player_label(expected)
        if snap.state == RelayState.WAITING_FOR_BATON:
            mode = "wrong" if snap.wrong_baton else "switch"
            switch_key = ("waiting", snap.expected_person_index)
            if (
                mode == "switch"
                and switch_key != self._prev_switch_key
                and self.config.ui.switch_sound
            ):
                play_switch_chime(volume=self.config.ui.switch_sound_volume)
            self._prev_switch_key = switch_key
            self.switch_overlay.show_switch(
                person_label,
                expected.color,
                mode=mode,
                detail=snap.last_message,
                team_name=snap.team_name,
                roster=snap.roster,
                highlight=snap.expected_person_index,
            )
            self._fit_switch_overlay()
        elif snap.state == RelayState.FROZEN:
            self._prev_switch_key = None
            slot = (
                snap.roster[snap.current_person_index]
                if snap.current_person_index is not None
                else expected
            )
            self.switch_overlay.show_switch(
                _player_label(slot),
                slot.color,
                mode="resume",
                detail=snap.last_message,
                team_name=snap.team_name,
                roster=snap.roster,
                highlight=slot.person_index,
                resume_bonus=resume_bonus_cfg,
            )
            self._fit_switch_overlay()
        elif snap.state == RelayState.DISCONNECTED:
            self._prev_switch_key = None
            self.switch_overlay.show_switch(
                person_label,
                expected.color,
                mode="wait",
                detail=snap.last_message or "Device disconnected",
                team_name=snap.team_name,
                roster=snap.roster,
                highlight=snap.expected_person_index,
            )
            self._fit_switch_overlay()
        else:
            self._prev_switch_key = None
            self.switch_overlay.clear()


class MainWindow(QMainWindow):
    def __init__(
        self,
        config: AppConfig,
        sets: list[QuestionSet],
        *,
        fake_device: bool = True,
    ) -> None:
        super().__init__()
        self.config = config
        self.sets = sets
        self.fake_device = fake_device
        self.session: GameSession | None = None
        self.event_log: EventLog | None = None
        self.run_dir = None
        self._last_qid: str | None = None
        self._fake: FakeBatonSource | None = None

        self.setWindowTitle("Terminal Relay")
        self.resize(1280, 800)
        self.setMinimumSize(1024, 640)
        self.setStyleSheet(build_stylesheet(config.theme))

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.startup = StartupScreen(config)
        self.startup.started.connect(self._start_game)
        self.startup.open_config.connect(self._open_config)
        self.game_screen = GameScreen(config)
        self.game_screen.bind_submit(self._on_submit)
        self.score_screen = ScoreScreen()
        self.score_screen.next_team.connect(self._next_team)

        self.stack.addWidget(self.startup)
        self.stack.addWidget(self.game_screen)
        self.stack.addWidget(self.score_screen)
        self.stack.currentChanged.connect(lambda _i: self._update_star_holes())

        # Full-bleed star overlay (edge-to-edge map); solid panels punch clear holes.
        self._stars = StarfieldOverlay(self)
        self._stars.resize(self.size())
        self._stars.raise_()

        # Above stars so override banners stay readable
        self._override_flash = OverrideFlash(self)
        self._override_flash.resize(self.size())
        self._override_flash.raise_()

        self._timer = QTimer(self)
        self._timer.setInterval(100)
        self._timer.timeout.connect(self._on_tick)

        self._xbox = XboxController(self)
        self._xbox.unlocked_changed.connect(self._on_xbox_unlocked)
        self._xbox.locked_press.connect(self._on_xbox_locked_press)
        self._xbox.start(self._on_xbox_action)
        self._xbox.apply_config(config.controller)

        if fake_device:
            self._fake = FakeBatonSource(config)
            self._fake.start(self._on_reading)

        self._pending_after_correct = False
        self._device_label = "FAKE" if fake_device else "waiting"
        self._ckpt_ticks = 0
        self.game_screen.correct_burst.finished.connect(self._after_correct_burst)
        self.startup.reset()
        QTimer.singleShot(0, self._update_star_holes)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._stars.setGeometry(self.rect())
        self._stars.raise_()
        self._override_flash.setGeometry(self.rect())
        self._override_flash.raise_()
        self._update_star_holes()

    def _flash_override(self, title: str, sub: str = "") -> None:
        self._override_flash.setGeometry(self.rect())
        self._override_flash.raise_()
        self._override_flash.play(title, sub)

    def _update_star_holes(self) -> None:
        """Stars only in the gaps — solid boxes stay clear. Quieter during play."""
        current = self.stack.currentWidget()
        if current is self.startup:
            self._stars.set_scrolling(True)
            self._stars.set_subtle(False)
            self._stars.set_holes([self.startup.solid_panel_rect_in(self._stars)])
        elif current is self.game_screen:
            self._stars.set_scrolling(False)
            self._stars.set_subtle(True)
            self._stars.set_holes(self.game_screen.panel_rects_in(self._stars))
        else:
            self._stars.set_scrolling(True)
            self._stars.set_subtle(False)
            self._stars.set_holes([])

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        key = event.key()
        if key == Qt.Key.Key_F11:
            if self.isFullScreen():
                self.showNormal()
            else:
                self.showFullScreen()
            return
        if key == Qt.Key.Key_Escape and self.isFullScreen():
            self.showNormal()
            return

        if self._fake and self.stack.currentWidget() is self.game_screen:
            locked = not self.session or self.session.questions_locked()
            ctrl = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
            text = event.text()

            if key == Qt.Key.Key_Backspace and (locked or ctrl):
                self._fake.handle_key("BACKSPACE")
                return
            if ctrl and key in (
                Qt.Key.Key_1,
                Qt.Key.Key_2,
                Qt.Key.Key_3,
                Qt.Key.Key_4,
                Qt.Key.Key_5,
                Qt.Key.Key_6,
                Qt.Key.Key_0,
                Qt.Key.Key_U,
                Qt.Key.Key_P,
            ):
                mapping = {
                    Qt.Key.Key_1: "1",
                    Qt.Key.Key_2: "2",
                    Qt.Key.Key_3: "3",
                    Qt.Key.Key_4: "4",
                    Qt.Key.Key_5: "5",
                    Qt.Key.Key_6: "6",
                    Qt.Key.Key_0: "0",
                    Qt.Key.Key_U: "U",
                    Qt.Key.Key_P: "P",
                }
                self._fake.handle_key(mapping[key])
                return
            if locked and text:
                self._fake.handle_key(text)
                return
        super().keyPressEvent(event)

    def _open_config(self) -> None:
        dlg = ConfigDialog(self.config, self)
        dlg.setStyleSheet(build_stylesheet(self.config.theme))
        if dlg.exec() and dlg.result_config is not None:
            self._apply_config(dlg.result_config)

    def _apply_config(self, config: AppConfig) -> None:
        self.config = config
        try:
            self.sets = load_all_question_files(config.questions.files)
        except Exception:
            pass
        self.game_screen.config = config
        self.game_screen.switch_overlay.theme = config.theme
        self.startup.apply_config(config)
        self.setStyleSheet(build_stylesheet(config.theme))
        self.game_screen._person_accent = ""
        if self._fake is not None:
            self._fake.config = config
        self._xbox.apply_config(config.controller)
        if self.session is not None:
            self.session.config = config
        self._update_star_holes()

    def _unlock_chord_text(self) -> str:
        return "+".join(self.config.controller.unlock_buttons)

    def _on_xbox_unlocked(self, unlocked: bool) -> None:
        if not self.config.controller.enabled:
            return
        if unlocked:
            self._flash_override("OVERRIDE", "Pad armed — use bound buttons")
            if self.stack.currentWidget() is self.game_screen:
                self.game_screen.append_activity(
                    f"{datetime.now().strftime('%H:%M:%S')}  OVERRIDE armed"
                )
        else:
            self._flash_override(
                "OVERRIDE OFF",
                f"Hold {self._unlock_chord_text()} to arm again",
            )

    def _on_xbox_locked_press(self) -> None:
        if not self.config.controller.enabled:
            return
        self._flash_override(
            "HOLD TO OVERRIDE",
            f"Hold {self._unlock_chord_text()}, then press the action",
        )

    def _on_xbox_action(self, action: str) -> None:
        if not self.config.controller.enabled:
            return
        ts = datetime.now().strftime("%H:%M:%S")
        if action == "skip_question" and self.session:
            self.session.skip_question(organizer=True)
            self._flash_override("OVERRIDE · SKIP", "Question skipped")
            self.game_screen.append_activity(f"{ts}  OVERRIDE skip")
            self._render(force_question=True)
        elif action == "force_leg_swap" and self.session:
            if self.session.state != RelayState.PAUSED_SCORE:
                self.session.advance_rotation()
                self._flash_override("OVERRIDE · SWAP", "Forced leg change")
                self.game_screen.append_activity(f"{ts}  OVERRIDE leg swap")
                self._render()
        elif action == "confirm":
            if (
                self.session
                and self.session.state == RelayState.ACTIVE
                and not self.session.questions_locked()
            ):
                self._flash_override("OVERRIDE · CONFIRM", "Submit")
                self.game_screen.question_host._submit()
        elif action == "cancel":
            self._flash_override("OVERRIDE · CANCEL", "No action bound")
        elif action == "pause_overlay" and self.session:
            self.session.last_message = "Controller pause — continue playing."
            self._flash_override("OVERRIDE · PAUSE", "Message ping")
            self.game_screen.append_activity(f"{ts}  OVERRIDE pause ping")
            self._render()

    def _on_reading(self, reading: BatonReading) -> None:
        if not self.session:
            return
        if reading.kind == ReadingKind.EMPTY:
            self.session.on_baton_reading(None, source=reading.source)
        elif reading.kind == ReadingKind.UNKNOWN:
            self.session.last_message = f"Unknown baton reading {reading.pins}"
            self.session.wrong_baton = True
            if self.event_log:
                self.event_log.emit(
                    "baton_unknown", pins=list(reading.pins), source=reading.source
                )
            self._render()
        else:
            self.session.on_baton_reading(reading.person_index, source=reading.source)

    def _start_game(self, team_name: str, player_names: list) -> None:
        results_dir = self.config.paths.results_dir
        if team_name_taken(results_dir, team_name):
            resumable = find_resumable_run(results_dir, team_name)
            dlg = TeamNameConflictDialog(
                team_name, resumable=resumable, parent=self
            )
            dlg.setStyleSheet(build_stylesheet(self.config.theme))
            dlg.exec()
            if dlg.choice == TeamNameConflictDialog.RESUME and resumable is not None:
                self._resume_game(resumable.run_dir)
                return
            self.startup.name_edit.setFocus()
            self.startup.name_edit.selectAll()
            return

        self._begin_new_game(team_name, list(player_names))

    def _resume_game(self, run_dir) -> None:
        ckpt = checkpoint_path_for(run_dir)
        if not ckpt.is_file():
            self.startup.name_edit.setFocus()
            self.startup.name_edit.selectAll()
            return

        self.run_dir = run_dir
        self.event_log = EventLog(run_dir / "events.jsonl")
        self.game_screen.clear_activity()

        def on_event(name: str, payload: dict) -> None:
            assert self.event_log is not None
            assert self.session is not None
            # payload may already include team — merge so we don't double-pass it
            self.event_log.emit(
                name, **{**payload, "team": self.session.team_name}
            )
            self._mirror_event(name, payload)
            self._save_checkpoint()

        session = load_checkpoint(ckpt, self.config, self.sets, on_event=on_event)
        self.session = session
        self.session.add_listener(lambda snap: self._on_snapshot(snap))
        self._device_label = "FAKE" if self.fake_device else "waiting"
        self.session.set_device_status(self._device_label)
        self._last_qid = None

        self.event_log.emit(
            "run_resumed",
            team=self.session.team_name,
            local_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            score=self.session.progress.total_score,
            game_remaining=round(self.session.game_remaining, 2),
        )
        self.game_screen.append_activity(
            f"{datetime.now().strftime('%H:%M:%S')}  RESUME {self.session.team_name} — "
            + ", ".join(_player_label(s) for s in self.session.roster)
            + f"  ·  {self.session.progress.total_score:g} pts"
        )
        self._save_checkpoint()
        self.stack.setCurrentWidget(self.game_screen)
        self._timer.start()
        self._render(force_question=True)
        self.game_screen.setFocus()

    def _begin_new_game(self, team_name: str, player_names: list) -> None:
        self.run_dir = new_run_dir(self.config.paths.results_dir, team_name)
        self.event_log = EventLog(self.run_dir / "events.jsonl")
        self.game_screen.clear_activity()

        def on_event(name: str, payload: dict) -> None:
            assert self.event_log is not None
            # payload may already include team — merge so we don't double-pass it
            self.event_log.emit(name, **{**payload, "team": team_name})
            self._mirror_event(name, payload)
            self._save_checkpoint()

        self.session = GameSession(
            self.config,
            self.sets,
            team_name=team_name,
            player_names=list(player_names),
            on_event=on_event,
        )
        self.session.add_listener(lambda snap: self._on_snapshot(snap))
        self._device_label = "FAKE" if self.fake_device else "waiting"
        self.session.set_device_status(self._device_label)
        self._last_qid = None
        roster_payload = [
            {
                "player_number": s.player_number,
                "name": s.name,
                "person_index": s.person_index,
                "color": s.color,
            }
            for s in self.session.roster
        ]
        self.event_log.emit(
            "game_started",
            team=team_name,
            roster=roster_payload,
            local_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
        self.game_screen.append_activity(
            f"{datetime.now().strftime('%H:%M:%S')}  {team_name} — "
            + ", ".join(_player_label(s) for s in self.session.roster)
        )
        self._save_checkpoint()
        self.stack.setCurrentWidget(self.game_screen)
        self._timer.start()
        self._render(force_question=True)
        self.game_screen.setFocus()

    def _save_checkpoint(self) -> None:
        if not self.session or not self.run_dir:
            return
        if self.session.state == RelayState.PAUSED_SCORE:
            return
        try:
            path = checkpoint_path_for(self.run_dir)
            save_checkpoint(path, self.session)
            # Mirror for reset tooling
            mirror = self.config.paths.checkpoint_path
            if mirror.resolve() != path.resolve():
                save_checkpoint(mirror, self.session)
        except OSError:
            pass

    def _who_label(self, number, name) -> str:
        num = number if number is not None else "?"
        handle = str(name or "").strip()
        if handle and handle != str(num):
            return f"#{num} {handle}"
        return f"#{num}"

    def _mirror_event(self, name: str, payload: dict) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        if name == "answer":
            who = self._who_label(payload.get("player_number"), payload.get("player_name"))
            pts = payload.get("points")
            max_p = payload.get("max_points")
            qid = payload.get("question_id")
            mark = "✓" if payload.get("correct") else "✗"
            # Prefer short clock time from local_time if present
            clock = str(payload.get("local_time", ts))
            if " " in clock:
                clock = clock.split(" ")[-1]
            line = f"{clock}  {who}  {mark}  {qid}  +{pts:g}/{max_p:g}"
            self.game_screen.append_activity(line)
        elif name == "baton_accepted":
            who = self._who_label(payload.get("player_number"), payload.get("player_name"))
            bonus = payload.get("resume_bonus_seconds") or 0
            verb = "resume" if payload.get("resume") else "in"
            extra = f"  (+{bonus:g}s)" if bonus else ""
            self.game_screen.append_activity(f"{ts}  {who}  {verb}{extra}")
        elif name == "frozen":
            who = self._who_label(payload.get("player_number"), payload.get("player_name"))
            self.game_screen.append_activity(f"{ts}  {who}  baton out")
        elif name == "leg_swap":
            who = self._who_label(
                payload.get("expected_player_number"),
                payload.get("expected_player_name"),
            )
            self.game_screen.append_activity(f"{ts}  next  {who}")
        elif name == "leg_expired":
            self.game_screen.append_activity(f"{ts}  leg time up")
        elif name == "game_ended":
            self.game_screen.append_activity(
                f"{ts}  end  {payload.get('score')} pts"
            )

    def _on_snapshot(self, snap: GameSnapshot) -> None:
        if snap.state == RelayState.PAUSED_SCORE:
            self._timer.stop()
            if self.session and self.event_log and self.run_dir:
                self.event_log.write_summary(
                    self.run_dir / "summary.json",
                    {
                        "team": snap.team_name,
                        "roster": [
                            {
                                "player_number": s.player_number,
                                "name": s.name,
                                "person_index": s.person_index,
                            }
                            for s in snap.roster
                        ],
                        "score": snap.progress.total_score,
                        "answered": {
                            k: {
                                "points": v.points,
                                "correct": v.correct,
                            }
                            for k, v in snap.progress.answered.items()
                        },
                    },
                )
                # Finished runs are not resumable
                for path in (
                    checkpoint_path_for(self.run_dir),
                    self.config.paths.checkpoint_path,
                ):
                    try:
                        if path.is_file():
                            path.unlink()
                    except OSError:
                        pass
            self.score_screen.show_score(
                snap.team_name,
                snap.progress.total_score,
                snap.last_message,
                snap.roster,
            )
            self.stack.setCurrentWidget(self.score_screen)
        else:
            self._render()

    def _on_tick(self) -> None:
        if self.session:
            self.session.tick(0.1)
            # Persist timers ~every 2s so a crash can resume mid-leg
            self._ckpt_ticks += 1
            if self._ckpt_ticks >= 20:
                self._ckpt_ticks = 0
                self._save_checkpoint()

    def _on_submit(self, answer) -> None:
        if not self.session:
            return
        result = self.session.submit_answer(answer)
        if not result:
            return
        self.game_screen.question_host.show_feedback(
            f"{result.feedback}  (+{result.points:g}/{result.max_points:g})"
        )
        if result.correct:
            self._pending_after_correct = True
            self.game_screen.play_correct(f"+{result.points:g} pts")
        else:
            self._pending_after_correct = False
            self._render(force_question=True)

    def _after_correct_burst(self) -> None:
        if not self._pending_after_correct:
            return
        self._pending_after_correct = False
        self._render(force_question=True)

    def _render(self, force_question: bool = False) -> None:
        if not self.session:
            return
        snap = self.session.snapshot()
        q = self.session.current_question()
        qid = q.id if q else None
        changed = force_question or qid != self._last_qid
        self._last_qid = qid
        self.game_screen.render(
            snap,
            changed,
            q,
            window=self,
            resume_bonus_cfg=self.config.timers.resume_bonus_seconds,
        )
        self._update_star_holes()

    def _next_team(self) -> None:
        self.session = None
        self.event_log = None
        self.run_dir = None
        self._last_qid = None
        self.game_screen._person_accent = ""
        self.game_screen.clear_activity()
        # Reload config in case it changed mid-run via another path
        try:
            self.config = load_config(self.config.config_path)
            self._apply_config(self.config)
        except Exception:
            self.setStyleSheet(build_stylesheet(self.config.theme))
        self.startup.reset()
        self.stack.setCurrentWidget(self.startup)
