"""Tab completion for the desk terminal line."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from baton_relay.desk.sandbox import list_public_files, public_root

COMMANDS = (
    "help",
    "pwd",
    "ls",
    "dir",
    "cat",
    "type",
    "head",
    "grep",
    "findstr",
    "b64",
    "base64",
    "sha256",
    "sha256sum",
    "md5",
    "md5sum",
    "python",
    "python3",
    "py",
)


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
    """Complete the last token of a command line (commands or public files)."""
    text = line
    # Token is everything after the last whitespace (keep leading command intact).
    if text.endswith(" ") or text == "":
        prefix = ""
        head = text
    else:
        parts = text.rsplit(None, 1)
        if len(parts) == 1:
            head, prefix = "", parts[0]
        else:
            head, prefix = parts[0] + " ", parts[1]

    # First word → commands; later words → files (and .py scripts).
    first_word = not head.strip()
    if first_word:
        folded = prefix.casefold()
        candidates = [c for c in COMMANDS if c.casefold().startswith(folded)]
    else:
        try:
            root = public_root(Path(public_dir))
            names = list_public_files(root)
        except Exception:
            names = []
        folded = prefix.casefold()
        candidates = [n for n in names if n.casefold().startswith(folded)]

    if not candidates:
        return CompleteResult(text=text, matches=())

    if len(candidates) == 1:
        return CompleteResult(text=head + candidates[0] + (" " if first_word else ""), matches=tuple(candidates))

    shared = _common_prefix(candidates)
    if shared and len(shared) > len(prefix):
        return CompleteResult(text=head + shared, matches=tuple(candidates))
    return CompleteResult(text=text, matches=tuple(candidates))
