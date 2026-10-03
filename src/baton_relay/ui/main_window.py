"""Main window and screen flow."""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QKeyEvent, QPainter, QColor, QPen
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from baton_relay.audio import play_switch_chime
from baton_relay.config import AppConfig
from baton_relay.input.base import BatonReading, ReadingKind
from baton_relay.input.fake import FakeBatonSource
from baton_relay.questions.base import QuestionSet
from baton_relay.results.log import EventLog, new_run_dir
from baton_relay.state.machine import GameSession, GameSnapshot, RelayState
from baton_relay.ui.correct_burst import CorrectBurst
from baton_relay.ui.question_widgets import QuestionHost
from baton_relay.ui.theme import build_stylesheet, display_color, game_screen_wash, soften


def _fmt_time(seconds: float) -> str:
    s = max(0, int(seconds))
    m, sec = divmod(s, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h:d}:{m:02d}:{sec:02d}"
    return f"{m:02d}:{sec:02d}"


class ScanlineOverlay(QWidget):
    """Very light CRT-style scanlines (kept subtle so panels stay clean)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        pen = QPen(QColor(0, 0, 0, 14))
        pen.setWidth(1)
        painter.setPen(pen)
        for y in range(0, self.height(), 4):
            painter.drawLine(0, y, self.width(), y)


class StartupScreen(QWidget):
    started = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(48, 48, 48, 48)
        layout.addStretch(1)

        brand = QLabel("TERMINAL RELAY")
        brand.setObjectName("brand")
        brand.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(brand)

        layout.addSpacing(32)

        panel = QFrame()
        panel.setObjectName("startupPanel")
        panel.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(32, 28, 32, 28)
        panel_layout.setSpacing(16)
        title = QLabel("TEAM NAME")
        title.setObjectName("muted")
        panel_layout.addWidget(title)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Enter team name…")
        self.name_edit.returnPressed.connect(self._go)
        panel_layout.addWidget(self.name_edit)
        self.start_btn = QPushButton("START")
        self.start_btn.setObjectName("primary")
        self.start_btn.clicked.connect(self._go)
        panel_layout.addWidget(self.start_btn)
        hint = QLabel("F11 toggles fullscreen · Esc exits fullscreen")
        hint.setObjectName("muted")
        panel_layout.addWidget(hint)
        layout.addWidget(panel, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addStretch(2)

    def _go(self) -> None:
        name = self.name_edit.text().strip()
        if not name:
            self.name_edit.setPlaceholderText("Team name required")
            return
        self.started.emit(name)

    def reset(self) -> None:
        self.name_edit.clear()
        self.name_edit.setFocus()


class ScoreScreen(QWidget):
    next_team = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
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

    def show_score(self, team: str, points: float, message: str) -> None:
        self.team.setText(team)
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
        outer.setContentsMargins(48, 48, 48, 48)
        outer.addStretch(1)

        self.box = QFrame()
        self.box.setObjectName("switchBox")
        box_l = QVBoxLayout(self.box)
        box_l.setContentsMargins(64, 48, 64, 48)
        box_l.setSpacing(16)

        self.title = QLabel("SWITCH")
        self.title.setObjectName("switchTitle")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        box_l.addWidget(self.title)

        self.person = QLabel("—")
        self.person.setObjectName("switchPerson")
        self.person.setAlignment(Qt.AlignmentFlag.AlignCenter)
        box_l.addWidget(self.person)

        self.subtitle = QLabel("")
        self.subtitle.setObjectName("switchSub")
        self.subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.subtitle.setWordWrap(True)
        box_l.addWidget(self.subtitle)

        outer.addWidget(self.box, alignment=Qt.AlignmentFlag.AlignCenter)
        outer.addStretch(1)
        self.hide()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        # Scale the switch card with the display
        w = max(520, int(self.width() * 0.55))
        h = max(360, int(self.height() * 0.55))
        self.box.setMinimumSize(w, h)
        self.box.setMaximumWidth(int(self.width() * 0.85))

    def show_switch(self, person_label: str, color: str, *, mode: str, detail: str = "") -> None:
        if mode == "switch":
            self.title.setText("SWITCH")
            self.subtitle.setText(detail or f"Person {person_label} — plug in now")
        elif mode == "resume":
            self.title.setText("BATON OUT")
            self.subtitle.setText(detail or f"Person {person_label} — plug back in to continue")
        elif mode == "wrong":
            self.title.setText("WRONG")
            self.subtitle.setText(detail or f"Need person {person_label}")
        else:
            self.title.setText("WAIT")
            self.subtitle.setText(detail or f"Person {person_label}")
        self.person.setText(person_label)
        show = display_color(color, self.theme)
        border = soften(color, self.theme, amount=0.25)
        self.person.setStyleSheet(f"color: {show}; background: transparent;")
        self.title.setStyleSheet(f"color: {border}; background: transparent;")
        self.box.setStyleSheet(
            f"QFrame#switchBox {{ border: 3px solid {border}; "
            f"background-color: rgba(10, 14, 20, 236); border-radius: 10px; }}"
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
        root.setSpacing(16)

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

        # Stage holds gameplay + SWITCH overlay; header stays above so timers remain visible.
        self.stage = QWidget()
        stage_l = QVBoxLayout(self.stage)
        stage_l.setContentsMargins(0, 0, 0, 0)
        stage_l.setSpacing(16)

        body = QHBoxLayout()

        left = QFrame()
        left.setObjectName("panel")
        left_l = QVBoxLayout(left)
        left_l.addWidget(QLabel("NEXT / LEG"))
        self.next_big = QLabel("—")
        self.next_big.setObjectName("timerBig")
        self.next_big.setAlignment(Qt.AlignmentFlag.AlignCenter)
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
        left_l.addStretch(1)
        body.addWidget(left, 1)

        right = QFrame()
        right.setObjectName("panel")
        right_l = QVBoxLayout(right)
        self.question_host = QuestionHost()
        right_l.addWidget(self.question_host)
        body.addWidget(right, 2)

        stage_l.addLayout(body, 1)

        footer = QHBoxLayout()
        self.device_status = QLabel("DEVICE —")
        self.device_status.setObjectName("muted")
        footer.addWidget(self.device_status)
        footer.addStretch(1)
        self.hint = QLabel("Fake: 1-6 insert · P pull · U unknown")
        self.hint.setObjectName("muted")
        footer.addWidget(self.hint)
        stage_l.addLayout(footer)

        root.addWidget(self.stage, 1)

        self.switch_overlay = SwitchOverlay(config.theme, self.stage)
        self.correct_burst = CorrectBurst(self.stage)

    def _fit_switch_overlay(self) -> None:
        self.switch_overlay.setGeometry(self.stage.rect())
        self.switch_overlay.raise_()
        self.correct_burst.setGeometry(self.stage.rect())
        if self.correct_burst.isVisible():
            self.correct_burst.raise_()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._fit_switch_overlay()

    def bind_submit(self, handler: Callable) -> None:
        self.question_host.set_submit_handler(handler)

    def play_correct(self, points_text: str = "") -> None:
        ui = self.config.ui
        self.correct_burst.setGeometry(self.stage.rect())
        self.correct_burst.raise_()
        self.correct_burst.play(
            points_text,
            fade_in_ms=ui.correct_fade_in_ms,
            hold_ms=ui.correct_hold_ms,
            fade_out_ms=ui.correct_fade_out_ms,
        )

    def apply_person_color(self, color: str, window: QMainWindow | None = None) -> None:
        """Drive accents + background wash from the current / expected person."""
        if color == self._person_accent:
            return
        self._person_accent = color
        theme = self.config.theme
        soft = soften(color, theme, amount=0.15)
        self.setStyleSheet(game_screen_wash(theme, color))
        if window is not None:
            window.setStyleSheet(build_stylesheet(theme, accent=soft))

    def render(
        self,
        snap: GameSnapshot,
        question_changed: bool,
        question,
        *,
        window: QMainWindow | None = None,
    ) -> None:
        self.team_label.setText(snap.team_name or "TEAM")
        score = snap.progress.total_score
        self.score_label.setText(f"SCORE {score:.1f}" if score % 1 else f"SCORE {int(score)}")
        self.game_timer.setText(f"GAME {_fmt_time(snap.game_remaining)}")
        self.leg_timer.setText(_fmt_time(snap.leg_remaining))

        expected = self.config.people[snap.expected_person_index]
        # Active person owns the color while answering; otherwise expected next
        if snap.state == RelayState.ACTIVE and snap.current_person_index is not None:
            accent_person = self.config.people[snap.current_person_index]
        elif snap.state == RelayState.FROZEN and snap.current_person_index is not None:
            accent_person = self.config.people[snap.current_person_index]
        else:
            accent_person = expected
        self.apply_person_color(accent_person.color, window=window)

        self.next_big.setText(expected.label)
        show = display_color(accent_person.color, self.config.theme)
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
        self.device_status.setText(f"DEVICE {snap.device_status}")

        locked = snap.state != RelayState.ACTIVE
        self.question_host.set_locked(locked)
        if question_changed:
            self.question_host.show_question(question)

        # Big takeover when someone must plug in (header stays visible for game timer)
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
                expected.label,
                expected.color,
                mode=mode,
                detail=snap.last_message,
            )
            self._fit_switch_overlay()
        elif snap.state == RelayState.FROZEN:
            self._prev_switch_key = None
            person = (
                self.config.people[snap.current_person_index]
                if snap.current_person_index is not None
                else expected
            )
            self.switch_overlay.show_switch(
                person.label,
                person.color,
                mode="resume",
                detail=snap.last_message,
            )
            self._fit_switch_overlay()
        elif snap.state == RelayState.DISCONNECTED:
            self._prev_switch_key = None
            self.switch_overlay.show_switch(
                expected.label,
                expected.color,
                mode="wait",
                detail=snap.last_message or "Device disconnected",
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

        self.startup = StartupScreen()
        self.startup.started.connect(self._start_game)
        self.game_screen = GameScreen(config)
        self.game_screen.bind_submit(self._on_submit)
        self.score_screen = ScoreScreen()
        self.score_screen.next_team.connect(self._next_team)

        self.stack.addWidget(self.startup)
        self.stack.addWidget(self.game_screen)
        self.stack.addWidget(self.score_screen)

        self._scanlines = ScanlineOverlay(self)
        self._scanlines.resize(self.size())
        self._scanlines.raise_()

        self._timer = QTimer(self)
        self._timer.setInterval(100)
        self._timer.timeout.connect(self._on_tick)

        if fake_device:
            self._fake = FakeBatonSource(config)
            self._fake.start(self._on_reading)
            self.game_screen.hint.setText(
                "Fake: 1-6 insert · P pull · U unknown  (Ctrl+key while answering)  ·  F11 fullscreen"
            )
        else:
            self.game_screen.hint.setText("Serial device mode (connect RP2040)  ·  F11 fullscreen")

        self._pending_after_correct = False
        self.game_screen.correct_burst.finished.connect(self._after_correct_burst)
        self.startup.reset()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._scanlines.setGeometry(self.rect())
        self._scanlines.raise_()

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
            # When answering, require Ctrl so digits don't steal from text fields.
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

    def _start_game(self, team_name: str) -> None:
        self.run_dir = new_run_dir(self.config.paths.results_dir, team_name)
        self.event_log = EventLog(self.run_dir / "events.jsonl")

        def on_event(name: str, payload: dict) -> None:
            assert self.event_log is not None
            self.event_log.emit(name, team=team_name, **payload)

        self.session = GameSession(
            self.config,
            self.sets,
            team_name=team_name,
            on_event=on_event,
        )
        self.session.add_listener(lambda snap: self._on_snapshot(snap))
        self.session.set_device_status("FAKE" if self.fake_device else "waiting")
        self._last_qid = None
        self.event_log.emit("game_started", team=team_name)
        self.stack.setCurrentWidget(self.game_screen)
        self._timer.start()
        self._render(force_question=True)
        self.game_screen.setFocus()

    def _on_snapshot(self, snap: GameSnapshot) -> None:
        if snap.state == RelayState.PAUSED_SCORE:
            self._timer.stop()
            if self.session and self.event_log and self.run_dir:
                self.event_log.write_summary(
                    self.run_dir / "summary.json",
                    {
                        "team": snap.team_name,
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
            self.score_screen.show_score(
                snap.team_name,
                snap.progress.total_score,
                snap.last_message,
            )
            self.stack.setCurrentWidget(self.score_screen)
        else:
            self._render()

    def _on_tick(self) -> None:
        if self.session:
            self.session.tick(0.1)

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
        self.game_screen.render(snap, changed, q, window=self)

    def _next_team(self) -> None:
        self.session = None
        self.event_log = None
        self.run_dir = None
        self._last_qid = None
        self.game_screen._person_accent = ""  # force palette refresh next game
        self.setStyleSheet(build_stylesheet(self.config.theme))
        self.startup.reset()
        self.stack.setCurrentWidget(self.startup)
