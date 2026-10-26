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
  grep -r <pat> [path] search under a folder (default: .)
  b64 <file|text>      base64-decode a file or string
  sha256 <file|text>   sha256 hex digest
  md5 <file|text>      md5 hex digest
  python <script.py> [args...]
  python -c "code"     one-liner
  <name> ...           run bin/<name>.py if this challenge ships it
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


def _run_py(root: Path, script: Path, argv_tail: list[str], *, timeout: float) -> TerminalResult:
    proc = subprocess.run(
        [sys.executable, str(script), *argv_tail],
        cwd=str(root),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    return TerminalResult(out.rstrip("\n"), proc.returncode)


def _bin_tool(root: Path, name: str) -> Path | None:
    """Challenge-local fake tool: public/bin/<name>.py"""
    if not name or "/" in name or "\\" in name or name in {".", ".."}:
        return None
    candidate = root / "bin" / f"{name}.py"
    if candidate.is_file():
        return candidate
    return None


def _grep(root: Path, cmd: str, args: list[str]) -> TerminalResult:
    if not args:
        return TerminalResult(f"usage: {cmd} <pattern> <file>  OR  {cmd} -r <pattern> [path]", 1)

    recursive = False
    rest = list(args)
    if rest[0] in {"-r", "-R", "--recursive"}:
        recursive = True
        rest = rest[1:]
    if not rest:
        return TerminalResult(f"usage: {cmd} -r <pattern> [path]", 1)

    pattern = rest[0]
    needle = pattern.casefold()

    if recursive:
        rel = rest[1] if len(rest) > 1 else "."
        base = resolve_in_public(root, rel)
        if base.is_file():
            files = [base]
        elif base.is_dir():
            files = sorted(p for p in base.rglob("*") if p.is_file())
        else:
            return TerminalResult(f"not found: {rel}", 1)
        hits: list[str] = []
        for path in files:
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            rel_path = path.relative_to(root).as_posix()
            for i, line in enumerate(text.splitlines(), start=1):
                if needle in line.casefold():
                    hits.append(f"{rel_path}:{i}:{line}")
        return TerminalResult("\n".join(hits) if hits else "(no matches)", 0 if hits else 1)

    if len(rest) < 2:
        return TerminalResult(f"usage: {cmd} <pattern> <file>", 1)
    rel = rest[1]
    path = resolve_in_public(root, rel)
    if not path.is_file():
        return TerminalResult(f"not a file: {rel}", 1)
    hits = [line for line in _read_text(path).splitlines() if needle in line.casefold()]
    return TerminalResult("\n".join(hits) if hits else "(no matches)", 0 if hits else 1)


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
            return _grep(root, cmd, args)
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
                out = (proc.stdout or "") + (proc.stderr or "")
                return TerminalResult(out.rstrip("\n"), proc.returncode)
            script = resolve_in_public(root, args[0])
            if not script.is_file():
                return TerminalResult(f"not a file: {args[0]}", 1)
            if script.suffix.casefold() not in {".py", ".pyw"}:
                return TerminalResult("only .py scripts are allowed", 1)
            return _run_py(root, script, args[1:], timeout=timeout)

        tool = _bin_tool(root, argv[0])
        if tool is not None:
            return _run_py(root, tool, args, timeout=timeout)

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
