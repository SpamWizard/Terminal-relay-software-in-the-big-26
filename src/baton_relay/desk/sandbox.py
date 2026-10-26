"""Keep desk paths inside a challenge public/ folder."""

from __future__ import annotations

from pathlib import Path


class SandboxError(ValueError):
    """Path escaped the challenge public directory."""


def public_root(public_dir: Path) -> Path:
    root = Path(public_dir).resolve()
    if not root.is_dir():
        raise SandboxError(f"public directory missing: {root}")
    return root


def resolve_in_public(public_dir: Path, relative: str) -> Path:
    """Resolve a player path under public/. Rejects abs paths and .. escapes."""
    root = public_root(public_dir)
    text = (relative or "").strip().replace("\\", "/")
    if not text or text in (".", "./"):
        return root
    if text.startswith("/") or (len(text) >= 2 and text[1] == ":"):
        raise SandboxError("absolute paths are not allowed")
    parts = [p for p in text.split("/") if p and p != "."]
    if any(p == ".." for p in parts):
        raise SandboxError("path escapes the challenge folder")
    candidate = (root.joinpath(*parts)).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise SandboxError("path escapes the challenge folder") from exc
    return candidate


def list_public_files(public_dir: Path) -> list[str]:
    root = public_root(public_dir)
    out: list[str] = []
    for path in sorted(root.rglob("*")):
        if path.is_file():
            out.append(path.relative_to(root).as_posix())
    return out
