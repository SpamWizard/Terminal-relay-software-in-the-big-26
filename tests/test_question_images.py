"""Pictures are optional on every question type and tile in one area."""

from __future__ import annotations

import json
import struct
import zlib
from pathlib import Path

import pytest

from baton_relay.config import ScoringConfig, ThemeConfig
from baton_relay.questions.images import gallery_rows
from baton_relay.questions.loader import QuestionLoadError, load_question_file
from baton_relay.ui.theme import build_stylesheet

SCORING = ScoringConfig(partial_credit=True, wrong_answer_penalty=0, redo_multiplier=0.5)

THEME = ThemeConfig(
    name="deep_space",
    accent="#7dd3fc",
    background="#050816",
    foreground="#e8f1ff",
)


def _png(path: Path, rgb: tuple[int, int, int] = (40, 120, 200), size: int = 8) -> None:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    raw = b"".join(b"\x00" + bytes(rgb) * size for _ in range(size))
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


def _question(qtype: str, **extra) -> dict:
    base = {
        "multiple_choice": {"choices": ["no", "yes"], "answer": 1},
        "select_all": {"choices": ["a", "b", "c"], "answer": [0, 2]},
        "put_in_order": {"items": ["a", "b", "c"], "answer": [2, 0, 1]},
        "match_up": {
            "left": ["a", "b"],
            "right": ["A", "B"],
            "answer": {"0": 1, "1": 0},
        },
        "short_answer": {"accepted": ["dns"]},
        "numeric": {"answer": 62, "tolerance": 0},
        "fill_blank": {"accepted": ["trust"]},
        "flag": {"accepted": ["FLAG{ok}"]},
        "hands_on": {
            "image": "relay/practice:latest",
            "ports": [8080],
            "success": {"type": "flag", "accepted": ["FLAG{ok}"]},
        },
    }[qtype]
    return {"prompt": f"Text for {qtype}", "points": 10, **base, **extra}


def _write_set(path: Path, questions: list[dict]) -> None:
    path.write_text(
        json.dumps({"set_id": "pics", "title": "Pictures", "questions": questions}),
        encoding="utf-8",
    )


def test_gallery_rows_cover_one_through_eight():
    assert gallery_rows(1) == [1]
    assert gallery_rows(2) == [2]
    assert gallery_rows(3) == [3]
    assert gallery_rows(4) == [2, 2]
    assert gallery_rows(5) == [3, 2]
    assert gallery_rows(6) == [3, 3]
    assert gallery_rows(7) == [4, 3]
    assert gallery_rows(8) == [4, 4]
    for count in range(1, 9):
        rows = gallery_rows(count)
        assert sum(rows) == count
        assert rows == sorted(rows, reverse=True)


def test_repo_text_sets_have_no_images():
    root = Path(__file__).resolve().parents[1] / "questions"
    for path in sorted(root.glob("*.json")):
        if path.name.startswith("06_"):
            continue  # Fake Logos is intentionally pictured
        for question in load_question_file(path).questions:
            assert question.images is None


@pytest.mark.parametrize(
    "qtype,answer,expect_correct",
    [
        ("multiple_choice", 1, True),
        ("select_all", [0, 2], True),
        ("put_in_order", [2, 0, 1], True),
        ("match_up", {"0": 1, "1": 0}, True),
        ("short_answer", "dns", True),
        ("numeric", 62, True),
        ("fill_blank", "trust", True),
        ("flag", "FLAG{ok}", True),
        ("hands_on", "FLAG{ok}", True),
    ],
)
def test_every_type_accepts_pictures_and_still_scores(tmp_path: Path, qtype, answer, expect_correct):
    picture = tmp_path / "diagram.png"
    _png(picture, (20, 80, 140))
    path = tmp_path / "set.json"
    _write_set(
        path,
        [
            {
                "id": qtype,
                "type": qtype,
                **_question(
                    qtype,
                    images=["diagram.png", {"src": "diagram.png", "caption": "Same diagram"}],
                ),
            }
        ],
    )
    question = load_question_file(path).questions[0]
    assert question.prompt == f"Text for {qtype}"
    assert question.images is not None
    assert len(question.images) == 2
    assert question.images[0].caption == ""
    assert question.images[1].caption == "Same diagram"
    assert Path(question.images[0].path).is_file()
    if qtype == "hands_on":
        assert question.image == "relay/practice:latest"
    scored = question.score(answer, SCORING)
    assert scored.correct is expect_correct


