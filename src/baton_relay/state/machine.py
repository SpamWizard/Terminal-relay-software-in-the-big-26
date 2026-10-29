"""Relay state machine and game session logic."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Callable

from baton_relay.config import MAX_BOARD_SLOTS, AppConfig, PersonConfig
from baton_relay.duration import format_duration
from baton_relay.questions.base import Question, QuestionSet, ScoreResult
from baton_relay.questions.types import MultipleChoice
from baton_relay.questions.describe import format_expected, format_submitted


class RelayState(Enum):
    WAITING_FOR_BATON = auto()
    ACTIVE = auto()
    FROZEN = auto()
    DISCONNECTED = auto()
    PAUSED_SCORE = auto()
    CHOOSING_CATEGORY = auto()


@dataclass
class Progress:
    set_index: int = 0
    question_index: int = 0
    # Within a set / pick redo pass
    in_redo: bool = False
    redo_queue: list[str] = field(default_factory=list)  # question ids
    redo_index: int = 0
    answered: dict[str, ScoreResult] = field(default_factory=dict)
    missed_ids: list[str] = field(default_factory=list)
    total_score: float = 0.0
    finished: bool = False
    # Board / warm-up
    phase: str = "warmup"  # warmup | board | in_pick
    warmup_done: int = 0
    set_cursors: dict[str, int] = field(default_factory=dict)  # set_id -> next q index
    board_slots: list[str] = field(default_factory=list)  # set_ids on the board
    pool: list[str] = field(default_factory=list)  # unused set_ids with questions left
    pick_set_id: str | None = None
    pick_remaining: int = 0
    pick_missed: list[str] = field(default_factory=list)
    # Question id -> choice indexes already guessed wrong. Each one lowers miss_cost awards.
    spent_choices: dict[str, list[int]] = field(default_factory=dict)


@dataclass(frozen=True)
class PlayerSlot:
    """Runtime player assignment for one seat (config person index)."""

    person_index: int
    player_number: int  # 1-based assignment order
    name: str
    color: str
    seat_label: str


@dataclass
class GameSnapshot:
    team_name: str
    state: RelayState
    expected_person_index: int
    current_person_index: int | None
    leg_remaining: float
    game_remaining: float
    progress: Progress
    last_message: str
    wrong_baton: bool
    device_status: str
    roster: tuple[PlayerSlot, ...]
    last_resume_bonus: float
    bypass_baton: bool = False


Listener = Callable[[GameSnapshot], None]


class GameSession:
    """Core relay rules. UI and input sources call into this; timers tick via `tick`."""

    def __init__(
        self,
        config: AppConfig,
        sets: list[QuestionSet],
        *,
        team_name: str = "",
        player_names: list[str] | None = None,
        on_event: Callable[[str, dict[str, Any]], None] | None = None,
        bypass_baton: bool = False,
    ) -> None:
        if not sets:
            raise ValueError("at least one question set is required")
        self.config = config
        self.sets = sets
        self._sets_by_id = {s.set_id: s for s in sets}
        self.team_name = team_name
        self.bypass_baton = bypass_baton
        self._on_event = on_event or (lambda *_: None)

        names = list(player_names or [])
        while len(names) < config.team_size:
            names.append(config.people[len(names)].label)
        self.roster: tuple[PlayerSlot, ...] = tuple(
            PlayerSlot(
                person_index=i,
                player_number=i + 1,
                name=names[i].strip() or config.people[i].label,
                color=config.people[i].color,
                seat_label=config.people[i].label,
            )
            for i in range(config.team_size)
        )

        self.state = RelayState.WAITING_FOR_BATON
        self.rotation_pos = 0  # index into config.rotation
        self.current_person_index: int | None = None
        self.leg_remaining = float(config.timers.leg_seconds)
        self.game_remaining = float(config.timers.game_seconds)
        self.timers_started = False
        self.progress = Progress(
            set_cursors={s.set_id: 0 for s in sets},
        )
        first = self.player_display(self.expected_person_index)
        self.last_message = f"SWITCH — {first} plug in to begin."
        self.wrong_baton = False
        self.device_status = "unknown"
        self.last_resume_bonus = 0.0
        self._pre_disconnect_state: RelayState | None = None
        self._listeners: list[Listener] = []

        if config.questions.warmup_count <= 0:
            self._enter_board(initial=True)
        if self.bypass_baton:
            self._ensure_testing_seat()

    # --- observers ---

    def add_listener(self, listener: Listener) -> None:
        self._listeners.append(listener)

    def player_slot(self, person_index: int) -> PlayerSlot:
        return self.roster[person_index]

    def player_display(self, person_index: int) -> str:
        slot = self.roster[person_index]
        # Avoid "#1 1" when the handle is just the seat number
        if slot.name.strip() == str(slot.player_number):
            return f"#{slot.player_number}"
        return f"#{slot.player_number} {slot.name}"

    def snapshot(self) -> GameSnapshot:
        return GameSnapshot(
            team_name=self.team_name,
            state=self.state,
            expected_person_index=self.expected_person_index,
            current_person_index=self.current_person_index,
            leg_remaining=self.leg_remaining,
            game_remaining=self.game_remaining,
            progress=self.progress,
            last_message=self.last_message,
            wrong_baton=self.wrong_baton,
            device_status=self.device_status,
            roster=self.roster,
            last_resume_bonus=self.last_resume_bonus,
            bypass_baton=self.bypass_baton,
        )

    def _emit(self) -> None:
        snap = self.snapshot()
        for listener in self._listeners:
            listener(snap)

    def _event(self, name: str, **payload: Any) -> None:
        # Include team even for events fired from __init__, before the UI
        # has stored the session (board open when warmup_count is 0).
        payload.setdefault("team", self.team_name)
        self._on_event(name, payload)

    # --- derived ---

    @property
    def expected_person_index(self) -> int:
        return self.config.rotation[self.rotation_pos % len(self.config.rotation)]

    @property
    def expected_person(self) -> PersonConfig:
        return self.config.people[self.expected_person_index]

    def board_categories(self) -> list[tuple[str, str]]:
        """Visible board slots as (set_id, title)."""
        out: list[tuple[str, str]] = []
        for sid in self.progress.board_slots:
            s = self._sets_by_id.get(sid)
            if s is not None:
                out.append((sid, s.title))
        return out

    def current_question(self) -> Question | None:
        if self.progress.finished:
            return None
        if self.progress.phase == "board":
            return None
        if self.progress.in_redo:
            if not self.progress.redo_queue:
                return None
            if self.progress.redo_index >= len(self.progress.redo_queue):
                return None
            qid = self.progress.redo_queue[self.progress.redo_index]
            return self._find_question(qid)
        if self.progress.phase == "in_pick":
            sid = self.progress.pick_set_id
            if not sid:
                return None
            s = self._sets_by_id.get(sid)
            if s is None:
                return None
            idx = self.progress.set_cursors.get(sid, 0)
            if idx >= len(s.questions):
                return None
            return s.questions[idx]
        # warmup
        if self.progress.set_index >= len(self.sets):
            return None
        s = self.sets[self.progress.set_index]
        if self.progress.question_index >= len(s.questions):
            return None
        return s.questions[self.progress.question_index]

    def _find_question(self, qid: str) -> Question | None:
        for s in self.sets:
            for q in s.questions:
                if q.id == qid:
                    return q
        return None

    def _set_index_for_id(self, set_id: str) -> int:
        for i, s in enumerate(self.sets):
            if s.set_id == set_id:
                return i
        return 0

    def _remaining_in_set(self, set_id: str) -> int:
        s = self._sets_by_id.get(set_id)
        if s is None:
            return 0
        cursor = self.progress.set_cursors.get(set_id, 0)
        return max(0, len(s.questions) - cursor)

    def questions_locked(self) -> bool:
        if self.bypass_baton and self.progress.phase != "board":
            return False
        return self.state != RelayState.ACTIVE

    # --- board ---

    def _sets_with_remaining(self) -> list[str]:
        return [s.set_id for s in self.sets if self._remaining_in_set(s.set_id) > 0]

    def _is_deferred(self, set_id: str) -> bool:
        s = self._sets_by_id.get(set_id)
        return bool(s is not None and s.deferred)

    def _any_primary_remaining(self) -> bool:
        return any(
            not s.deferred and self._remaining_in_set(s.set_id) > 0 for s in self.sets
        )

    def _board_eligible(self, set_id: str) -> bool:
        """Deferred categories stay off the board until every primary is gone."""
        if self._remaining_in_set(set_id) <= 0:
            return False
        if self._is_deferred(set_id) and self._any_primary_remaining():
            return False
        return True

    def _rebuild_board_slots(self, *, defer_id: str | None = None) -> None:
        """Fill the board in config-file order every time.

        Top-left is always the first remaining eligible category, then the next,
        and so on — never a scrambled pool order. ``defer_id`` (just finished a
        pick but still has questions) stays off the board this round.
        """
        slots_n = min(self.config.questions.board_slots, MAX_BOARD_SLOTS)
        held = {defer_id} if defer_id else set()
        ordered = [
            s.set_id
            for s in self.sets
            if s.set_id not in held and self._board_eligible(s.set_id)
        ]
        self.progress.board_slots = ordered[:slots_n]
        on_board = set(self.progress.board_slots)
        self.progress.pool = [
            s.set_id
            for s in self.sets
            if s.set_id not in on_board and self._remaining_in_set(s.set_id) > 0
        ]

    def _enter_board(self, *, initial: bool = False) -> None:
        self.progress.phase = "board"
        self.progress.pick_set_id = None
        self.progress.pick_remaining = 0
        self.progress.pick_missed = []
        self.progress.in_redo = False
        self.progress.redo_queue = []
        self.progress.redo_index = 0

        self._rebuild_board_slots()

        if not self.progress.board_slots:
            self._pause_score("All categories complete.")
            return

        self.state = RelayState.CHOOSING_CATEGORY
        titles = [self._sets_by_id[sid].title for sid in self.progress.board_slots]
        self.last_message = "Choose a category."
        self._event(
            "board_opened",
            categories=list(self.progress.board_slots),
            titles=titles,
            initial=initial,
        )
        if self.bypass_baton:
            self._ensure_testing_seat()
        if not initial:
            self._emit()

    def select_category(self, set_id: str) -> bool:
        """Mouse pick from the board. Returns True if the pick started."""
        if self.state != RelayState.CHOOSING_CATEGORY or self.progress.phase != "board":
            return False
        if set_id not in self.progress.board_slots:
            return False
        remaining = self._remaining_in_set(set_id)
        if remaining <= 0:
            return False

        self.progress.board_slots = [s for s in self.progress.board_slots if s != set_id]
        pick_n = min(self.config.questions.questions_per_pick, remaining)
        self.progress.phase = "in_pick"
        self.progress.pick_set_id = set_id
        self.progress.pick_remaining = pick_n
        self.progress.pick_missed = []
        self.progress.set_index = self._set_index_for_id(set_id)
        self.progress.question_index = self.progress.set_cursors.get(set_id, 0)

        title = self._sets_by_id[set_id].title
        self.last_message = f"Category: {title}"
        self._event(
            "category_selected",
            set_id=set_id,
            title=title,
            questions=pick_n,
        )

        if self.bypass_baton:
            self.current_person_index = self.expected_person_index
        if self.current_person_index is not None:
            self.state = RelayState.ACTIVE
            if not self.timers_started:
                self.timers_started = True
                self._event("timers_started", source="board")
        else:
            self.state = RelayState.WAITING_FOR_BATON
            self.last_message = (
                f"Category: {title} — "
                f"{self.player_display(self.expected_person_index)} plug in."
            )
        self._emit()
        return True

    def return_to_board(self) -> bool:
        """Leave the open category and show the board again.

        Answers already scored stay. The category comes back if it still has
        questions, so it can be picked again.
        """
        if self.state == RelayState.PAUSED_SCORE or self.progress.finished:
            return False
        if self.progress.phase != "in_pick":
            return False

        sid = self.progress.pick_set_id
        self.progress.in_redo = False
        self.progress.redo_queue = []
        self.progress.redo_index = 0
        self.progress.pick_set_id = None
        self.progress.pick_remaining = 0
        self.progress.pick_missed = []

        self._rebuild_board_slots()

        if not self.progress.board_slots:
            self._pause_score("All categories complete.")
            return True

        self.progress.phase = "board"
        self.state = RelayState.CHOOSING_CATEGORY
        self.last_message = "Choose a category."
        self._ensure_testing_seat()
        self._event(
            "board_opened",
            categories=list(self.progress.board_slots),
            titles=[self._sets_by_id[s].title for s in self.progress.board_slots],
            initial=False,
        )
        self._emit()
        return True

    def cycle_board(self) -> bool:
        """Quick testing: page to the next slice of categories (config order).

        Nothing is marked skipped. Deferred categories stay held until every
        primary category is gone.
        """
        if not self.bypass_baton:
            return False
        if self.state != RelayState.CHOOSING_CATEGORY or self.progress.phase != "board":
            return False

        eligible = [s.set_id for s in self.sets if self._board_eligible(s.set_id)]
        slots_n = min(self.config.questions.board_slots, MAX_BOARD_SLOTS)
        if len(eligible) <= slots_n:
            return False

        start = 0
        if self.progress.board_slots:
            try:
                start = eligible.index(self.progress.board_slots[0])
            except ValueError:
                start = 0
            start = (start + slots_n) % len(eligible)
        rotated = eligible[start:] + eligible[:start]
        self.progress.board_slots = rotated[:slots_n]
        on_board = set(self.progress.board_slots)
        self.progress.pool = [
            s.set_id
            for s in self.sets
            if s.set_id not in on_board and self._remaining_in_set(s.set_id) > 0
        ]
        self.last_message = "Choose a category."
        self._ensure_testing_seat()
        self._event(
            "board_cycled",
            categories=list(self.progress.board_slots),
            titles=[self._sets_by_id[s].title for s in self.progress.board_slots],
        )
        self._emit()
        return True

    def _refill_and_return_to_board(self) -> None:
        finished_id = self.progress.pick_set_id
        # Still has questions → keep it off the board this round so a different
        # category fills its slot; it returns later in its config-file place.
        # If it is the only category left, putting it aside would empty the
        # board and end the game with questions still waiting (Fake Logos
        # after Google).
        defer = None
        if finished_id and self._remaining_in_set(finished_id) > 0:
            defer = finished_id

        self.progress.pick_set_id = None
        self.progress.pick_remaining = 0
        self.progress.pick_missed = []

        self._rebuild_board_slots(defer_id=defer)
        if not self.progress.board_slots and defer is not None:
            self._rebuild_board_slots(defer_id=None)

        if not self.progress.board_slots:
            self._pause_score("All categories complete.")
            return

        self.progress.phase = "board"
        self.state = RelayState.CHOOSING_CATEGORY
        self.last_message = "Choose a category."
        self._ensure_testing_seat()
        self._event(
            "board_opened",
            categories=list(self.progress.board_slots),
            titles=[self._sets_by_id[s].title for s in self.progress.board_slots],
            initial=False,
        )

    # --- input: baton ---

    def _ensure_testing_seat(self) -> None:
        """Keep the player who is up seated, without leaving the category screen."""
        if not self.bypass_baton or self.state == RelayState.PAUSED_SCORE:
            return
        self.wrong_baton = False
        self.current_person_index = self.expected_person_index
        if self.state in (RelayState.CHOOSING_CATEGORY, RelayState.ACTIVE):
            return
        self._activate(self.expected_person_index, source="quick", resume=False)

    def on_baton_reading(self, person_index: int | None, *, source: str = "baton") -> None:
        """person_index is seat index, or None for unknown / empty."""
        if self.bypass_baton or self.state == RelayState.PAUSED_SCORE:
            return

        if self.state == RelayState.CHOOSING_CATEGORY:
            if person_index is None:
                self.current_person_index = None
                self.wrong_baton = False
                self._emit()
                return
            if person_index < 0 or person_index >= self.config.team_size:
                self.wrong_baton = True
                self._emit()
                return
            expected = self.expected_person_index
            if person_index == expected or person_index == self.current_person_index:
                self.current_person_index = person_index
                self.wrong_baton = False
            else:
                self.wrong_baton = True
                self.last_message = (
                    f"Wrong player ({self.player_display(person_index)}). "
                    f"Need {self.player_display(expected)}. Choose a category."
                )
            self._emit()
            return

        if person_index is None:
            self.wrong_baton = False
            if self.state == RelayState.ACTIVE:
                who = (
                    self.player_display(self.current_person_index)
                    if self.current_person_index is not None
                    else self.player_display(self.expected_person_index)
                )
                self._freeze(f"Baton removed — {who} plug back in.", source=source)
            elif self.state == RelayState.WAITING_FOR_BATON:
                self.last_message = (
                    f"SWITCH — {self.player_display(self.expected_person_index)}."
                )
                self._emit()
            return

        if person_index < 0 or person_index >= self.config.team_size:
            self.wrong_baton = True
            self.last_message = "Unknown baton."
            self._event("baton_rejected", reason="out_of_range", source=source)
            self._emit()
            return

        expected = self.expected_person_index

        if self.state in (RelayState.WAITING_FOR_BATON, RelayState.FROZEN, RelayState.DISCONNECTED):
            # Hardware readings ignored while disconnected; reconnect path restores state first.
            # Fake/keyboard source may still force a seat change while disconnected.
            if self.state == RelayState.DISCONNECTED and source == "baton":
                return

            if self.state == RelayState.FROZEN and self.current_person_index is not None:
                # Same person may resume
                if person_index == self.current_person_index:
                    self._activate(person_index, source=source, resume=True)
                    return

            if person_index == expected:
                self._activate(person_index, source=source, resume=False)
            else:
                got = self.player_display(person_index)
                need = self.player_display(expected)
                self.wrong_baton = True
                self.last_message = f"Wrong player ({got}). Need {need}."
                self._event(
                    "baton_rejected",
                    reason="wrong_person",
                    got=person_index,
                    got_name=self.roster[person_index].name,
                    got_player_number=self.roster[person_index].player_number,
                    expected=expected,
                    expected_name=self.roster[expected].name,
                    expected_player_number=self.roster[expected].player_number,
                    source=source,
                )
                self._emit()
            return

        if self.state == RelayState.ACTIVE:
            if person_index != self.current_person_index:
                # Treated as removal + wrong, or mid-leg swap attempt: freeze if different
                self._freeze("Baton changed.", source=source)
            return

    def on_device_disconnected(self) -> None:
        if self.bypass_baton or self.state in (RelayState.DISCONNECTED, RelayState.PAUSED_SCORE):
            return
        self._pre_disconnect_state = self.state
        self.state = RelayState.DISCONNECTED
        self.last_message = "Device disconnected. Reconnect the board or use keyboard seating."
        self.device_status = "disconnected"
        self._event("device_disconnected")
        self._emit()

    def on_device_reconnected(self) -> None:
        if self.state != RelayState.DISCONNECTED:
            self.device_status = "connected"
            self._emit()
            return
        prior = self._pre_disconnect_state
        self._pre_disconnect_state = None
        self.device_status = "connected"
        if prior == RelayState.CHOOSING_CATEGORY:
            self.state = RelayState.CHOOSING_CATEGORY
            self.last_message = "Reconnected — choose a category."
        elif prior in (RelayState.ACTIVE, RelayState.FROZEN) and self.current_person_index is not None:
            self.state = RelayState.FROZEN
            who = self.current_person_index
            self.last_message = (
                f"Reconnected — {self.player_display(who)} plug back in."
            )
        else:
            self.state = RelayState.WAITING_FOR_BATON
            self.current_person_index = None
            self.last_message = (
                f"Reconnected. SWITCH — {self.player_display(self.expected_person_index)}."
            )
        self._event("device_reconnected")
        self._emit()

    def set_device_status(self, status: str) -> None:
        self.device_status = status
        self._emit()

    def _activate(self, person_index: int, *, source: str, resume: bool) -> None:
        self.wrong_baton = False
        self.current_person_index = person_index
        slot = self.roster[person_index]
        person = self.config.people[person_index]
        bonus = 0.0
        if resume:
            bonus = float(self.config.timers.resume_bonus_seconds)
            if bonus > 0:
                self.leg_remaining += bonus
                self.game_remaining += bonus
            self.last_resume_bonus = bonus
            if bonus > 0:
                self.last_message = (
                    f"{self.player_display(person_index)} resumed "
                    f"(+{bonus:g}s). Team {self.team_name}."
                )
            else:
                self.last_message = (
                    f"{self.player_display(person_index)} resumed. "
                    f"Team {self.team_name}."
                )
        else:
            self.leg_remaining = float(self.config.timers.leg_seconds)
            self.last_resume_bonus = 0.0
            self.last_message = (
                f"{self.player_display(person_index)} active. Team {self.team_name}."
            )
        if not self.timers_started:
            self.timers_started = True
            self._event("timers_started", source=source)
        self.state = RelayState.ACTIVE
        self._event(
            "baton_accepted",
            person_index=person_index,
            person_id=person.id,
            player_number=slot.player_number,
            player_name=slot.name,
            resume=resume,
            resume_bonus_seconds=bonus,
            source=source,
        )
        self._emit()

    def _freeze(self, message: str, *, source: str) -> None:
        self.state = RelayState.FROZEN
        self.last_message = message
        who_idx = (
            self.current_person_index
            if self.current_person_index is not None
            else self.expected_person_index
        )
        slot = self.roster[who_idx]
        self._event(
            "frozen",
            message=message,
            source=source,
            player_number=slot.player_number,
            player_name=slot.name,
            person_index=who_idx,
            team=self.team_name,
        )
        self._emit()

    def advance_rotation(self) -> None:
        self.rotation_pos = (self.rotation_pos + 1) % len(self.config.rotation)
        self.current_person_index = None
        self.leg_remaining = float(self.config.timers.leg_seconds)
        # Stay on board if choosing; otherwise wait for next baton.
        # Quick testing keeps whoever is up seated, so a handoff never asks for a baton.
        if self.bypass_baton:
            self.current_person_index = self.expected_person_index
            self.wrong_baton = False
            if self.progress.phase == "board":
                self.state = RelayState.CHOOSING_CATEGORY
                self.last_message = "Choose a category."
            else:
                self.state = RelayState.ACTIVE
                who = self.player_display(self.expected_person_index)
                self.last_message = f"{who} active. Team {self.team_name}."
        elif self.progress.phase == "board":
            self.state = RelayState.CHOOSING_CATEGORY
            self.last_message = (
                f"SWITCH — {self.player_display(self.expected_person_index)} "
                f"(choose a category)."
            )
        else:
            self.state = RelayState.WAITING_FOR_BATON
            self.last_message = f"SWITCH — {self.player_display(self.expected_person_index)} next."
        nxt = self.expected_person_index
        self.wrong_baton = False
        self._event(
            "leg_swap",
            expected=nxt,
            expected_player_number=self.roster[nxt].player_number,
            expected_player_name=self.roster[nxt].name,
        )
        self._emit()

    # --- timers ---

    def tick(self, dt: float) -> None:
        if dt <= 0 or self.state == RelayState.PAUSED_SCORE:
            return

        # Board menu: neither timer runs, and nothing else changes on a tick.
        # Emitting here re-rendered the category buttons ~10×/s and ate clicks.
        if self.state == RelayState.CHOOSING_CATEGORY:
            return

        # Timers stay frozen until the first correct baton is accepted.
        if not self.timers_started:
            self._emit()
            return

        # Game timer runs in active/frozen/waiting/disconnected.
        # Wall-clock pause while the app is down is handled by checkpoint restore.
        if self.state in (
            RelayState.ACTIVE,
            RelayState.FROZEN,
            RelayState.WAITING_FOR_BATON,
            RelayState.DISCONNECTED,
        ):
            self.game_remaining = max(0.0, self.game_remaining - dt)
            if self.game_remaining <= 0:
                self._pause_score("Game time expired.")
                return

        if self.state == RelayState.ACTIVE:
            self.leg_remaining = max(0.0, self.leg_remaining - dt)
            if self.leg_remaining <= 0:
                self._event("leg_expired")
                self.advance_rotation()
                return
        elif self.state == RelayState.FROZEN and self.config.timers.leg_runs_while_frozen:
            self.leg_remaining = max(0.0, self.leg_remaining - dt)
            if self.leg_remaining <= 0:
                self._event("leg_expired")
                self.advance_rotation()
                return

        self._emit()

    def time_used_seconds(self) -> float:
        """Game-clock time used. Bonuses that add time back make this smaller."""
        return round(
            max(0.0, float(self.config.timers.game_seconds) - self.game_remaining),
            2,
        )

    def _set_for_question(self, question: Question) -> tuple[str, str]:
        for s in self.sets:
            if any(q.id == question.id for q in s.questions):
                return s.set_id, s.title
        return "", ""

    def _attempt_fields(
        self,
        question: Question,
        *,
        answer: Any,
        skipped: bool,
        result: ScoreResult | None,
        redo: bool,
    ) -> dict[str, Any]:
        set_id, set_title = self._set_for_question(question)
        who_idx = (
            self.current_person_index
            if self.current_person_index is not None
            else self.expected_person_index
        )
        slot = self.roster[who_idx]
        used = self.time_used_seconds()
        return {
            "question_id": question.id,
            "question_type": question.type,
            "question_prompt": question.prompt,
            "question_points": question.points,
            "set_id": set_id,
            "set_title": set_title,
            "answer": answer,
            "answer_text": "" if skipped else format_submitted(question, answer),
            "expected_text": format_expected(question),
            "correct": False if result is None else result.correct,
            "partial": False if result is None else result.partial,
            "redo": redo,
            "skipped": skipped,
            "points": 0.0 if result is None else result.points,
            "max_points": question.points if result is None else result.max_points,
            "feedback": "" if result is None else result.feedback,
            "phase": "redo" if self.progress.in_redo else self.progress.phase,
            "person_index": who_idx,
            "player_number": slot.player_number,
            "player_name": slot.name,
            "local_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "time_used_seconds": used,
            "time_used": format_duration(used),
            "game_remaining": round(self.game_remaining, 2),
            "leg_remaining": round(self.leg_remaining, 2),
            "game_limit_seconds": float(self.config.timers.game_seconds),
            "total_score": round(self.progress.total_score, 3),
        }

    def _pause_score(self, message: str) -> None:
        self.state = RelayState.PAUSED_SCORE
        self.last_message = message
        self.progress.finished = True
        used = self.time_used_seconds()
        self._event(
            "game_ended",
            score=self.progress.total_score,
            reason=message,
            game_remaining=round(self.game_remaining, 2),
            leg_remaining=round(self.leg_remaining, 2),
            game_limit_seconds=float(self.config.timers.game_seconds),
            time_used_seconds=used,
            time_used=format_duration(used),
            local_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
        self._emit()

    # --- answers ---

    def submit_answer(self, answer: Any) -> ScoreResult | None:
        if self.questions_locked():
            return None
        question = self.current_question()
        if question is None:
            return None

        is_redo = self.progress.in_redo
        result = question.score(answer, self.config.scoring)
        result = self._adjust_miss_cost(question, answer, result)
        if is_redo:
            result = ScoreResult(
                points=result.points * self.config.scoring.redo_multiplier,
                max_points=result.max_points * self.config.scoring.redo_multiplier,
                correct=result.correct,
                feedback=result.feedback + " (redo)",
                partial=result.partial,
            )

        qid = question.id
        prev = self.progress.answered.get(qid)
        if prev is None:
            self.progress.total_score += result.points
        else:
            # Replace score if redoing
            self.progress.total_score += result.points - prev.points
        self.progress.answered[qid] = result

        if not result.correct and qid not in self.progress.missed_ids:
            self.progress.missed_ids.append(qid)
        if result.correct and qid in self.progress.missed_ids:
            self.progress.missed_ids.remove(qid)

        if self.progress.phase == "in_pick" and not is_redo:
            if not result.correct and qid not in self.progress.pick_missed:
                self.progress.pick_missed.append(qid)
            if result.correct and qid in self.progress.pick_missed:
                self.progress.pick_missed.remove(qid)

        self._event(
            "answer",
            **self._attempt_fields(
                question,
                answer=answer,
                skipped=False,
                result=result,
                redo=is_redo,
            ),
        )
        # Wrong / partial: stay on the same question so teams can keep trying.
        # Correct (or skip) advances.
        if result.correct:
            self.last_message = result.feedback or "Correct."
            self._advance_after_answer()
        else:
            self.last_message = (result.feedback or "Incorrect") + " — try again."
        self._emit()
        return result

    def _adjust_miss_cost(self, question: Question, answer: Any, result: ScoreResult) -> ScoreResult:
        """Shrink a multiple-choice award once per distinct wrong guess.

        The team score stays put until the right letter. That guess pays whatever
        is left. Guessing the same wrong letter again does not take another slice.
        """
        if not isinstance(question, MultipleChoice) or not question.shrinks_when_wrong():
            return result
        if result.feedback == "Invalid choice" or isinstance(answer, bool):
            return result
        try:
            choice = int(answer)
        except (TypeError, ValueError):
            return result
        choices = question.choices or []
        if choice < 0 or choice >= len(choices):
            return result

        spent = self.progress.spent_choices.setdefault(question.id, [])
        if result.correct:
            award = question.value_after_misses(len(spent))
            return ScoreResult(
                award,
                question.points,
                True,
                "Correct",
                partial=award < question.points,
            )
        if choice in spent:
            return ScoreResult(0, question.points, False, "Already tried that one")
        spent.append(choice)
        left = question.value_after_misses(len(spent))
        return ScoreResult(0, question.points, False, f"Incorrect — worth {left:g} now")

    def skip_question(self, *, organizer: bool = False) -> None:
        question = self.current_question()
        if question is None:
            return
        if self.questions_locked() and not organizer:
            return
        qid = question.id
        if qid not in self.progress.missed_ids:
            self.progress.missed_ids.append(qid)
        if self.progress.phase == "in_pick" and not self.progress.in_redo:
            if qid not in self.progress.pick_missed:
                self.progress.pick_missed.append(qid)
        self._event(
            "skip",
            organizer=organizer,
            **self._attempt_fields(
                question,
                answer=None,
                skipped=True,
                result=None,
                redo=self.progress.in_redo,
            ),
        )
        self._advance_after_answer()
        self._emit()

    def _sync_cursor_from_warmup(self) -> None:
        if self.progress.set_index < len(self.sets):
            sid = self.sets[self.progress.set_index].set_id
            self.progress.set_cursors[sid] = self.progress.question_index

    def _advance_after_answer(self) -> None:
        if self.progress.in_redo:
            self.progress.redo_index += 1
            if self.progress.redo_index >= len(self.progress.redo_queue):
                self.progress.in_redo = False
                self.progress.redo_queue = []
                self.progress.redo_index = 0
                if self.progress.phase == "in_pick":
                    self._refill_and_return_to_board()
                elif self.progress.phase == "warmup":
                    self._warmup_next_after_set()
            return

        if self.progress.phase == "in_pick":
            sid = self.progress.pick_set_id
            if sid:
                cursor = self.progress.set_cursors.get(sid, 0) + 1
                self.progress.set_cursors[sid] = cursor
                self.progress.question_index = cursor
            self.progress.pick_remaining = max(0, self.progress.pick_remaining - 1)
            exhausted = sid is None or self._remaining_in_set(sid) <= 0
            if self.progress.pick_remaining <= 0 or exhausted:
                if self.config.questions.redo_missed_at_set_end and self.progress.pick_missed:
                    self.progress.in_redo = True
                    self.progress.redo_queue = list(self.progress.pick_missed)
                    self.progress.redo_index = 0
                    self.last_message = "Redo pass for missed questions."
                    return
                self._refill_and_return_to_board()
            return

        # Warm-up linear advance
        self.progress.question_index += 1
        self.progress.warmup_done += 1
        self._sync_cursor_from_warmup()

        if self.progress.warmup_done >= self.config.questions.warmup_count:
            self._enter_board()
            return

        s = self.sets[self.progress.set_index]
        if self.progress.question_index >= len(s.questions):
            if self.config.questions.redo_missed_at_set_end:
                set_qids = {q.id for q in s.questions}
                missed = [qid for qid in self.progress.missed_ids if qid in set_qids]
                if missed:
                    self.progress.in_redo = True
                    self.progress.redo_queue = missed
                    self.progress.redo_index = 0
                    self.last_message = "Redo pass for missed questions."
                    return
            self._warmup_next_after_set()

    def _warmup_next_after_set(self) -> None:
        self.progress.set_index += 1
        self.progress.question_index = 0
        if self.progress.set_index >= len(self.sets):
            # No more warm-up material — go to board (may end if empty)
            self._enter_board()
            return
        if self.progress.warmup_done >= self.config.questions.warmup_count:
            self._enter_board()
            return
        self.last_message = f"Set: {self.sets[self.progress.set_index].title}"
        self._event("set_started", set_id=self.sets[self.progress.set_index].set_id)
