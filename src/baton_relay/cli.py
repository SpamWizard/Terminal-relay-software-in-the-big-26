"""CLI entrypoints: `relay run`, `relay quick`, `relay warm`, `relay probe`, `relay reset`."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _default_config_path() -> Path:
    cwd = Path.cwd()
    candidate = cwd / "config" / "config.toml"
    if candidate.is_file():
        return candidate
    return cwd / "config.toml"


def cmd_run(args: argparse.Namespace) -> int:
    from baton_relay.app import run_app

    # Quick always uses keyboard seating; otherwise honor --fake-device / --no-fake-device.
    fake = True if args.quick else bool(args.fake_device)
    return run_app(
        config_path=Path(args.config),
        fake_device=fake,
        quick=args.quick,
    )


def cmd_quick(args: argparse.Namespace) -> int:
    from baton_relay.app import run_app

    return run_app(
        config_path=Path(args.config),
        fake_device=True,
        quick=True,
    )


def cmd_warm(args: argparse.Namespace) -> int:
    """Pre-copy the golden Kali disk so the next team start is instant."""
    from baton_relay.config import ConfigError, load_config
    from baton_relay.desk.shell import ShellError, ensure_standby_disk, standby_vhdx_path

    try:
        config = load_config(Path(args.config))
    except ConfigError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    repo_root = config.paths.results_dir.parent
    try:
        path = ensure_standby_disk(repo_root)
    except ShellError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"Standby desk disk ready: {path}")
    print(f"(same as {standby_vhdx_path(repo_root)})")
    return 0


def cmd_probe(args: argparse.Namespace) -> int:
    from baton_relay.probe import run_probe

    return run_probe(Path(args.config), port=args.port)


def cmd_reset(args: argparse.Namespace) -> int:
    from baton_relay.reset import reset_machine

    return reset_machine(config_path=Path(args.config))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="relay",
        description="Terminal Relay — timed team relay with baton identity",
    )
    parser.add_argument(
        "--config",
        default=str(_default_config_path()),
        help="Path to config.toml (default: ./config/config.toml)",
    )
    sub = parser.add_subparsers(dest="command")

    run_p = sub.add_parser("run", help="Start the relay UI")
    run_p.add_argument(
        "--fake-device",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Keyboard baton: Ctrl+1–6 insert, Ctrl+P pull, Ctrl+U unknown (default). "
        "Use --no-fake-device for RP2040 USB serial from [serial] in config.",
    )
    run_p.add_argument(
        "--quick",
        action="store_true",
        help="Skip the name screen and open category selection with a player already in. "
        "Skip (F6) jumps to another category. Same as `relay quick`. Uses keyboard baton.",
    )
    run_p.set_defaults(func=cmd_run)

    quick_p = sub.add_parser(
        "quick",
        help="Skip names and open the board. Skip (F6) jumps to another category",
    )
    quick_p.set_defaults(func=cmd_quick)

    warm_p = sub.add_parser(
        "warm",
        help="Pre-copy the golden Kali disk so the next team start does not wait",
    )
    warm_p.set_defaults(func=cmd_warm)

    probe_p = sub.add_parser(
        "probe",
        help="Print which baton pins are plugged in (no game window)",
    )
    probe_p.add_argument(
        "--port",
        default=None,
        help="Serial port override (default: [serial].port, usually auto)",
    )
    probe_p.set_defaults(func=cmd_probe)

    reset_p = sub.add_parser(
        "reset",
        help="Archive checkpoints so the next team starts clean",
    )
    reset_p.set_defaults(func=cmd_reset)

    return parser


def main(argv: list[str] | None = None) -> int:
    from baton_relay.deps import ensure_dependencies

    try:
        ensure_dependencies()
    except SystemExit as exc:
        code = exc.code
        return 1 if code in (None, "") else int(code)

    raw = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    if not raw or raw[0] not in ("run", "probe", "reset", "quick", "warm"):
        raw = ["run", *raw]
    args = parser.parse_args(raw)
    return args.func(args)
