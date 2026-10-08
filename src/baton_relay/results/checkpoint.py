"""Persist / restore an in-progress game session."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from baton_relay.config import AppConfig
from baton_relay.questions.base import QuestionSet, ScoreResult
from baton_relay.state.machine import GameSession, PlayerSlot, Progress, RelayState


def checkpoint_path_for(run_dir: Path) -> Path:
    return run_dir / "checkpoint.json"


def progress_to_dict(progress: Progress) -> dict[str, Any]:
    return {
        "set_index": progress.set_index,
        "question_index": progress.question_index,
        "in_redo": progress.in_redo,
        "redo_queue": list(progress.redo_queue),
        "redo_index": progress.redo_index,
        "answered": {
            qid: {
                "points": r.points,
                "max_points": r.max_points,
                "correct": r.correct,
                "feedback": r.feedback,
                "partial": r.partial,
            }
            for qid, r in progress.answered.items()
        },
        "missed_ids": list(progress.missed_ids),
        "total_score": progress.total_score,
        "finished": progress.finished,
    }


def progress_from_dict(raw: dict[str, Any]) -> Progress:
    answered_raw = raw.get("answered") or {}
    answered: dict[str, ScoreResult] = {}
    for qid, val in answered_raw.items():
        if isinstance(val, dict):
            answered[qid] = ScoreResult(
                points=float(val.get("points", 0)),
                max_points=float(val.get("max_points", 0)),
                correct=bool(val.get("correct", False)),
                feedback=str(val.get("feedback", "")),
                partial=bool(val.get("partial", False)),
            )
    return Progress(
        set_index=int(raw.get("set_index", 0)),
        question_index=int(raw.get("question_index", 0)),
        in_redo=bool(raw.get("in_redo", False)),
        redo_queue=list(raw.get("redo_queue") or []),
        redo_index=int(raw.get("redo_index", 0)),
        answered=answered,
        missed_ids=list(raw.get("missed_ids") or []),
        total_score=float(raw.get("total_score", 0)),
        finished=bool(raw.get("finished", False)),
    )


def roster_to_list(roster: tuple[PlayerSlot, ...]) -> list[dict[str, Any]]:
    return [
        {
            "person_index": s.person_index,
            "player_number": s.player_number,
            "name": s.name,
            "color": s.color,
            "seat_label": s.seat_label,
        }
        for s in roster
    ]


def roster_from_list(raw: list[Any], config: AppConfig) -> tuple[PlayerSlot, ...]:
    slots: list[PlayerSlot] = []
    for i in range(config.team_size):
        if i < len(raw) and isinstance(raw[i], dict):
            entry = raw[i]
            slots.append(
                PlayerSlot(
                    person_index=int(entry.get("person_index", i)),
                    player_number=int(entry.get("player_number", i + 1)),
                    name=str(entry.get("name") or config.people[i].label),
                    color=str(entry.get("color") or config.people[i].color),
                    seat_label=str(entry.get("seat_label") or config.people[i].label),
                )
            )
        else:
            slots.append(
                PlayerSlot(
                    person_index=i,
                    player_number=i + 1,
                    name=config.people[i].label,
                    color=config.people[i].color,
                    seat_label=config.people[i].label,
                )
            )
    return tuple(slots)


def session_to_dict(session: GameSession) -> dict[str, Any]:
    return {
        "version": 1,
        "team_name": session.team_name,
        "roster": roster_to_list(session.roster),
        "state": session.state.name,
        "rotation_pos": session.rotation_pos,
        "current_person_index": session.current_person_index,
        "leg_remaining": session.leg_remaining,
        "game_remaining": session.game_remaining,
        "timers_started": session.timers_started,
        "progress": progress_to_dict(session.progress),
        "last_message": session.last_message,
        "wrong_baton": session.wrong_baton,
        "device_status": session.device_status,
        "last_resume_bonus": session.last_resume_bonus,
    }


def apply_checkpoint(session: GameSession, data: dict[str, Any], config: AppConfig) -> None:
    session.team_name = str(data.get("team_name") or session.team_name)
    session.roster = roster_from_list(list(data.get("roster") or []), config)
    state_name = str(data.get("state") or "WAITING_FOR_BATON")
    try:
        state = RelayState[state_name]
    except KeyError:
        state = RelayState.WAITING_FOR_BATON
    # Never resume into a finished score screen via checkpoint
    if state == RelayState.PAUSED_SCORE:
        state = RelayState.WAITING_FOR_BATON
    session.state = state
    session.rotation_pos = int(data.get("rotation_pos", 0))
    cur = data.get("current_person_index")
    session.current_person_index = int(cur) if cur is not None else None
    session.leg_remaining = float(data.get("leg_remaining", config.timers.leg_seconds))
    session.game_remaining = float(data.get("game_remaining", config.timers.game_seconds))
    session.timers_started = bool(data.get("timers_started", False))
    session.progress = progress_from_dict(dict(data.get("progress") or {}))
    session.progress.finished = False
    session.last_message = str(
        data.get("last_message")
        or f"Resumed — {session.player_display(session.expected_person_index)} plug in."
    )
    session.wrong_baton = bool(data.get("wrong_baton", False))
    session.device_status = str(data.get("device_status") or "unknown")
    session.last_resume_bonus = float(data.get("last_resume_bonus", 0))
    # After app restart, require baton again if they were mid-leg
    if session.state == RelayState.ACTIVE:
        session.state = RelayState.FROZEN
        who = (
            session.current_person_index
            if session.current_person_index is not None
            else session.expected_person_index
        )
        session.last_message = (
            f"Run resumed — {session.player_display(who)} plug back in."
        )


def save_checkpoint(path: Path, session: GameSession) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(session_to_dict(session), indent=2, ensure_ascii=False, default=str)
        + "\n",
        encoding="utf-8",
    )


def load_checkpoint(
    path: Path,
    config: AppConfig,
    sets: list[QuestionSet],
    *,
    on_event: Callable[[str, dict[str, Any]], None] | None = None,
) -> GameSession:
    data = json.loads(path.read_text(encoding="utf-8"))
    roster_raw = list(data.get("roster") or [])
    names = [
        str(entry.get("name", ""))
        for entry in roster_raw
        if isinstance(entry, dict)
    ]
    session = GameSession(
        config,
        sets,
        team_name=str(data.get("team_name") or ""),
        player_names=names,
        on_event=on_event,
    )
    apply_checkpoint(session, data, config)
    return session
