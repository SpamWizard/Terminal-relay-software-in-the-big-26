"""Load and validate question JSON files at startup."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from baton_relay.questions.base import Question, QuestionSet
from baton_relay.questions.images import QuestionImage, QuestionImageError, resolve_question_images
from baton_relay.questions.registry import ensure_builtin_types_loaded, get_builder, known_types


class QuestionLoadError(Exception):
    """Raised when a question file is invalid."""


def _require(data: dict[str, Any], key: str, where: str) -> Any:
    if key not in data:
        raise QuestionLoadError(f"{where}: missing required field '{key}'")
    return data[key]


def _load_images(qdata: dict[str, Any], where: str, base_dir: Path) -> list[QuestionImage] | None:
    """Optional pictures. Missing key means text only; a present key must be 1-8 files."""
    if "images" not in qdata:
        return None
    try:
        return resolve_question_images(qdata["images"], where=where, base_dir=base_dir)
    except QuestionImageError as exc:
        raise QuestionLoadError(str(exc)) from exc


def load_question_file(path: Path) -> QuestionSet:
    ensure_builtin_types_loaded()
    where = str(path)
    if not path.is_file():
        raise QuestionLoadError(f"{where}: file not found")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise QuestionLoadError(f"{where}: JSON parse error: {exc}") from exc
    if not isinstance(data, dict):
        raise QuestionLoadError(f"{where}: root must be an object")

    set_id = str(_require(data, "set_id", where))
    title = str(_require(data, "title", where))
    questions_raw = _require(data, "questions", where)
    if not isinstance(questions_raw, list) or not questions_raw:
        raise QuestionLoadError(f"{where}: 'questions' must be a non-empty array")

    questions: list[Question] = []
    seen_ids: set[str] = set()
    for i, qdata in enumerate(questions_raw):
        qwhere = f"{where}: questions[{i}]"
        if not isinstance(qdata, dict):
            raise QuestionLoadError(f"{qwhere}: expected object")
        qid = str(_require(qdata, "id", qwhere))
        if qid in seen_ids:
            raise QuestionLoadError(f"{qwhere}: duplicate question id '{qid}'")
        seen_ids.add(qid)
        qtype = str(_require(qdata, "type", qwhere))
        _require(qdata, "prompt", qwhere)
        images = _load_images(qdata, qwhere, path.parent)
        builder = get_builder(qtype)
        if builder is None:
            raise QuestionLoadError(
                f"{qwhere}: unknown type '{qtype}' (known: {', '.join(known_types())})"
            )
        try:
            question = builder(qdata)
        except Exception as exc:
            raise QuestionLoadError(f"{qwhere}: {exc}") from exc
        question.images = images
        questions.append(question)

    return QuestionSet(set_id=set_id, title=title, questions=questions, source_path=where)


def load_all_question_files(paths: list[Path] | tuple[Path, ...]) -> list[QuestionSet]:
    sets: list[QuestionSet] = []
    seen_set_ids: set[str] = set()
    all_qids: set[str] = set()
    for path in paths:
        qset = load_question_file(Path(path))
        if qset.set_id in seen_set_ids:
            raise QuestionLoadError(f"{path}: duplicate set_id '{qset.set_id}'")
        seen_set_ids.add(qset.set_id)
        for q in qset.questions:
            if q.id in all_qids:
                raise QuestionLoadError(f"{path}: duplicate question id across sets: '{q.id}'")
            all_qids.add(q.id)
        sets.append(qset)
    return sets
