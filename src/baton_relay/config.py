"""TOML config loading and validation."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


VALID_BATON_PAIRS: frozenset[tuple[int, int]] = frozenset(
    (a, b) for a in range(1, 6) for b in range(a + 1, 6)
)


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
    timers = TimersConfig(
        leg_seconds=_as_float(_require(timers_raw, "leg_seconds", "[timers]"), "[timers].leg_seconds"),
        game_seconds=_as_float(
            _require(timers_raw, "game_seconds", "[timers]"), "[timers].game_seconds"
        ),
        leg_runs_while_frozen=_as_bool(
            timers_raw.get("leg_runs_while_frozen", True),
            "[timers].leg_runs_while_frozen",
        ),
        debounce_ms=_as_int(timers_raw.get("debounce_ms", 80), "[timers].debounce_ms"),
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
    theme = ThemeConfig(
        name=_as_str(theme_raw.get("name", "neon_terminal"), "[theme].name"),
        accent=_as_str(theme_raw.get("accent", "#00f5d4"), "[theme].accent"),
        background=_as_str(theme_raw.get("background", "#0a0e14"), "[theme].background"),
        foreground=_as_str(theme_raw.get("foreground", "#e6edf3"), "[theme].foreground"),
    )

    ui_raw = raw.get("ui", {})
    if not isinstance(ui_raw, dict):
        raise ConfigError("[ui]: expected table")
    hold_ms = _as_int(ui_raw.get("correct_hold_ms", 480), "[ui].correct_hold_ms")
    fade_in_ms = _as_int(ui_raw.get("correct_fade_in_ms", 160), "[ui].correct_fade_in_ms")
    fade_out_ms = _as_int(ui_raw.get("correct_fade_out_ms", 200), "[ui].correct_fade_out_ms")
    for label, value in (
        ("[ui].correct_hold_ms", hold_ms),
        ("[ui].correct_fade_in_ms", fade_in_ms),
        ("[ui].correct_fade_out_ms", fade_out_ms),
    ):
        if value < 0:
            raise ConfigError(f"{label}: must be >= 0, got {value}")
    ui = UiConfig(
        correct_hold_ms=hold_ms,
        correct_fade_in_ms=fade_in_ms,
        correct_fade_out_ms=fade_out_ms,
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
        ui=ui,
        config_path=path,
        root_dir=root_dir,
    )
