"""The project install covers every dependency, not one package at a time."""

from pathlib import Path
from unittest.mock import patch

from baton_relay.cli import main
from baton_relay.deps import (
    IMPORT_NAMES,
    DependencyError,
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


def test_cli_prints_install_failure_instead_of_crashing(capsys):
    with patch(
        "baton_relay.deps.ensure_dependencies",
        side_effect=DependencyError("Could not install project dependencies (pip exit 1)."),
    ):
        assert main(["quick"]) == 1
    err = capsys.readouterr().err
    assert "Could not install project dependencies" in err
