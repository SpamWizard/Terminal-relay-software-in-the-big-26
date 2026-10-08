"""Xbox / gamepad input via pygame — enable/disable and rebind without restart."""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QObject, QTimer, Signal

from baton_relay.config import XBOX_BUTTONS, ControllerConfig

# XInput face/shoulder + SDL GameController D-pad indices (Series X reports
# hats=0 and uses buttons 11–14 for the D-pad).
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
    11: "DPadUp",
    12: "DPadDown",
    13: "DPadLeft",
    14: "DPadRight",
}

_HAT_MAP: dict[tuple[int, int], str] = {
    (0, 1): "DPadUp",
    (0, -1): "DPadDown",
    (-1, 0): "DPadLeft",
    (1, 0): "DPadRight",
}

# Keep Joystick objects alive — pygame deactivates them if GC'd between polls.
_JOYSTICKS: list = []

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


def _refresh_joysticks() -> list:
    """Return live joystick instances, recreating the cache when count changes."""
    global _JOYSTICKS
    if not _ensure_pygame():
        _JOYSTICKS = []
        return _JOYSTICKS
    import pygame

    pygame.event.pump()
    count = pygame.joystick.get_count()
    if len(_JOYSTICKS) != count:
        _JOYSTICKS = []
        for i in range(count):
            try:
                joy = pygame.joystick.Joystick(i)
                if not joy.get_init():
                    joy.init()
                _JOYSTICKS.append(joy)
            except Exception:
                pass
    else:
        for joy in _JOYSTICKS:
            try:
                if not joy.get_init():
                    joy.init()
            except Exception:
                pass
    return _JOYSTICKS


def _trigger_pressed(value: float) -> bool:
    """Triggers may be 0→1 or −1→1; both read near +1 when fully held."""
    return value >= 0.5


def poll_pressed_buttons() -> set[str]:
    """Return currently held logical Xbox button names across all joysticks."""
    pressed: set[str] = set()
    for joy in _refresh_joysticks():
        try:
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
            naxes = joy.get_numaxes()
            # Prefer dedicated trigger axes when present (Xbox-style 4/5).
            trigger_axes: list[tuple[int, str]] = []
            if naxes >= 6:
                trigger_axes = [(4, "LT"), (5, "RT")]
            elif naxes >= 5:
                trigger_axes = [(4, "LT"), (2, "RT")]
            else:
                trigger_axes = [(2, "LT"), (5, "RT")]
            for axis_i, label in trigger_axes:
                if axis_i >= naxes:
                    continue
                try:
                    if _trigger_pressed(float(joy.get_axis(axis_i))):
                        pressed.add(label)
                except Exception:
                    pass
        except Exception:
            continue
    return pressed


def controller_connected() -> bool:
    return len(_refresh_joysticks()) > 0


def first_controller_name() -> str:
    joys = _refresh_joysticks()
    if not joys:
        return ""
    try:
        return joys[0].get_name() or "Controller"
    except Exception:
        return "Controller"


class XboxController(QObject):
    """Polls the pad and emits named actions when enabled."""

    action = Signal(str)  # binding action key, e.g. "skip_question"
    status_changed = Signal(str)
    unlocked_changed = Signal(bool)
    locked_press = Signal()  # button while locked — UI can nudge the unlock chord

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
        _refresh_joysticks()
        # Locked until organizer holds the unlock chord.
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
            self._set_status(f"OVERRIDE · {short}")
        else:
            chord = "+".join(self._cfg.unlock_buttons) or "chord"
            self._set_status(f"LOCKED · hold {chord}")

    def _tick(self) -> None:
        if not self._cfg.enabled:
            return
        dt = self._timer.interval()
        pressed = poll_pressed_buttons()
        newly = pressed - self._prev
        self._prev = set(pressed)

        if not controller_connected():
            if self._unlocked:
                self._unlocked = False
                self.unlocked_changed.emit(False)
            self._unlock_ms = 0.0
            self._refresh_status()
            return

        chord = set(self._cfg.unlock_buttons)
        if chord and chord.issubset(pressed):
            self._unlock_ms += dt
            if not self._unlocked and self._unlock_ms >= self._cfg.unlock_hold_ms:
                self._unlocked = True
                self._idle_ms = 0.0
                self._refresh_status()
                self.unlocked_changed.emit(True)
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
                self.unlocked_changed.emit(False)

        if not self._unlocked:
            bound = set(self._cfg.bindings.values())
            # Nudge only on bound overrides — not unlock-chord chatter
            if newly & bound:
                self.locked_press.emit()
            return

        for action, button in self._cfg.bindings.items():
            if button in newly and button in XBOX_BUTTONS:
                if self._on_action:
                    self._on_action(action)
                self.action.emit(action)
