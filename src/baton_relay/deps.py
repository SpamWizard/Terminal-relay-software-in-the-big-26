"""Install every project dependency in one step when any of them is missing."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import tomllib
from pathlib import Path


# Distribution name (as in pyproject.toml) -> import name.
IMPORT_NAMES = {
    "PySide6": "PySide6",
    "pyserial": "serial",
    "pygame": "pygame",
    "pywinpty": "winpty",
    "pyte": "pyte",
    "pytest": "pytest",
    "pytest-qt": "pytestqt",
}

INSTALL_COMMAND = 'pip install -e ".[dev]"'


class DependencyError(RuntimeError):
    """Project Python packages could not be installed."""


def dist_name(spec: str) -> str:
    """Package name from a requirement like ``PySide6>=6.6``."""
    name = spec.strip()
    for sep in ("[", ">", "<", "=", "!", "~", " ", ";"):
        name = name.split(sep, 1)[0]
    return name


def find_repo_root() -> Path | None:
    starts = [Path(__file__).resolve().parent, Path.cwd()]
    for start in starts:
        for parent in (start, *start.parents):
            if (parent / "pyproject.toml").is_file():
                return parent
    return None


def dependency_specs(repo_root: Path) -> list[str]:
    """Runtime dependencies plus the dev extra. One install gets both."""
    data = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))
    project = data["project"]
    specs = [str(item) for item in project.get("dependencies") or []]
    extras = project.get("optional-dependencies") or {}
    specs.extend(str(item) for item in extras.get("dev") or [])
    return specs


def missing_distributions(specs: list[str]) -> list[str]:
    missing: list[str] = []
    for spec in specs:
        name = dist_name(spec)
        module = IMPORT_NAMES.get(name)
        if module is not None and importlib.util.find_spec(module) is None:
            missing.append(name)
    return missing


def ensure_dependencies() -> None:
    """If any dependency is missing, install the full set from pyproject.toml."""
    root = find_repo_root()
    if root is None:
        return
    specs = dependency_specs(root)
    missing = missing_distributions(specs)
    if not missing:
        return
    print(
        "Missing Python packages: "
        + ", ".join(missing)
        + ".\nInstalling all project dependencies...",
        file=sys.stderr,
    )
    proc = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-e", ".[dev]"],
        cwd=root,
        check=False,
    )
    if proc.returncode != 0:
        raise DependencyError(
            f"Could not install project dependencies (pip exit {proc.returncode}).\n"
            f"From the project folder, run: {INSTALL_COMMAND}"
        )
    importlib.invalidate_caches()
    still = missing_distributions(specs)
    if still:
        raise DependencyError(
            "Still missing after install: "
            + ", ".join(still)
            + f"\nFrom the project folder, run: {INSTALL_COMMAND}"
        )
