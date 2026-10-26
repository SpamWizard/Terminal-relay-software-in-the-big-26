"""Load and validate question JSON files and HC challenge folders at startup."""

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


def _build_question(
    qdata: dict[str, Any],
    *,
    where: str,
    base_dir: Path,
    public_dir: Path | None = None,
) -> Question:
    if not isinstance(qdata, dict):
        raise QuestionLoadError(f"{where}: expected object")
    qid = str(_require(qdata, "id", where))
    qtype = str(_require(qdata, "type", where))
    _require(qdata, "prompt", where)
    images = _load_images(qdata, where, base_dir)
    builder = get_builder(qtype)
    if builder is None:
        raise QuestionLoadError(
            f"{where}: unknown type '{qtype}' (known: {', '.join(known_types())})"
        )
    payload = dict(qdata)
    if qtype == "desk":
        if public_dir is None:
            raise QuestionLoadError(f"{where}: desk questions require a challenge folder")
        payload["public_dir"] = str(public_dir.resolve())
        if not payload.get("accepted"):
            raise QuestionLoadError(f"{where}: desk.accepted must be a non-empty list")
    try:
        question = builder(payload)
    except Exception as exc:
        raise QuestionLoadError(f"{where}: {exc}") from exc
    question.images = images
    if qtype == "desk":
        assert public_dir is not None
        page = getattr(question, "page_file", None)
        if page:
            page_path = (public_dir / str(page)).resolve()
            try:
                page_path.relative_to(public_dir.resolve())
            except ValueError as exc:
                raise QuestionLoadError(f"{where}: page_file escapes public/") from exc
            if not page_path.is_file():
                raise QuestionLoadError(f"{where}: page_file not found: {page}")
        panes = getattr(question, "panes", None) or []
        if "page" in panes and not page:
            raise QuestionLoadError(f"{where}: pane 'page' requires page_file")
    return question


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
        q = _build_question(qdata, where=qwhere, base_dir=path.parent)
        if q.id in seen_ids:
            raise QuestionLoadError(f"{qwhere}: duplicate question id '{q.id}'")
        seen_ids.add(q.id)
        questions.append(q)

    return QuestionSet(set_id=set_id, title=title, questions=questions, source_path=where)


def _compact_challenge_to_set(data: dict[str, Any], where: str) -> dict[str, Any]:
    """Allow a one-question challenge.json without a questions[] wrapper."""
    if "questions" in data:
        return data
    for key in ("id", "type", "prompt", "points"):
        if key not in data:
            raise QuestionLoadError(f"{where}: compact challenge missing '{key}' (or use questions[])")
    set_id = str(data.get("set_id") or data["id"])
    title = str(data.get("title") or set_id)
    question = {k: v for k, v in data.items() if k not in {"set_id", "title"}}
    return {"set_id": set_id, "title": title, "questions": [question]}


def load_challenge_dir(path: Path) -> QuestionSet:
    """Load challenges/<name>/ with challenge.json + public/ (+ optional private/)."""
    ensure_builtin_types_loaded()
    root = Path(path)
    where = str(root)
    if not root.is_dir():
        raise QuestionLoadError(f"{where}: challenge folder not found")
    meta = root / "challenge.json"
    if not meta.is_file():
        raise QuestionLoadError(f"{where}: missing challenge.json")
    public = root / "public"
    if not public.is_dir():
        raise QuestionLoadError(f"{where}: missing public/ directory")

    try:
        raw = json.loads(meta.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise QuestionLoadError(f"{meta}: JSON parse error: {exc}") from exc
    if not isinstance(raw, dict):
        raise QuestionLoadError(f"{meta}: root must be an object")

    data = _compact_challenge_to_set(raw, str(meta))
    set_id = str(_require(data, "set_id", str(meta)))
    title = str(_require(data, "title", str(meta)))
    questions_raw = _require(data, "questions", str(meta))
    if not isinstance(questions_raw, list) or not questions_raw:
        raise QuestionLoadError(f"{meta}: 'questions' must be a non-empty array")

    # Desk challenges are one tile / one question by design.
    if len(questions_raw) != 1:
        deskish = any(
            isinstance(q, dict) and q.get("type") == "desk" for q in questions_raw
        )
        if deskish:
            raise QuestionLoadError(
                f"{meta}: desk challenge folders must contain exactly one question"
            )

    questions: list[Question] = []
    seen_ids: set[str] = set()
    for i, qdata in enumerate(questions_raw):
        qwhere = f"{meta}: questions[{i}]"
        qtype = str((qdata or {}).get("type", "")) if isinstance(qdata, dict) else ""
        public_arg = public if qtype == "desk" else None
        q = _build_question(
            qdata,
            where=qwhere,
            base_dir=root,
            public_dir=public_arg,
        )
        if q.id in seen_ids:
            raise QuestionLoadError(f"{qwhere}: duplicate question id '{q.id}'")
        seen_ids.add(q.id)
        questions.append(q)

    return QuestionSet(set_id=set_id, title=title, questions=questions, source_path=where)


def load_question_path(path: Path) -> QuestionSet:
    """Load a classic JSON set, a challenge folder, or a challenge.json path."""
    path = Path(path)
    if path.is_dir():
        return load_challenge_dir(path)
    if path.name == "challenge.json":
        return load_challenge_dir(path.parent)
    return load_question_file(path)


def load_all_question_files(paths: list[Path] | tuple[Path, ...]) -> list[QuestionSet]:
    sets: list[QuestionSet] = []
    seen_set_ids: set[str] = set()
    all_qids: set[str] = set()
    for path in paths:
        qset = load_question_path(Path(path))
        if qset.set_id in seen_set_ids:
            raise QuestionLoadError(f"{path}: duplicate set_id '{qset.set_id}'")
        seen_set_ids.add(qset.set_id)
        for q in qset.questions:
            if q.id in all_qids:
                raise QuestionLoadError(f"{path}: duplicate question id across sets: '{q.id}'")
            all_qids.add(q.id)
        sets.append(qset)
    return sets
