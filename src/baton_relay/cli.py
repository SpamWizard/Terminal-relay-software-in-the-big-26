"""CLI entrypoints: `relay run`, `relay quick`, `relay probe`, `relay reset`, `relay board`."""

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

    return run_app(
        config_path=Path(args.config),
        fake_device=args.fake_device or args.quick,
        quick=args.quick,
    )


def cmd_quick(args: argparse.Namespace) -> int:
    from baton_relay.app import run_app

    return run_app(
        config_path=Path(args.config),
        fake_device=True,
        quick=True,
    )


def cmd_probe(args: argparse.Namespace) -> int:
    from baton_relay.probe import run_probe

    return run_probe(Path(args.config), port=args.port)


def cmd_reset(args: argparse.Namespace) -> int:
    from baton_relay.reset import reset_machine

    return reset_machine(config_path=Path(args.config))


def _load_or_exit(args: argparse.Namespace):
    from baton_relay.config import ConfigError, load_config

    try:
        return load_config(Path(args.config))
    except ConfigError as exc:
        print(f"ERROR: bad config: {exc}", file=sys.stderr)
        return None


def cmd_board(args: argparse.Namespace) -> int:
    print(
        "Usage: relay board show | push | watch | serve\n"
        "  show   print the JSON the scoreboard would receive\n"
        "  push   PUT the board once\n"
        "  watch  keep pushing when scores change\n"
        "  serve  local projector page (does not push)",
        file=sys.stderr,
    )
    return 2


def cmd_board_show(args: argparse.Namespace) -> int:
    import json

    from baton_relay.scoreboard.sync import build_synced_board

    config = _load_or_exit(args)
    if config is None:
        return 1
    text = json.dumps(build_synced_board(config), indent=2, ensure_ascii=False) + "\n"
    out = getattr(args, "out", None)
    if out:
        Path(out).write_text(text, encoding="utf-8")
    sys.stdout.write(text)
    return 0


def cmd_board_push(args: argparse.Namespace) -> int:
    from baton_relay.scoreboard.publish import push_once

    config = _load_or_exit(args)
    if config is None:
        return 1
    return push_once(config)


def cmd_board_watch(args: argparse.Namespace) -> int:
    from baton_relay.scoreboard.publish import watch

    config = _load_or_exit(args)
    if config is None:
        return 1
    try:
        return watch(config)
    except KeyboardInterrupt:
        print("\nScoreboard watch stopped.", flush=True)
        return 0


def cmd_board_serve(args: argparse.Namespace) -> int:
    from baton_relay.scoreboard.display import serve_board

    config = _load_or_exit(args)
    if config is None:
        return 1
    return serve_board(config, host=args.host, port=args.port)


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
        action="store_true",
        help="Simulate batons with keyboard (1-6 insert, P pull out, U unknown). "
        "Default is RP2040 USB serial from [serial] in config.",
    )
    run_p.add_argument(
        "--quick",
        action="store_true",
        help="Skip the name screen and open category selection with a player already in. "
        "Same as `relay quick`. Implies --fake-device.",
    )
    run_p.set_defaults(func=cmd_run)

    quick_p = sub.add_parser(
        "quick",
        help="Skip names and open category selection (player already seated)",
    )
    quick_p.set_defaults(func=cmd_quick)

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

    board_p = sub.add_parser(
        "board",
        help="Publish or display the SaintCon scoreboard",
    )
    board_sub = board_p.add_subparsers(dest="board_command")
    board_p.set_defaults(func=cmd_board)

    show_p = board_sub.add_parser("show", help="Print the board JSON")
    show_p.add_argument("--out", default=None, help="Also write the JSON to this file")
    show_p.set_defaults(func=cmd_board_show)

    push_p = board_sub.add_parser("push", help="PUT the board once")
    push_p.set_defaults(func=cmd_board_push)

    watch_p = board_sub.add_parser(
        "watch",
        help="Push when scores change, without the game window",
    )
    watch_p.set_defaults(func=cmd_board_watch)

    serve_p = board_sub.add_parser("serve", help="Local projector page (does not push)")
    serve_p.add_argument("--host", default="127.0.0.1", help="Bind address")
    serve_p.add_argument("--port", type=int, default=8765, help="Listen port")
    serve_p.set_defaults(func=cmd_board_serve)

    return parser


def main(argv: list[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    if not raw or raw[0] not in ("run", "probe", "reset", "quick", "board"):
        raw = ["run", *raw]
    args = parser.parse_args(raw)
    return args.func(args)
