"""TOML config loading, validation, and in-app save."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any


VALID_BATON_PAIRS: frozenset[tuple[int, int]] = frozenset(
    (a, b) for a in range(1, 6) for b in range(a + 1, 6)
)

XBOX_BUTTONS: tuple[str, ...] = (
    "A",
    "B",
    "X",
    "Y",
    "LB",
    "RB",
    "LT",
    "RT",
    "Back",
    "Start",
    "LS",
    "RS",
    "DPadUp",
    "DPadDown",
    "DPadLeft",
    "DPadRight",
)

DEFAULT_CONTROLLER_BINDINGS: dict[str, str] = {
    "skip_question": "X",
    "force_leg_swap": "Y",
    "pause_overlay": "Start",
    "confirm": "A",
    "cancel": "B",
}


class ConfigError(Exception):
    """Raised when config is missing or invalid."""


@dataclass(frozen=True)
class PersonConfig:
    id: str
    label: str
    color: str
    baton_pins: tuple[int, int]


@dataclass(frozen=True)
class TimersConfig:
    leg_seconds: float
    game_seconds: float
    leg_runs_while_frozen: bool
    debounce_ms: int
    resume_bonus_seconds: float


@dataclass(frozen=True)
class SerialConfig:
    port: str
    baud: int
    heartbeat_timeout_ms: int


@dataclass(frozen=True)
class ScoringConfig:
    partial_credit: bool
    wrong_answer_penalty: float
    redo_multiplier: float


@dataclass(frozen=True)
class QuestionsConfig:
    files: tuple[Path, ...]
    redo_missed_at_set_end: bool


@dataclass(frozen=True)
class ControllerConfig:
    enabled: bool
    inactivity_lock_seconds: float
    unlock_hold_ms: int
    device_name: str
    unlock_buttons: tuple[str, ...]
    bindings: dict[str, str]


@dataclass(frozen=True)
class ContainersConfig:
    runtime: str
    network_mode: str
    memory_limit: str
    cpu_limit: float
    default_timeout_seconds: int


@dataclass(frozen=True)
class PathsConfig:
    results_dir: Path
    checkpoint_path: Path


@dataclass(frozen=True)
class ThemeConfig:
    name: str
    accent: str
    background: str
    foreground: str


@dataclass(frozen=True)
class UiConfig:
    correct_hold_ms: int
    correct_fade_in_ms: int
    correct_fade_out_ms: int
    switch_sound: bool
    switch_sound_volume: float


@dataclass(frozen=True)
class AppConfig:
    team_size: int
    rotation: tuple[int, ...]
    people: tuple[PersonConfig, ...]
    timers: TimersConfig
    serial: SerialConfig
    scoring: ScoringConfig
    questions: QuestionsConfig
    controller: ControllerConfig
    organizer_password_hash: str
    containers: ContainersConfig
    paths: PathsConfig
    theme: ThemeConfig
    themes: dict[str, ThemeConfig]
    ui: UiConfig
    config_path: Path
    root_dir: Path

    def person_for_pins(self, pins: tuple[int, int]) -> PersonConfig | None:
        key = tuple(sorted(pins))
        for person in self.people:
            if tuple(sorted(person.baton_pins)) == key:
                return person
        return None

    def person_index(self, person_id: str) -> int | None:
        for i, p in enumerate(self.people):
            if p.id == person_id:
                return i
        return None

    def with_updates(self, **kwargs: Any) -> AppConfig:
        return replace(self, **kwargs)


def _require(section: dict[str, Any], key: str, path: str) -> Any:
    if key not in section:
        raise ConfigError(f"{path}: missing required key '{key}'")
    return section[key]


def _as_int(value: Any, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(f"{path}: expected integer, got {value!r}")
    return value


def _as_float(value: Any, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"{path}: expected number, got {value!r}")
    return float(value)


def _as_number_expr(value: Any, path: str) -> float:
    """Accept a number or a simple arithmetic string like '4*60' or '40 * 60'."""
    if isinstance(value, bool):
        raise ConfigError(f"{path}: expected number or expression string, got {value!r}")
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        expr = value.strip()
        if not expr:
            raise ConfigError(f"{path}: empty expression")
        try:
            return float(_eval_arith(expr))
        except ConfigError:
            raise
        except Exception as exc:
            raise ConfigError(f"{path}: invalid expression {value!r}: {exc}") from exc
    raise ConfigError(f"{path}: expected number or expression string, got {value!r}")


def _eval_arith(expr: str) -> float:
    """Safely evaluate + - * / // % ** and parentheses over numbers only."""
    import ast
    import operator as op

    ops = {
        ast.Add: op.add,
        ast.Sub: op.sub,
        ast.Mult: op.mul,
        ast.Div: op.truediv,
        ast.FloorDiv: op.floordiv,
        ast.Mod: op.mod,
        ast.Pow: op.pow,
        ast.UAdd: op.pos,
        ast.USub: op.neg,
    }

    def _eval(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        # Python 3.11 still may see BinOp etc.
        if isinstance(node, ast.BinOp) and type(node.op) in ops:
            return float(ops[type(node.op)](_eval(node.left), _eval(node.right)))
        if isinstance(node, ast.UnaryOp) and type(node.op) in ops:
            return float(ops[type(node.op)](_eval(node.operand)))
        raise ConfigError(f"unsupported expression node: {type(node).__name__}")

    tree = ast.parse(expr, mode="eval")
    return _eval(tree)


def _as_bool(value: Any, path: str) -> bool:
    if not isinstance(value, bool):
        raise ConfigError(f"{path}: expected boolean, got {value!r}")
    return value


def _as_str(value: Any, path: str) -> str:
    if not isinstance(value, str):
        raise ConfigError(f"{path}: expected string, got {value!r}")
    return value


def load_config(path: Path) -> AppConfig:
    path = Path(path).resolve()
    if not path.is_file():
        raise ConfigError(f"config file not found: {path}")

    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{path}: TOML parse error: {exc}") from exc

    root_dir = path.parent.parent if path.parent.name == "config" else path.parent

    team = raw.get("team")
    if not isinstance(team, dict):
        raise ConfigError(f"{path}: missing [team] section")

    size = _as_int(_require(team, "size", "[team]"), "[team].size")
    if size < 3 or size > 6:
        raise ConfigError(f"[team].size: must be 3-6, got {size}")

    people_raw = team.get("people")
    if not isinstance(people_raw, list) or len(people_raw) < size:
        raise ConfigError(
            f"[team].people: need at least {size} people entries, got "
            f"{0 if not isinstance(people_raw, list) else len(people_raw)}"
        )

    people: list[PersonConfig] = []
    seen_pins: set[tuple[int, int]] = set()
    for i, entry in enumerate(people_raw[:size]):
        p = f"[team.people.{i}]"
        if not isinstance(entry, dict):
            raise ConfigError(f"{p}: expected table")
        pins_list = _require(entry, "baton_pins", p)
        if not isinstance(pins_list, list) or len(pins_list) != 2:
            raise ConfigError(f"{p}.baton_pins: expected exactly two pin numbers")
        pins = tuple(sorted(int(x) for x in pins_list))
        if pins not in VALID_BATON_PAIRS:
            raise ConfigError(
                f"{p}.baton_pins: {pins} is not a valid two-pin baton "
                f"(valid: {sorted(VALID_BATON_PAIRS)})"
            )
        if pins in seen_pins:
            raise ConfigError(f"{p}.baton_pins: duplicate baton assignment {pins}")
        seen_pins.add(pins)
        people.append(
            PersonConfig(
                id=_as_str(_require(entry, "id", p), f"{p}.id"),
                label=_as_str(_require(entry, "label", p), f"{p}.label"),
                color=_as_str(_require(entry, "color", p), f"{p}.color"),
                baton_pins=(pins[0], pins[1]),
            )
        )

    rotation_raw = team.get("rotation")
    if rotation_raw is None:
        rotation = tuple(range(size))
    else:
        if not isinstance(rotation_raw, list) or len(rotation_raw) != size:
            raise ConfigError(f"[team].rotation: expected list of {size} indices")
        rotation = tuple(int(x) for x in rotation_raw)
        if sorted(rotation) != list(range(size)):
            raise ConfigError(
                f"[team].rotation: must be a permutation of 0..{size - 1}, got {rotation}"
            )

    timers_raw = raw.get("timers", {})
    if not isinstance(timers_raw, dict):
        raise ConfigError("[timers]: expected table")
    resume_bonus = _as_number_expr(
        timers_raw.get("resume_bonus_seconds", 10),
        "[timers].resume_bonus_seconds",
    )
    if resume_bonus < 0:
        raise ConfigError(
            f"[timers].resume_bonus_seconds: must be >= 0, got {resume_bonus}"
        )
    timers = TimersConfig(
        leg_seconds=_as_number_expr(
            _require(timers_raw, "leg_seconds", "[timers]"), "[timers].leg_seconds"
        ),
        game_seconds=_as_number_expr(
            _require(timers_raw, "game_seconds", "[timers]"), "[timers].game_seconds"
        ),
        leg_runs_while_frozen=_as_bool(
            timers_raw.get("leg_runs_while_frozen", True),
            "[timers].leg_runs_while_frozen",
        ),
        debounce_ms=_as_int(timers_raw.get("debounce_ms", 80), "[timers].debounce_ms"),
        resume_bonus_seconds=resume_bonus,
    )

    serial_raw = raw.get("serial", {})
    if not isinstance(serial_raw, dict):
        raise ConfigError("[serial]: expected table")
    serial = SerialConfig(
        port=_as_str(serial_raw.get("port", "auto"), "[serial].port"),
        baud=_as_int(serial_raw.get("baud", 115200), "[serial].baud"),
        heartbeat_timeout_ms=_as_int(
            serial_raw.get("heartbeat_timeout_ms", 1500),
            "[serial].heartbeat_timeout_ms",
        ),
    )

    scoring_raw = raw.get("scoring", {})
    if not isinstance(scoring_raw, dict):
        raise ConfigError("[scoring]: expected table")
    scoring = ScoringConfig(
        partial_credit=_as_bool(
            scoring_raw.get("partial_credit", True), "[scoring].partial_credit"
        ),
        wrong_answer_penalty=_as_float(
            scoring_raw.get("wrong_answer_penalty", 0),
            "[scoring].wrong_answer_penalty",
        ),
        redo_multiplier=_as_float(
            scoring_raw.get("redo_multiplier", 0.5), "[scoring].redo_multiplier"
        ),
    )

    questions_raw = raw.get("questions", {})
    if not isinstance(questions_raw, dict):
        raise ConfigError("[questions]: expected table")
    files_raw = _require(questions_raw, "files", "[questions]")
    if not isinstance(files_raw, list) or not files_raw:
        raise ConfigError("[questions].files: expected non-empty list of paths")
    q_files: list[Path] = []
    for f in files_raw:
        p = Path(_as_str(f, "[questions].files[]"))
        if not p.is_absolute():
            p = (root_dir / p).resolve()
        q_files.append(p)
    questions = QuestionsConfig(
        files=tuple(q_files),
        redo_missed_at_set_end=_as_bool(
            questions_raw.get("redo_missed_at_set_end", True),
            "[questions].redo_missed_at_set_end",
        ),
    )

    controller_raw = raw.get("controller", {})
    if not isinstance(controller_raw, dict):
        raise ConfigError("[controller]: expected table")
    unlock_raw = controller_raw.get("unlock_buttons", ["LB", "RB"])
    if not isinstance(unlock_raw, list) or not unlock_raw:
        raise ConfigError("[controller].unlock_buttons: expected non-empty list")
    unlock_buttons: list[str] = []
    for i, btn in enumerate(unlock_raw):
        name = _as_str(btn, f"[controller].unlock_buttons[{i}]")
        if name not in XBOX_BUTTONS:
            raise ConfigError(
                f"[controller].unlock_buttons[{i}]: unknown button {name!r} "
                f"(valid: {', '.join(XBOX_BUTTONS)})"
            )
        unlock_buttons.append(name)
    bindings_raw = controller_raw.get("bindings", {})
    if bindings_raw is None:
        bindings_raw = {}
    if not isinstance(bindings_raw, dict):
        raise ConfigError("[controller.bindings]: expected table")
    bindings = dict(DEFAULT_CONTROLLER_BINDINGS)
    for key, value in bindings_raw.items():
        action = _as_str(key, "[controller.bindings] key")
        button = _as_str(value, f"[controller.bindings].{action}")
        if button not in XBOX_BUTTONS:
            raise ConfigError(
                f"[controller.bindings].{action}: unknown button {button!r}"
            )
        bindings[action] = button
    controller = ControllerConfig(
        enabled=_as_bool(controller_raw.get("enabled", True), "[controller].enabled"),
        inactivity_lock_seconds=_as_float(
            controller_raw.get("inactivity_lock_seconds", 30),
            "[controller].inactivity_lock_seconds",
        ),
        unlock_hold_ms=_as_int(
            controller_raw.get("unlock_hold_ms", 1000),
            "[controller].unlock_hold_ms",
        ),
        device_name=_as_str(
            controller_raw.get("device_name", "Xbox Controller"),
            "[controller].device_name",
        ),
        unlock_buttons=tuple(unlock_buttons),
        bindings=bindings,
    )

    organizer_raw = raw.get("organizer", {})
    if not isinstance(organizer_raw, dict):
        raise ConfigError("[organizer]: expected table")
    password_hash = _as_str(
        _require(organizer_raw, "password_hash", "[organizer]"),
        "[organizer].password_hash",
    )

    containers_raw = raw.get("containers", {})
    if not isinstance(containers_raw, dict):
        raise ConfigError("[containers]: expected table")
    containers = ContainersConfig(
        runtime=_as_str(containers_raw.get("runtime", "podman"), "[containers].runtime"),
        network_mode=_as_str(
            containers_raw.get("network_mode", "none"), "[containers].network_mode"
        ),
        memory_limit=_as_str(
            containers_raw.get("memory_limit", "256m"), "[containers].memory_limit"
        ),
        cpu_limit=_as_float(containers_raw.get("cpu_limit", 0.5), "[containers].cpu_limit"),
        default_timeout_seconds=_as_int(
            containers_raw.get("default_timeout_seconds", 600),
            "[containers].default_timeout_seconds",
        ),
    )

    paths_raw = raw.get("paths", {})
    if not isinstance(paths_raw, dict):
        raise ConfigError("[paths]: expected table")
    results_dir = Path(_as_str(paths_raw.get("results_dir", "results"), "[paths].results_dir"))
    checkpoint_path = Path(
        _as_str(
            paths_raw.get("checkpoint_path", "data/checkpoints/current.json"),
            "[paths].checkpoint_path",
        )
    )
    if not results_dir.is_absolute():
        results_dir = (root_dir / results_dir).resolve()
    if not checkpoint_path.is_absolute():
        checkpoint_path = (root_dir / checkpoint_path).resolve()
    paths = PathsConfig(results_dir=results_dir, checkpoint_path=checkpoint_path)

    theme_raw = raw.get("theme", {})
    if not isinstance(theme_raw, dict):
        raise ConfigError("[theme]: expected table")
    theme_name = _as_str(theme_raw.get("name", "deep_space"), "[theme].name")

    # Optional named presets under [themes.<name>]
    themes_raw = raw.get("themes", {})
    if themes_raw is not None and not isinstance(themes_raw, dict):
        raise ConfigError("[themes]: expected table of named themes")
    theme_presets: dict[str, ThemeConfig] = {}
    if isinstance(themes_raw, dict):
        for preset_name, candidate in themes_raw.items():
            if not isinstance(candidate, dict):
                raise ConfigError(f"[themes.{preset_name}]: expected table")
            theme_presets[str(preset_name)] = ThemeConfig(
                name=str(preset_name),
                accent=_as_str(
                    candidate.get("accent", "#7dd3fc"),
                    f"[themes.{preset_name}].accent",
                ),
                background=_as_str(
                    candidate.get("background", "#050816"),
                    f"[themes.{preset_name}].background",
                ),
                foreground=_as_str(
                    candidate.get("foreground", "#e8f1ff"),
                    f"[themes.{preset_name}].foreground",
                ),
            )

    preset_theme = theme_presets.get(theme_name)
    if theme_presets and preset_theme is None:
        available = ", ".join(sorted(theme_presets))
        raise ConfigError(
            f"[theme].name: unknown theme {theme_name!r} (available: {available})"
        )

    # Prefer preset colors; allow [theme] overrides for accent/background/foreground
    theme = ThemeConfig(
        name=theme_name,
        accent=_as_str(
            theme_raw.get(
                "accent",
                preset_theme.accent if preset_theme else "#7dd3fc",
            ),
            "[theme].accent",
        ),
        background=_as_str(
            theme_raw.get(
                "background",
                preset_theme.background if preset_theme else "#050816",
            ),
            "[theme].background",
        ),
        foreground=_as_str(
            theme_raw.get(
                "foreground",
                preset_theme.foreground if preset_theme else "#e8f1ff",
            ),
            "[theme].foreground",
        ),
    )

    ui_raw = raw.get("ui", {})
    if not isinstance(ui_raw, dict):
        raise ConfigError("[ui]: expected table")
    hold_ms = _as_int(ui_raw.get("correct_hold_ms", 480), "[ui].correct_hold_ms")
    fade_in_ms = _as_int(ui_raw.get("correct_fade_in_ms", 160), "[ui].correct_fade_in_ms")
    fade_out_ms = _as_int(ui_raw.get("correct_fade_out_ms", 200), "[ui].correct_fade_out_ms")
    switch_sound = _as_bool(ui_raw.get("switch_sound", True), "[ui].switch_sound")
    switch_vol = _as_number_expr(
        ui_raw.get("switch_sound_volume", 0.9), "[ui].switch_sound_volume"
    )
    for label, value in (
        ("[ui].correct_hold_ms", hold_ms),
        ("[ui].correct_fade_in_ms", fade_in_ms),
        ("[ui].correct_fade_out_ms", fade_out_ms),
    ):
        if value < 0:
            raise ConfigError(f"{label}: must be >= 0, got {value}")
    if not 0.0 <= switch_vol <= 1.0:
        raise ConfigError(
            f"[ui].switch_sound_volume: must be 0.0–1.0, got {switch_vol}"
        )
    ui = UiConfig(
        correct_hold_ms=hold_ms,
        correct_fade_in_ms=fade_in_ms,
        correct_fade_out_ms=fade_out_ms,
        switch_sound=switch_sound,
        switch_sound_volume=switch_vol,
    )

    return AppConfig(
        team_size=size,
        rotation=rotation,
        people=tuple(people),
        timers=timers,
        serial=serial,
        scoring=scoring,
        questions=questions,
        controller=controller,
        organizer_password_hash=password_hash,
        containers=containers,
        paths=paths,
        theme=theme,
        themes=theme_presets,
        ui=ui,
        config_path=path,
        root_dir=root_dir,
    )


def _toml_str(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _toml_number(value: float | int) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int) or (isinstance(value, float) and value.is_integer()):
        return str(int(value))
    return repr(float(value))


def _rel_path(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def save_config(config: AppConfig, path: Path | None = None) -> None:
    """Write AppConfig back to TOML for in-app editing."""
    dest = Path(path or config.config_path).resolve()
    root = config.root_dir
    lines: list[str] = [
        "# Terminal Relay — organizer config (editable in-app)",
        "",
        "[team]",
        f"size = {config.team_size}",
        f"rotation = [{', '.join(str(i) for i in config.rotation)}]",
        "",
    ]
    for person in config.people:
        lines.extend(
            [
                "[[team.people]]",
                f"id = {_toml_str(person.id)}",
                f"label = {_toml_str(person.label)}",
                f"color = {_toml_str(person.color)}",
                f"baton_pins = [{person.baton_pins[0]}, {person.baton_pins[1]}]",
                "",
            ]
        )
    t = config.timers
    lines.extend(
        [
            "[timers]",
            f"leg_seconds = {_toml_number(t.leg_seconds)}",
            f"game_seconds = {_toml_number(t.game_seconds)}",
            f"leg_runs_while_frozen = {'true' if t.leg_runs_while_frozen else 'false'}",
            f"debounce_ms = {t.debounce_ms}",
            f"resume_bonus_seconds = {_toml_number(t.resume_bonus_seconds)}",
            "",
            "[serial]",
            f"port = {_toml_str(config.serial.port)}",
            f"baud = {config.serial.baud}",
            f"heartbeat_timeout_ms = {config.serial.heartbeat_timeout_ms}",
            "",
            "[scoring]",
            f"partial_credit = {'true' if config.scoring.partial_credit else 'false'}",
            f"wrong_answer_penalty = {_toml_number(config.scoring.wrong_answer_penalty)}",
            f"redo_multiplier = {_toml_number(config.scoring.redo_multiplier)}",
            "",
            "[questions]",
            "files = [",
        ]
    )
    for qf in config.questions.files:
        lines.append(f"    {_toml_str(_rel_path(qf, root))},")
    lines.extend(
        [
            "]",
            f"redo_missed_at_set_end = "
            f"{'true' if config.questions.redo_missed_at_set_end else 'false'}",
            "",
            "[controller]",
            f"enabled = {'true' if config.controller.enabled else 'false'}",
            f"inactivity_lock_seconds = "
            f"{_toml_number(config.controller.inactivity_lock_seconds)}",
            f"unlock_hold_ms = {config.controller.unlock_hold_ms}",
            f"device_name = {_toml_str(config.controller.device_name)}",
            "unlock_buttons = ["
            + ", ".join(_toml_str(b) for b in config.controller.unlock_buttons)
            + "]",
            "",
            "[controller.bindings]",
        ]
    )
    for action, button in sorted(config.controller.bindings.items()):
        lines.append(f"{action} = {_toml_str(button)}")
    lines.extend(
        [
            "",
            "[organizer]",
            f"password_hash = {_toml_str(config.organizer_password_hash)}",
            "",
            "[containers]",
            f"runtime = {_toml_str(config.containers.runtime)}",
            f"network_mode = {_toml_str(config.containers.network_mode)}",
            f"memory_limit = {_toml_str(config.containers.memory_limit)}",
            f"cpu_limit = {_toml_number(config.containers.cpu_limit)}",
            f"default_timeout_seconds = {config.containers.default_timeout_seconds}",
            "",
            "[paths]",
            f"results_dir = {_toml_str(_rel_path(config.paths.results_dir, root))}",
            f"checkpoint_path = "
            f"{_toml_str(_rel_path(config.paths.checkpoint_path, root))}",
            "",
            "[theme]",
            f"name = {_toml_str(config.theme.name)}",
            "",
        ]
    )
    for name, preset in sorted(config.themes.items()):
        lines.extend(
            [
                f"[themes.{name}]",
                f"accent = {_toml_str(preset.accent)}",
                f"background = {_toml_str(preset.background)}",
                f"foreground = {_toml_str(preset.foreground)}",
                "",
            ]
        )
    ui = config.ui
    lines.extend(
        [
            "[ui]",
            f"correct_fade_in_ms = {ui.correct_fade_in_ms}",
            f"correct_hold_ms = {ui.correct_hold_ms}",
            f"correct_fade_out_ms = {ui.correct_fade_out_ms}",
            f"switch_sound = {'true' if ui.switch_sound else 'false'}",
            f"switch_sound_volume = {_toml_number(ui.switch_sound_volume)}",
            "",
        ]
    )
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("\n".join(lines), encoding="utf-8")

