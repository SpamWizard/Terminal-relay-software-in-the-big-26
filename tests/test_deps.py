"""The project install covers every dependency, not one package at a time."""

from pathlib import Path

from baton_relay.deps import (
    IMPORT_NAMES,
    dependency_specs,
    dist_name,
    missing_distributions,
)


ROOT = Path(__file__).resolve().parents[1]


def test_install_list_covers_runtime_and_dev():
    names = [dist_name(spec) for spec in dependency_specs(ROOT)]
    assert names == [
        "PySide6",
        "pyserial",
        "pygame",
        "pywinpty",
        "pyte",
        "pytest",
        "pytest-qt",
    ]
    assert set(names) <= set(IMPORT_NAMES)


def test_installed_environment_reports_nothing_missing():
    assert missing_distributions(dependency_specs(ROOT)) == []
