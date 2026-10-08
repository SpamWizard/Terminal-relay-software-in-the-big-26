"""Xbox / gamepad input via pygame — enable/disable and rebind without restart."""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QObject, QTimer, Signal

from baton_relay.config import XBOX_BUTTONS, ControllerConfig

# Common SDL / XInput-style face + shoulder mapping
_BUTTON_INDEX: dict[int, str] = {
    0: "A",
    1: "B",
    2: "X",
    3: "Y",
    4: "LB",
    5: "RB",
    6: "Back",
    7: "Start",
    8: "LS",
    9: "RS",
}

_HAT_MAP: dict[tuple[int, int], str] = {
    (0, 1): "DPadUp",
    (0, -1): "DPadDown",
    (-1, 0): "DPadLeft",
    (1, 0): "DPadRight",
}

ActionCallback = Callable[[str], None]


def _ensure_pygame() -> bool:
    try:
        import pygame

        if not pygame.get_init():
            pygame.init()
        if not pygame.joystick.get_init():
            pygame.joystick.init()
        return True
    except Exception:
        return False


def poll_pressed_buttons() -> set[str]:
    """Return currently held logical Xbox button names across all joysticks."""
    pressed: set[str] = set()
    if not _ensure_pygame():
        return pressed
    import pygame

    pygame.event.pump()
    count = pygame.joystick.get_count()
    for i in range(count):
        try:
            joy = pygame.joystick.Joystick(i)
            if not joy.get_init():
                joy.init()
        except Exception:
            continue
        for bi in range(joy.get_numbuttons()):
            try:
                if joy.get_button(bi):
                    name = _BUTTON_INDEX.get(bi)
                    if name:
                        pressed.add(name)
            except Exception:
                pass
        if joy.get_numhats() > 0:
            try:
                hat = joy.get_hat(0)
                name = _HAT_MAP.get(hat)
                if name:
                    pressed.add(name)
            except Exception:
                pass
        # Triggers as digital presses
        for axis_i, label in ((4, "LT"), (5, "RT"), (2, "LT"), (5, "RT")):
            if axis_i >= joy.get_numaxes():
                continue
            try:
                if joy.get_axis(axis_i) > 0.55:
                    pressed.add(label)
            except Exception:
                pass
    return pressed


def controller_connected() -> bool:
    if not _ensure_pygame():
        return False
    import pygame

    pygame.event.pump()
    return pygame.joystick.get_count() > 0


def first_controller_name() -> str:
    if not _ensure_pygame():
        return ""
    import pygame

    pygame.event.pump()
    if pygame.joystick.get_count() <= 0:
        return ""
    try:
        joy = pygame.joystick.Joystick(0)
        if not joy.get_init():
            joy.init()
        return joy.get_name() or "Controller"
    except Exception:
        return "Controller"


class XboxController(QObject):
    """Polls the pad and emits named actions when enabled + unlocked."""

    action = Signal(str)  # binding action key, e.g. "skip_question"
    status_changed = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._cfg = ControllerConfig(
            enabled=False,
            inactivity_lock_seconds=30,
            unlock_hold_ms=1000,
            device_name="Xbox Controller",
            unlock_buttons=("LB", "RB"),
            bindings={},
        )
        self._on_action: ActionCallback | None = None
        self._unlocked = False
        self._unlock_ms = 0.0
        self._idle_ms = 0.0
        self._prev: set[str] = set()
        self._timer = QTimer(self)
        self._timer.setInterval(40)
        self._timer.timeout.connect(self._tick)
        self._status = "OFF"

    @property
    def status_label(self) -> str:
        return self._status

    def apply_config(self, cfg: ControllerConfig) -> None:
        """Hot-apply enable flag + bindings without restarting the app."""
        was = self._cfg.enabled
        self._cfg = cfg
        if cfg.enabled:
            if not was or not self._timer.isActive():
                self.start()
            else:
                self._refresh_status()
        else:
            self.stop()

    def start(self, on_action: ActionCallback | None = None) -> None:
        if on_action is not None:
            self._on_action = on_action
        if not self._cfg.enabled:
            self.stop()
            return
        _ensure_pygame()
        self._unlocked = False
        self._unlock_ms = 0.0
        self._idle_ms = 0.0
        self._prev = set()
        if not self._timer.isActive():
            self._timer.start()
        self._refresh_status()

    def stop(self) -> None:
        self._timer.stop()
        self._unlocked = False
        self._set_status("OFF")

    def _set_status(self, text: str) -> None:
        if text == self._status:
            return
        self._status = text
        self.status_changed.emit(text)

    def _refresh_status(self) -> None:
        if not self._cfg.enabled:
            self._set_status("OFF")
            return
        if not controller_connected():
            self._set_status("NO PAD")
            return
        name = first_controller_name() or self._cfg.device_name
        short = name if len(name) < 22 else name[:20] + "…"
        if self._unlocked:
            self._set_status(f"UNLOCKED · {short}")
        else:
            chord = "+".join(self._cfg.unlock_buttons)
            self._set_status(f"LOCKED · hold {chord}")

    def _tick(self) -> None:
        if not self._cfg.enabled:
            return
        dt = self._timer.interval()
        pressed = poll_pressed_buttons()
        newly = pressed - self._prev
        self._prev = set(pressed)

        if not controller_connected():
            self._unlocked = False
            self._unlock_ms = 0.0
            self._refresh_status()
            return

        # Unlock chord hold
        chord = set(self._cfg.unlock_buttons)
        if chord and chord.issubset(pressed):
            self._unlock_ms += dt
            if not self._unlocked and self._unlock_ms >= self._cfg.unlock_hold_ms:
                self._unlocked = True
                self._idle_ms = 0.0
                self._refresh_status()
        else:
            self._unlock_ms = 0.0

        if pressed:
            self._idle_ms = 0.0
        else:
            self._idle_ms += dt
            if (
                self._unlocked
                and self._cfg.inactivity_lock_seconds > 0
                and self._idle_ms >= self._cfg.inactivity_lock_seconds * 1000
            ):
                self._unlocked = False
                self._refresh_status()

        if not self._unlocked:
            return

        # Edge-trigger bound actions
        for action, button in self._cfg.bindings.items():
            if button in newly and button in XBOX_BUTTONS:
                if self._on_action:
                    self._on_action(action)
                self.action.emit(action)
