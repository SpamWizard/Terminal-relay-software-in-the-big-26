"""In-app visual editor for config.toml."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from baton_relay.config import (
    AppConfig,
    ConfigError,
    PathsConfig,
    PersonConfig,
    MAX_BOARD_SLOTS,
    QuestionsConfig,
    ScoringConfig,
    SerialConfig,
    ThemeConfig,
    TimersConfig,
    UiConfig,
    VALID_BATON_PAIRS,
    load_config,
    save_config,
)


class ConfigDialog(QDialog):
    """Edit config.toml through form controls — no nested scrollers."""

    def __init__(self, config: AppConfig, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = config
        self.result_config: AppConfig | None = None
        self.setWindowTitle("Config")
        self.resize(820, 620)
        self.setModal(True)

        root = QVBoxLayout(self)
        root.setSpacing(12)
        title = QLabel("CONFIG")
        title.setObjectName("headline")
        root.addWidget(title)

        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)

        self._build_team_tab()
        self._build_timers_tab()
        self._build_scoring_tab()
        self._build_questions_tab()
        self._build_theme_tab()
        self._build_serial_tab()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self._load_from_config(config)

    def _build_team_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 12, 8, 8)
        form = QFormLayout()
        self.team_size = QSpinBox()
        self.team_size.setRange(3, 6)
        self.team_size.valueChanged.connect(self._sync_people_rows)
        form.addRow("Team size", self.team_size)
        layout.addLayout(form)

        self.people_box = QGroupBox("Seats (baton + color)")
        self.people_layout = QVBoxLayout(self.people_box)
        self.people_layout.setSpacing(6)
        self._people_rows: list[dict] = []
        layout.addWidget(self.people_box)
        layout.addStretch(1)
        self.tabs.addTab(page, "Crew")

    def _sync_people_rows(self) -> None:
        size = self.team_size.value()
        while len(self._people_rows) < size:
            self._add_person_row(len(self._people_rows))
        while len(self._people_rows) > size:
            row = self._people_rows.pop()
            row["widget"].setParent(None)
            row["widget"].deleteLater()

    def _add_person_row(self, index: int) -> None:
        wrap = QWidget()
        row = QHBoxLayout(wrap)
        row.setContentsMargins(0, 0, 0, 0)
        num = QLabel(f"#{index + 1}")
        num.setObjectName("playerBadge")
        num.setMinimumWidth(40)
        row.addWidget(num)
        pid = QLineEdit()
        pid.setPlaceholderText("id")
        pid.setMaximumWidth(72)
        row.addWidget(pid)
        label = QLineEdit()
        label.setPlaceholderText("label")
        label.setMaximumWidth(64)
        row.addWidget(label)
        color_btn = QPushButton("Color")
        color_btn.setProperty("hex", "#56B4E9")
        color_btn.clicked.connect(lambda _=False, b=color_btn: self._pick_color(b))
        row.addWidget(color_btn)
        pin_a = QSpinBox()
        pin_a.setRange(1, 5)
        pin_b = QSpinBox()
        pin_b.setRange(1, 5)
        row.addWidget(QLabel("pins"))
        row.addWidget(pin_a)
        row.addWidget(pin_b)
        self.people_layout.addWidget(wrap)
        self._people_rows.append(
            {
                "widget": wrap,
                "id": pid,
                "label": label,
                "color": color_btn,
                "pin_a": pin_a,
                "pin_b": pin_b,
            }
        )

    def _pick_color(self, btn: QPushButton) -> None:
        current = QColor(btn.property("hex") or "#56B4E9")
        chosen = QColorDialog.getColor(current, self, "Seat color")
        if chosen.isValid():
            hex_c = chosen.name()
            btn.setProperty("hex", hex_c)
            btn.setStyleSheet(f"background-color: {hex_c}; color: #041018;")
            btn.setText(hex_c)

    def _build_timers_tab(self) -> None:
        page = QWidget()
        form = QFormLayout(page)
        form.setContentsMargins(8, 16, 8, 8)
        self.leg_seconds = QDoubleSpinBox()
        self.leg_seconds.setRange(1, 3600)
        self.leg_seconds.setSuffix(" s")
        form.addRow("Leg timer", self.leg_seconds)
        self.game_seconds = QDoubleSpinBox()
        self.game_seconds.setRange(30, 24 * 3600)
        self.game_seconds.setSuffix(" s")
        form.addRow("Game timer", self.game_seconds)
        self.resume_bonus = QDoubleSpinBox()
        self.resume_bonus.setRange(0, 120)
        self.resume_bonus.setSuffix(" s")
        form.addRow("Resume bonus", self.resume_bonus)
        self.leg_while_frozen = QCheckBox("Leg timer runs while baton is out")
        form.addRow(self.leg_while_frozen)
        self.debounce_ms = QSpinBox()
        self.debounce_ms.setRange(0, 2000)
        self.debounce_ms.setSuffix(" ms")
        form.addRow("Debounce", self.debounce_ms)
        self.tabs.addTab(page, "Timers")

    def _build_scoring_tab(self) -> None:
        page = QWidget()
        form = QFormLayout(page)
        form.setContentsMargins(8, 16, 8, 8)
        self.partial_credit = QCheckBox("Partial credit")
        form.addRow(self.partial_credit)
        self.wrong_penalty = QDoubleSpinBox()
        self.wrong_penalty.setRange(0, 100)
        form.addRow("Wrong-answer penalty", self.wrong_penalty)
        self.redo_mult = QDoubleSpinBox()
        self.redo_mult.setRange(0, 1)
        self.redo_mult.setSingleStep(0.05)
        form.addRow("Redo multiplier", self.redo_mult)
        self.tabs.addTab(page, "Scoring")

    def _build_questions_tab(self) -> None:
        page = QWidget()
        form = QFormLayout(page)
        form.setContentsMargins(8, 16, 8, 8)
        self.question_files = QLineEdit()
        self.question_files.setPlaceholderText("challenges/steghide, questions/fake_logos.json")
        form.addRow("Category files", self.question_files)
        hint = QLabel("Each entry is one board category: a JSON file or a challenge folder.")
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        form.addRow(hint)
        self.warmup_count = QSpinBox()
        self.warmup_count.setRange(0, 9999)
        form.addRow("Warm-up questions (0 = board first)", self.warmup_count)
        self.board_slots = QSpinBox()
        self.board_slots.setRange(1, MAX_BOARD_SLOTS)
        form.addRow("Board slots (max 8 on screen)", self.board_slots)
        self.questions_per_pick = QSpinBox()
        self.questions_per_pick.setRange(1, 100)
        form.addRow("Questions per category pick", self.questions_per_pick)
        self.redo_at_end = QCheckBox("Redo missed questions at set / pick end")
        form.addRow(self.redo_at_end)
        self.tabs.addTab(page, "Questions")

    def _build_theme_tab(self) -> None:
        page = QWidget()
        form = QFormLayout(page)
        form.setContentsMargins(8, 16, 8, 8)
        self.theme_name = QComboBox()
        self.theme_name.setEditable(True)
        form.addRow("Theme preset", self.theme_name)
        self.theme_accent = QLineEdit()
        form.addRow("Accent", self.theme_accent)
        self.theme_bg = QLineEdit()
        form.addRow("Background", self.theme_bg)
        self.theme_fg = QLineEdit()
        form.addRow("Foreground", self.theme_fg)
        self.switch_sound = QCheckBox("Play switch chime")
        form.addRow(self.switch_sound)
        self.switch_vol = QDoubleSpinBox()
        self.switch_vol.setRange(0, 1)
        self.switch_vol.setSingleStep(0.05)
        form.addRow("Switch volume", self.switch_vol)
        self.tabs.addTab(page, "Theme")

    def _build_serial_tab(self) -> None:
        page = QWidget()
        form = QFormLayout(page)
        form.setContentsMargins(8, 16, 8, 8)
        self.serial_port = QLineEdit()
        form.addRow("Serial port", self.serial_port)
        self.serial_baud = QSpinBox()
        self.serial_baud.setRange(9600, 921600)
        form.addRow("Baud", self.serial_baud)
        self.serial_heartbeat = QSpinBox()
        self.serial_heartbeat.setRange(100, 30000)
        self.serial_heartbeat.setSuffix(" ms")
        form.addRow("Heartbeat timeout", self.serial_heartbeat)
        self.results_dir = QLineEdit()
        form.addRow("Results dir", self.results_dir)
        self.checkpoint_path = QLineEdit()
        form.addRow("Checkpoint path", self.checkpoint_path)
        self.tabs.addTab(page, "Device")

    def _load_from_config(self, config: AppConfig) -> None:
        self.team_size.setValue(config.team_size)
        self._sync_people_rows()
        for i, person in enumerate(config.people):
            if i >= len(self._people_rows):
                break
            row = self._people_rows[i]
            row["id"].setText(person.id)
            row["label"].setText(person.label)
            row["color"].setProperty("hex", person.color)
            row["color"].setText(person.color)
            row["color"].setStyleSheet(
                f"background-color: {person.color}; color: #041018;"
            )
            row["pin_a"].setValue(person.baton_pins[0])
            row["pin_b"].setValue(person.baton_pins[1])

        self.leg_seconds.setValue(config.timers.leg_seconds)
        self.game_seconds.setValue(config.timers.game_seconds)
        self.resume_bonus.setValue(config.timers.resume_bonus_seconds)
        self.leg_while_frozen.setChecked(config.timers.leg_runs_while_frozen)
        self.debounce_ms.setValue(config.timers.debounce_ms)

        self.partial_credit.setChecked(config.scoring.partial_credit)
        self.wrong_penalty.setValue(config.scoring.wrong_answer_penalty)
        self.redo_mult.setValue(config.scoring.redo_multiplier)
        self.redo_at_end.setChecked(config.questions.redo_missed_at_set_end)
        self.warmup_count.setValue(config.questions.warmup_count)
        self.board_slots.setValue(config.questions.board_slots)
        self.questions_per_pick.setValue(config.questions.questions_per_pick)
        rel_files = []
        for f in config.questions.files:
            try:
                rel_files.append(f.resolve().relative_to(config.root_dir.resolve()).as_posix())
            except ValueError:
                rel_files.append(f.as_posix())
        self.question_files.setText(", ".join(rel_files))

        self.theme_name.clear()
        names = sorted(config.themes) or [config.theme.name]
        self.theme_name.addItems(names)
        idx = self.theme_name.findText(config.theme.name)
        if idx >= 0:
            self.theme_name.setCurrentIndex(idx)
        else:
            self.theme_name.setEditText(config.theme.name)
        self.theme_accent.setText(config.theme.accent)
        self.theme_bg.setText(config.theme.background)
        self.theme_fg.setText(config.theme.foreground)
        self.switch_sound.setChecked(config.ui.switch_sound)
        self.switch_vol.setValue(config.ui.switch_sound_volume)

        self.serial_port.setText(config.serial.port)
        self.serial_baud.setValue(config.serial.baud)
        self.serial_heartbeat.setValue(config.serial.heartbeat_timeout_ms)
        try:
            self.results_dir.setText(
                config.paths.results_dir.resolve()
                .relative_to(config.root_dir.resolve())
                .as_posix()
            )
        except ValueError:
            self.results_dir.setText(config.paths.results_dir.as_posix())
        try:
            self.checkpoint_path.setText(
                config.paths.checkpoint_path.resolve()
                .relative_to(config.root_dir.resolve())
                .as_posix()
            )
        except ValueError:
            self.checkpoint_path.setText(config.paths.checkpoint_path.as_posix())

    def _build_updated_config(self) -> AppConfig:
        size = self.team_size.value()
        people: list[PersonConfig] = []
        seen: set[tuple[int, int]] = set()
        for i in range(size):
            row = self._people_rows[i]
            pins = tuple(sorted((row["pin_a"].value(), row["pin_b"].value())))
            if pins[0] == pins[1]:
                raise ConfigError(f"Seat #{i + 1}: baton pins must be two different pins")
            if pins not in VALID_BATON_PAIRS:
                raise ConfigError(f"Seat #{i + 1}: invalid baton pair {pins}")
            if pins in seen:
                raise ConfigError(f"Seat #{i + 1}: duplicate baton pair {pins}")
            seen.add(pins)
            pid = row["id"].text().strip() or f"p{i + 1}"
            label = row["label"].text().strip() or str(i + 1)
            color = row["color"].property("hex") or "#56B4E9"
            people.append(
                PersonConfig(id=pid, label=label, color=color, baton_pins=(pins[0], pins[1]))
            )

        theme_name = self.theme_name.currentText().strip() or "deep_space"
        themes = dict(self._config.themes)
        themes[theme_name] = ThemeConfig(
            name=theme_name,
            accent=self.theme_accent.text().strip() or "#7dd3fc",
            background=self.theme_bg.text().strip() or "#050816",
            foreground=self.theme_fg.text().strip() or "#e8f1ff",
        )

        q_files: list[Path] = []
        for part in self.question_files.text().split(","):
            text = part.strip()
            if not text:
                continue
            p = Path(text)
            if not p.is_absolute():
                p = (self._config.root_dir / p).resolve()
            q_files.append(p)
        if not q_files:
            raise ConfigError("At least one question file is required")

        results = Path(self.results_dir.text().strip() or "results")
        checkpoint = Path(self.checkpoint_path.text().strip() or "data/checkpoints/current.json")
        if not results.is_absolute():
            results = (self._config.root_dir / results).resolve()
        if not checkpoint.is_absolute():
            checkpoint = (self._config.root_dir / checkpoint).resolve()

        return self._config.with_updates(
            team_size=size,
            rotation=tuple(range(size)),
            people=tuple(people),
            timers=TimersConfig(
                leg_seconds=self.leg_seconds.value(),
                game_seconds=self.game_seconds.value(),
                leg_runs_while_frozen=self.leg_while_frozen.isChecked(),
                debounce_ms=self.debounce_ms.value(),
                resume_bonus_seconds=self.resume_bonus.value(),
            ),
            serial=SerialConfig(
                port=self.serial_port.text().strip() or "auto",
                baud=self.serial_baud.value(),
                heartbeat_timeout_ms=self.serial_heartbeat.value(),
            ),
            scoring=ScoringConfig(
                partial_credit=self.partial_credit.isChecked(),
                wrong_answer_penalty=self.wrong_penalty.value(),
                redo_multiplier=self.redo_mult.value(),
            ),
            questions=QuestionsConfig(
                files=tuple(q_files),
                redo_missed_at_set_end=self.redo_at_end.isChecked(),
                warmup_count=self.warmup_count.value(),
                board_slots=self.board_slots.value(),
                questions_per_pick=self.questions_per_pick.value(),
            ),
            paths=PathsConfig(
                results_dir=results,
                checkpoint_path=checkpoint,
            ),
            theme=themes[theme_name],
            themes=themes,
            ui=UiConfig(
                correct_hold_ms=self._config.ui.correct_hold_ms,
                correct_fade_in_ms=self._config.ui.correct_fade_in_ms,
                correct_fade_out_ms=self._config.ui.correct_fade_out_ms,
                switch_sound=self.switch_sound.isChecked(),
                switch_sound_volume=self.switch_vol.value(),
            ),
        )

    def _save(self) -> None:
        try:
            updated = self._build_updated_config()
            save_config(updated)
            self.result_config = load_config(updated.config_path)
        except (ConfigError, OSError, ValueError) as exc:
            QMessageBox.critical(self, "Config error", str(exc))
            return
        self.accept()
