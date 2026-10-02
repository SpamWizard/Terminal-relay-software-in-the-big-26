"""Relay state machine and game session logic."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable

from baton_relay.config import AppConfig, PersonConfig
from baton_relay.questions.base import Question, QuestionSet, ScoreResult


class RelayState(Enum):
    WAITING_FOR_BATON = auto()
    ACTIVE = auto()
    FROZEN = auto()
    DISCONNECTED = auto()
    PAUSED_SCORE = auto()


@dataclass
class Progress:
    set_index: int = 0
    question_index: int = 0
    # Within a set redo pass
    in_redo: bool = False
    redo_queue: list[str] = field(default_factory=list)  # question ids
    redo_index: int = 0
    answered: dict[str, ScoreResult] = field(default_factory=dict)
    missed_ids: list[str] = field(default_factory=list)
    total_score: float = 0.0
    finished: bool = False


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


Listener = Callable[[GameSnapshot], None]


class GameSession:
    """Core relay rules. UI and input sources call into this; timers tick via `tick`."""

    def __init__(
        self,
        config: AppConfig,
        sets: list[QuestionSet],
        *,
        team_name: str = "",
        on_event: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> None:
        if not sets:
            raise ValueError("at least one question set is required")
        self.config = config
        self.sets = sets
        self.team_name = team_name
        self._on_event = on_event or (lambda *_: None)

        self.state = RelayState.WAITING_FOR_BATON
        self.rotation_pos = 0  # index into config.rotation
        self.current_person_index: int | None = None
        self.leg_remaining = float(config.timers.leg_seconds)
        self.game_remaining = float(config.timers.game_seconds)
        self.timers_started = False
        self.progress = Progress()
        self.last_message = "SWITCH — plug in to begin."
        self.wrong_baton = False
        self.device_status = "unknown"
        self._pre_disconnect_state: RelayState | None = None
        self._listeners: list[Listener] = []

    # --- observers ---

    def add_listener(self, listener: Listener) -> None:
        self._listeners.append(listener)

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
        )

    def _emit(self) -> None:
        snap = self.snapshot()
        for listener in self._listeners:
            listener(snap)

    def _event(self, name: str, **payload: Any) -> None:
        self._on_event(name, payload)

    # --- derived ---

    @property
    def expected_person_index(self) -> int:
        return self.config.rotation[self.rotation_pos % len(self.config.rotation)]

    @property
    def expected_person(self) -> PersonConfig:
        return self.config.people[self.expected_person_index]

    def current_question(self) -> Question | None:
        if self.progress.finished:
            return None
        if self.progress.in_redo:
            if not self.progress.redo_queue:
                return None
            qid = self.progress.redo_queue[self.progress.redo_index]
            return self._find_question(qid)
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

    def questions_locked(self) -> bool:
        return self.state != RelayState.ACTIVE

    # --- input: baton ---

    def on_baton_reading(self, person_index: int | None, *, source: str = "baton") -> None:
        """person_index is seat index, or None for unknown / empty."""
        if self.state == RelayState.PAUSED_SCORE:
            return

        if person_index is None:
            self.wrong_baton = False
            if self.state == RelayState.ACTIVE:
                self._freeze("Baton removed — plug back in.", source=source)
            elif self.state == RelayState.WAITING_FOR_BATON:
                self.last_message = f"SWITCH — person {self.expected_person.label}."
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
            # From DISCONNECTED, still allow correct baton if device came back via override path
            if self.state == RelayState.DISCONNECTED and source == "baton":
                # Device readings ignored while disconnected unless we reconnect separately
                pass

            if self.state == RelayState.FROZEN and self.current_person_index is not None:
                # Same person may resume
                if person_index == self.current_person_index:
                    self._activate(person_index, source=source, resume=True)
                    return

            if person_index == expected:
                self._activate(person_index, source=source, resume=False)
            else:
                person = self.config.people[person_index]
                self.wrong_baton = True
                self.last_message = (
                    f"Wrong person ({person.label}). "
                    f"Need person {self.expected_person.label}."
                )
                self._event(
                    "baton_rejected",
                    reason="wrong_person",
                    got=person_index,
                    expected=expected,
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
        if self.state in (RelayState.DISCONNECTED, RelayState.PAUSED_SCORE):
            return
        self._pre_disconnect_state = self.state
        if self.state == RelayState.ACTIVE:
            # Preserve question; freeze visually via DISCONNECTED
            pass
        self.state = RelayState.DISCONNECTED
        self.last_message = "Device disconnected. Use controller override or reconnect."
        self.device_status = "disconnected"
        self._event("device_disconnected")
        self._emit()

    def on_device_reconnected(self) -> None:
        if self.state != RelayState.DISCONNECTED:
            self.device_status = "connected"
            self._emit()
            return
        # Return to waiting/frozen; require baton again
        self.state = RelayState.WAITING_FOR_BATON
        self.current_person_index = None
        self.last_message = f"Reconnected. SWITCH — person {self.expected_person.label}."
        self.device_status = "connected"
        self._pre_disconnect_state = None
        self._event("device_reconnected")
        self._emit()

    def set_device_status(self, status: str) -> None:
        self.device_status = status
        self._emit()

    def _activate(self, person_index: int, *, source: str, resume: bool) -> None:
        self.wrong_baton = False
        self.current_person_index = person_index
        if not resume:
            self.leg_remaining = float(self.config.timers.leg_seconds)
        if not self.timers_started:
            self.timers_started = True
            self._event("timers_started", source=source)
        self.state = RelayState.ACTIVE
        person = self.config.people[person_index]
        self.last_message = f"Person {person.label} active."
        self._event(
            "baton_accepted",
            person_index=person_index,
            person_id=person.id,
            resume=resume,
            source=source,
        )
        self._emit()

    def _freeze(self, message: str, *, source: str) -> None:
        self.state = RelayState.FROZEN
        self.last_message = message
        self._event("frozen", message=message, source=source)
        self._emit()

    def advance_rotation(self) -> None:
        self.rotation_pos = (self.rotation_pos + 1) % len(self.config.rotation)
        self.current_person_index = None
        self.leg_remaining = float(self.config.timers.leg_seconds)
        self.state = RelayState.WAITING_FOR_BATON
        self.last_message = f"SWITCH — person {self.expected_person.label} next."
        self.wrong_baton = False
        self._event("leg_swap", expected=self.expected_person_index)
        self._emit()

    # --- timers ---

    def tick(self, dt: float) -> None:
        if dt <= 0 or self.state == RelayState.PAUSED_SCORE:
            return

        # Timers stay frozen until the first correct baton is accepted.
        if not self.timers_started:
            self._emit()
            return

        # Game timer runs in active/frozen/waiting (paused only while app down — handled by checkpoint)
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

    def _pause_score(self, message: str) -> None:
        self.state = RelayState.PAUSED_SCORE
        self.last_message = message
        self.progress.finished = True
        self._event("game_ended", score=self.progress.total_score, reason=message)
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

        self._event(
            "answer",
            question_id=qid,
            points=result.points,
            correct=result.correct,
            redo=is_redo,
            answer=answer,
        )
        self._advance_after_answer()
        self._emit()
        return result

    def skip_question(self, *, organizer: bool = False) -> None:
        question = self.current_question()
        if question is None:
            return
        if self.questions_locked() and not organizer:
            return
        qid = question.id
        if qid not in self.progress.missed_ids:
            self.progress.missed_ids.append(qid)
        self._event("skip", question_id=qid, organizer=organizer)
        self._advance_after_answer()
        self._emit()

    def _advance_after_answer(self) -> None:
        if self.progress.in_redo:
            self.progress.redo_index += 1
            if self.progress.redo_index >= len(self.progress.redo_queue):
                self.progress.in_redo = False
                self.progress.redo_queue = []
                self.progress.redo_index = 0
                self._next_set()
            return

        self.progress.question_index += 1
        s = self.sets[self.progress.set_index]
        if self.progress.question_index >= len(s.questions):
            # End of set — maybe redo missed from this set
            if self.config.questions.redo_missed_at_set_end:
                set_ids = {q.id for q in s.questions}
                missed = [qid for qid in self.progress.missed_ids if qid in set_ids]
                if missed:
                    self.progress.in_redo = True
                    self.progress.redo_queue = missed
                    self.progress.redo_index = 0
                    self.last_message = "Redo pass for missed questions."
                    return
            self._next_set()

    def _next_set(self) -> None:
        self.progress.set_index += 1
        self.progress.question_index = 0
        if self.progress.set_index >= len(self.sets):
            self._pause_score("All questions complete.")
        else:
            self.last_message = f"Set: {self.sets[self.progress.set_index].title}"
            self._event("set_started", set_id=self.sets[self.progress.set_index].set_id)