def test_caption_whitespace_and_relative_parent(tmp_path: Path):
    shared = tmp_path / "shared"
    shared.mkdir()
    _png(shared / "star.png", (200, 80, 40))
    folder = tmp_path / "questions"
    folder.mkdir()
    path = folder / "set.json"
    _write_set(
        path,
        [
            {
                "id": "q",
                "type": "short_answer",
                **_question(
                    "short_answer",
                    images=[{"src": "../shared/star.png", "caption": "  star   topology "}],
                ),
            }
        ],
    )
    image = load_question_file(path).questions[0].images[0]
    assert image.caption == "star topology"
    assert Path(image.path) == (shared / "star.png").resolve()


def test_absolute_picture_path(tmp_path: Path):
    picture = tmp_path / "one.png"
    _png(picture)
    path = tmp_path / "set.json"
    _write_set(
        path,
        [
            {
                "id": "q",
                "type": "numeric",
                **_question("numeric", images=[str(picture)]),
            }
        ],
    )
    assert load_question_file(path).questions[0].images[0].path == str(picture.resolve())


@pytest.mark.parametrize(
    "images,match",
    [
        ([], "1 to 8"),
        (None, "1 to 8"),
        ("diagram.png", "array"),
        ([" "], "empty"),
        ([{"caption": "x"}], "src"),
        ([{"src": "diagram.png", "file": "nope.png"}], "unknown"),
        ([{"src": "diagram.png", "caption": 3}], "caption"),
        (["notes.txt"], "unsupported"),
        (["missing.png"], "not found"),
        (["not-really.png"], "not a valid PNG"),
        ([f"p{i}.png" for i in range(9)], "1 to 8"),
    ],
)
def test_loader_rejects_bad_pictures(tmp_path: Path, images, match):
    _png(tmp_path / "diagram.png")
    (tmp_path / "notes.txt").write_text("hello", encoding="utf-8")
    (tmp_path / "not-really.png").write_bytes(b"not a png")
    for i in range(9):
        _png(tmp_path / f"p{i}.png", ((i * 20) % 255, 40, 90))
    path = tmp_path / "set.json"
    _write_set(
        path,
        [{"id": "q", "type": "multiple_choice", **_question("multiple_choice", images=images)}],
    )
    with pytest.raises(QuestionLoadError, match=match):
        load_question_file(path)


def test_wrong_suffix_magic_rejected(tmp_path: Path):
    picture = tmp_path / "photo.jpg"
    _png(picture)
    path = tmp_path / "set.json"
    _write_set(
        path,
        [{"id": "q", "type": "flag", **_question("flag", images=["photo.jpg"])}],
    )
    with pytest.raises(QuestionLoadError, match="not a valid JPG"):
        load_question_file(path)


def _host(qtbot, question):
    from PySide6.QtWidgets import QApplication

    from baton_relay.ui.question_widgets import QuestionHost

    host = QuestionHost()
    host.setStyleSheet(build_stylesheet(THEME))
    qtbot.addWidget(host)
    host.resize(980, 700)
    host.show_question(question)
    host.show()
    qtbot.wait(30)
    QApplication.processEvents()
    return host


