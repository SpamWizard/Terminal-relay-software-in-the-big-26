"""Tab completion for file names under the challenge public folder (Windows-side rail)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from baton_relay.desk.sandbox import list_public_files, public_root


@dataclass(frozen=True)
class CompleteResult:
    text: str
    matches: tuple[str, ...] = ()


def _common_prefix(items: list[str]) -> str:
    if not items:
        return ""
    prefix = items[0]
    for item in items[1:]:
        while not item.startswith(prefix):
            prefix = prefix[:-1]
            if not prefix:
                return ""
    return prefix


def complete_line(public_dir: Path | str, line: str) -> CompleteResult:
    """Complete the last path token from public/ file names."""
    text = line
    if text.endswith(" ") or text == "":
        prefix = ""
        head = text
    else:
        parts = text.rsplit(None, 1)
        if len(parts) == 1:
            head, prefix = "", parts[0]
        else:
            head, prefix = parts[0] + " ", parts[1]

    try:
        root = public_root(Path(public_dir))
        names = list_public_files(root)
        bin_dir = root / "bin"
        if bin_dir.is_dir():
            for script in sorted(bin_dir.glob("*.py")):
                stem = script.stem
                if stem not in names:
                    names.append(stem)
    except Exception:
        names = []

    folded = prefix.casefold()
    matches = [n for n in names if n.casefold().startswith(folded)]
    if not matches:
        return CompleteResult(text)
    if len(matches) == 1:
        return CompleteResult(head + matches[0])
    shared = _common_prefix(matches)
    if shared and len(shared) > len(prefix):
        return CompleteResult(head + shared, tuple(matches))
    return CompleteResult(text, tuple(matches))
