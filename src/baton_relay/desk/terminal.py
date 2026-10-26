"""Line-oriented challenge terminal (no real shell)."""

from __future__ import annotations

import base64
import hashlib
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from baton_relay.desk.sandbox import SandboxError, list_public_files, public_root, resolve_in_public

_HELP = """Available commands:
  help                 this list
  pwd                  challenge folder
  ls / dir [path]      list files
  cat / type <file>    print a text file
  head <file> [n]      first n lines (default 20)
  grep / findstr <pat> <file>
  b64 <file|text>      base64-decode a file or string
  sha256 <file|text>   sha256 hex digest
  md5 <file|text>      md5 hex digest
  python <script.py> [args...]
  python -c "code"     one-liner
Paths stay inside this challenge folder."""


@dataclass(frozen=True)
class TerminalResult:
    output: str
    exit_code: int = 0


def _split(line: str) -> list[str]:
    try:
        return shlex.split(line, posix=True)
    except ValueError as exc:
        raise SandboxError(str(exc)) from exc


def _bytes_arg(root: Path, token: str) -> bytes:
    """If token names a file under public/, hash/decode that file; else use the string."""
    try:
        path = resolve_in_public(root, token)
    except SandboxError:
        return token.encode("utf-8")
    if path.is_file():
        return path.read_bytes()
    return token.encode("utf-8")


def _read_text(path: Path, *, limit: int | None = None) -> str:
    raw = path.read_bytes()
    # Binary-ish files: show a short hex preview plus printable tail.
    if b"\x00" in raw[:4096]:
        preview = raw[:256]
        hexed = " ".join(f"{b:02x}" for b in preview)
        return f"[binary file, {len(raw)} bytes]\n{hexed}"
    text = raw.decode("utf-8", errors="replace")
    if limit is None:
        return text
    lines = text.splitlines()
    return "\n".join(lines[:limit])


def run_desk_command(public_dir: Path | str, line: str, *, timeout: float = 8.0) -> TerminalResult:
    """Run one player command confined to public_dir."""
    root = public_root(Path(public_dir))
    text = (line or "").strip()
    if not text:
        return TerminalResult("", 0)
    try:
        argv = _split(text)
    except SandboxError as exc:
        return TerminalResult(f"error: {exc}", 1)
    if not argv:
        return TerminalResult("", 0)

    cmd = argv[0].casefold()
    args = argv[1:]

    try:
        if cmd in {"help", "?"}:
            return TerminalResult(_HELP, 0)
        if cmd == "pwd":
            return TerminalResult(str(root), 0)
        if cmd in {"ls", "dir"}:
            target = resolve_in_public(root, args[0] if args else ".")
            if target.is_file():
                return TerminalResult(target.name, 0)
            if target == root:
                names = list_public_files(root)
                return TerminalResult("\n".join(names) if names else "(empty)", 0)
            entries = sorted(p.name + ("/" if p.is_dir() else "") for p in target.iterdir())
            return TerminalResult("\n".join(entries) if entries else "(empty)", 0)
        if cmd in {"cat", "type"}:
            if not args:
                return TerminalResult("usage: cat <file>", 1)
            path = resolve_in_public(root, args[0])
            if not path.is_file():
                return TerminalResult(f"not a file: {args[0]}", 1)
            return TerminalResult(_read_text(path), 0)
        if cmd == "head":
            if not args:
                return TerminalResult("usage: head <file> [n]", 1)
            n = 20
            if len(args) >= 2:
                try:
                    n = max(1, int(args[1]))
                except ValueError:
                    return TerminalResult("usage: head <file> [n]", 1)
            path = resolve_in_public(root, args[0])
            if not path.is_file():
                return TerminalResult(f"not a file: {args[0]}", 1)
            return TerminalResult(_read_text(path, limit=n), 0)
        if cmd in {"grep", "findstr"}:
            if len(args) < 2:
                return TerminalResult(f"usage: {cmd} <pattern> <file>", 1)
            pattern, rel = args[0], args[1]
            path = resolve_in_public(root, rel)
            if not path.is_file():
                return TerminalResult(f"not a file: {rel}", 1)
            hits = [
                line
                for line in _read_text(path).splitlines()
                if pattern.casefold() in line.casefold()
            ]
            return TerminalResult("\n".join(hits) if hits else "(no matches)", 0 if hits else 1)
        if cmd in {"b64", "base64"}:
            if not args:
                return TerminalResult("usage: b64 <file|text>", 1)
            blob = _bytes_arg(root, args[0])
            try:
                decoded = base64.b64decode(blob, validate=False)
            except Exception as exc:
                return TerminalResult(f"error: {exc}", 1)
            return TerminalResult(decoded.decode("utf-8", errors="replace"), 0)
        if cmd in {"sha256", "sha256sum"}:
            if not args:
                return TerminalResult("usage: sha256 <file|text>", 1)
            digest = hashlib.sha256(_bytes_arg(root, args[0])).hexdigest()
            return TerminalResult(digest, 0)
        if cmd in {"md5", "md5sum"}:
            if not args:
                return TerminalResult("usage: md5 <file|text>", 1)
            digest = hashlib.md5(_bytes_arg(root, args[0]), usedforsecurity=False).hexdigest()
            return TerminalResult(digest, 0)
        if cmd in {"python", "python3", "py"}:
            if not args:
                return TerminalResult("usage: python <script.py> [args...]  OR  python -c \"code\"", 1)
            if args[0] == "-c":
                if len(args) < 2:
                    return TerminalResult("usage: python -c \"code\"", 1)
                proc = subprocess.run(
                    [sys.executable, "-c", args[1]],
                    cwd=str(root),
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    check=False,
                )
            else:
                script = resolve_in_public(root, args[0])
                if not script.is_file():
                    return TerminalResult(f"not a file: {args[0]}", 1)
                if script.suffix.casefold() not in {".py", ".pyw"}:
                    return TerminalResult("only .py scripts are allowed", 1)
                proc = subprocess.run(
                    [sys.executable, str(script), *args[1:]],
                    cwd=str(root),
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    check=False,
                )
            out = (proc.stdout or "") + (proc.stderr or "")
            return TerminalResult(out.rstrip("\n"), proc.returncode)
        return TerminalResult(
            f"unknown command: {argv[0]}\nType 'help' for the list.",
            1,
        )
    except SandboxError as exc:
        return TerminalResult(f"error: {exc}", 1)
    except subprocess.TimeoutExpired:
        return TerminalResult("error: command timed out", 1)
    except OSError as exc:
        return TerminalResult(f"error: {exc}", 1)
