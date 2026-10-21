"""Optional pictures shared by every question type.

A question keeps its normal answer type. ``images`` only adds 1-8 pictures
that the game shows with the prompt text.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

MIN_IMAGES = 1
MAX_IMAGES = 8
IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp")

# Rows for 1..8 pictures. Shorter last rows are centered by the gallery.
_GALLERY_ROWS: dict[int, tuple[int, ...]] = {
    1: (1,),
    2: (2,),
    3: (3,),
    4: (2, 2),
    5: (3, 2),
    6: (3, 3),
    7: (4, 3),
    8: (4, 4),
}


class QuestionImageError(ValueError):
    """A question's ``images`` field is missing, empty, or not a real picture."""


@dataclass(frozen=True)
class QuestionImage:
    path: str
    caption: str = ""


def gallery_rows(count: int) -> list[int]:
    """How many pictures sit on each row of the tiled area."""
    try:
        return list(_GALLERY_ROWS[count])
    except KeyError as exc:
        raise QuestionImageError(
            f"A question can show {MIN_IMAGES} to {MAX_IMAGES} pictures (got {count})"
        ) from exc


def pictures_for(images: list[QuestionImage] | list[str] | None) -> list[QuestionImage]:
    """Normalize loader results and plain path lists for the gallery."""
    pictures: list[QuestionImage] = []
    for item in images or []:
        if isinstance(item, QuestionImage):
            if item.path:
                pictures.append(item)
        elif isinstance(item, str) and item.strip():
            pictures.append(QuestionImage(path=item.strip()))
    return pictures


def resolve_question_images(value: Any, *, where: str, base_dir: Path) -> list[QuestionImage]:
    """Resolve ``images`` relative to the question file and check they load."""
    if not isinstance(value, list):
        raise QuestionImageError(f"{where}: 'images' must be an array of 1 to 8 pictures")
    count = len(value)
    if count < MIN_IMAGES or count > MAX_IMAGES:
        raise QuestionImageError(
            f"{where}: 'images' must contain 1 to 8 pictures (got {count})"
        )
    resolved: list[QuestionImage] = []
    for index, item in enumerate(value):
        src, caption = _entry(item, where=f"{where}: images[{index}]")
        path = _resolve_path(src, where=f"{where}: images[{index}]", base_dir=base_dir)
        resolved.append(QuestionImage(path=str(path), caption=caption))
    return resolved


def _entry(item: Any, *, where: str) -> tuple[str, str]:
    if isinstance(item, str):
        text = item.strip()
        if not text:
            raise QuestionImageError(f"{where}: picture path is empty")
        return text, ""
    if isinstance(item, dict):
        unknown = set(item) - {"src", "caption"}
        if unknown:
            name = min(unknown)
            raise QuestionImageError(f"{where}: unknown image field '{name}'")
        src = item.get("src")
        if not isinstance(src, str) or not src.strip():
            raise QuestionImageError(f"{where}: expected a path or {{\"src\": \"file.png\"}}")
        caption = item.get("caption", "")
        if caption is None:
            caption = ""
        if not isinstance(caption, str):
            raise QuestionImageError(f"{where}: 'caption' must be text")
        return src.strip(), " ".join(caption.split())
    raise QuestionImageError(f"{where}: expected a path or {{\"src\": \"file.png\"}}")


def _resolve_path(src: str, *, where: str, base_dir: Path) -> Path:
    raw = Path(src)
    path = raw.resolve() if raw.is_absolute() else (base_dir / raw).resolve()
    suffix = path.suffix.lower()
    if suffix not in IMAGE_SUFFIXES:
        allowed = ", ".join(IMAGE_SUFFIXES)
        shown = path.suffix or "(none)"
        raise QuestionImageError(
            f"{where}: unsupported picture type '{shown}' (use {allowed})"
        )
    if not path.is_file():
        raise QuestionImageError(f"{where}: picture not found: {src}")
    if not _file_matches_suffix(path, suffix):
        kind = suffix.lstrip(".").upper()
        raise QuestionImageError(f"{where}: file is not a valid {kind} image")
    return path


def _file_matches_suffix(path: Path, suffix: str) -> bool:
    try:
        head = path.read_bytes()[:32]
    except OSError:
        return False
    if suffix == ".png":
        return head.startswith(b"\x89PNG\r\n\x1a\n")
    if suffix in {".jpg", ".jpeg"}:
        return head.startswith(b"\xff\xd8\xff")
    if suffix == ".gif":
        return head.startswith((b"GIF87a", b"GIF89a"))
    if suffix == ".bmp":
        return head.startswith(b"BM")
    if suffix == ".webp":
        return len(head) >= 12 and head.startswith(b"RIFF") and head[8:12] == b"WEBP"
    return False