def test_text_only_question_has_no_gallery(qtbot, tmp_path: Path):
    from baton_relay.ui.image_gallery import ImageGallery

    path = tmp_path / "set.json"
    _write_set(path, [{"id": "q", "type": "multiple_choice", **_question("multiple_choice")}])
    question = load_question_file(path).questions[0]
    host = _host(qtbot, question)
    assert host.prompt.text() == "Text for multiple_choice"
    assert host._gallery is None
    assert host.findChildren(ImageGallery) == []


def test_picture_question_tiles_and_still_answers(qtbot, tmp_path: Path):
    from PySide6.QtCore import QPoint
    from PySide6.QtWidgets import QPushButton

    colors = [
        (230, 80, 70),
        (70, 160, 230),
        (240, 180, 40),
        (80, 190, 120),
        (180, 90, 220),
    ]
    names = []
    for i, rgb in enumerate(colors):
        dest = tmp_path / f"tile{i}.png"
        _png(dest, rgb, size=24)
        names.append(dest.name)
    path = tmp_path / "set.json"
    _write_set(
        path,
        [
            {
                "id": "q",
                "type": "multiple_choice",
                **_question(
                    "multiple_choice",
                    prompt="Which picture is the star topology?",
                    images=[
                        names[0],
                        {"src": names[1], "caption": "Ring"},
                        names[2],
                        {"src": names[3], "caption": "Star"},
                        names[4],
                    ],
                ),
            }
        ],
    )
    question = load_question_file(path).questions[0]
    host = _host(qtbot, question)
    assert host.prompt.text() == "Which picture is the star topology?"
    gallery = host._gallery
    assert gallery is not None
    assert len(gallery.tiles) == 5

    def origin(widget):
        return widget.mapTo(host, QPoint(0, 0))

    prompt_y = origin(host.prompt).y()
    gallery_y = origin(gallery).y()
    assert gallery_y > prompt_y

    points = [origin(tile) for tile in gallery.tiles]
    top = points[:3]
    bottom = points[3:]
    assert max(p.y() for p in top) + 20 < min(p.y() for p in bottom)
    top_mid = (top[0].x() + top[2].x() + gallery.tiles[2].width()) / 2
    bottom_left = bottom[0].x()
    bottom_right = bottom[1].x() + gallery.tiles[4].width()
    bottom_mid = (bottom_left + bottom_right) / 2
    assert abs(top_mid - bottom_mid) < 30
    assert bottom_left > top[0].x() + 10
    assert gallery.tiles[3].caption.text() == "Star"

    buttons = host._body.findChildren(QPushButton)
    buttons[1].click()
    got: list = []
    host.set_submit_handler(got.append)
    host.set_locked(False)
    host.submit_btn.click()
    assert got == [1]

    from baton_relay.questions.types import MultipleChoice

    text_only = MultipleChoice(
        id="plain",
        type="multiple_choice",
        prompt="Just text",
        points=5,
        choices=["a", "b"],
        answer=0,
    )
    host.show_question(text_only)
    qtbot.wait(20)
    assert host._gallery is None
    assert host.prompt.text() == "Just text"


def test_eight_pictures_make_two_rows_of_four(qtbot, tmp_path: Path):
    from PySide6.QtCore import QPoint

    names = []
    for i in range(8):
        dest = tmp_path / f"p{i}.png"
        _png(dest, ((i * 30) % 255, 90, 160), size=16)
        names.append(dest.name)
    path = tmp_path / "set.json"
    _write_set(
        path,
        [
            {
                "id": "q",
                "type": "select_all",
                **_question(
                    "select_all",
                    prompt="Select the diagrams that show a firewall.",
                    images=names,
                ),
            }
        ],
    )
    host = _host(qtbot, load_question_file(path).questions[0])
    tiles = host._gallery.tiles
    assert len(tiles) == 8
    ys = [tile.mapTo(host, QPoint(0, 0)).y() for tile in tiles]
    assert max(ys[:4]) + 20 < min(ys[4:])
    xs = [tile.mapTo(host, QPoint(0, 0)).x() for tile in tiles]
    for col in range(4):
        assert abs(xs[col] - xs[col + 4]) < 8
