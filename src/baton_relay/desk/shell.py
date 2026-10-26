"""Team Linux shell: linked-clone WSL disk + one long-lived bash piped through the GUI."""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from baton_relay.results.log import team_slug


class ShellError(RuntimeError):
    """WSL / linked-clone / bash pipe failure."""


def distro_name(team_name: str) -> str:
    return f"relay-{team_slug(team_name)}"


def gold_vhdx_path(repo_root: Path) -> Path:
    return repo_root / "images" / "relay-gold.vhdx"


def team_vhdx_path(repo_root: Path, team_name: str) -> Path:
    return repo_root / "data" / "wsl" / team_slug(team_name) / "ext4.vhdx"


def wsl_available() -> bool:
    return shutil.which("wsl") is not None or shutil.which("wsl.exe") is not None


def new_vhd_available() -> bool:
    try:
        proc = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "if (Get-Command New-VHD -ErrorAction SilentlyContinue) { 'yes' } else { 'no' }",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return (proc.stdout or "").strip().casefold() == "yes"


def require_desk_runtime(repo_root: Path) -> None:
    """Raise ShellError if desk challenges cannot run on this machine."""
    if not wsl_available():
        raise ShellError("wsl.exe not found. Install WSL2 and reboot if needed.")
    gold = gold_vhdx_path(repo_root)
    if not gold.is_file():
        raise ShellError(
            f"Golden image missing: {gold}\n"
            "Build it with: powershell -File scripts/build_relay_gold.ps1"
        )
    if not new_vhd_available():
        raise ShellError(
            "New-VHD not found. Enable Hyper-V PowerShell tools "
            "(Microsoft-Hyper-V-Management-PowerShell), then reboot if asked."
        )


def _wsl_exe() -> str:
    return shutil.which("wsl") or shutil.which("wsl.exe") or "wsl.exe"


def _decode_wsl_bytes(raw: bytes) -> str:
    """WSL on Windows often prints UTF-16LE; fall back to UTF-8."""
    if not raw:
        return ""
    if raw[:2] == b"\xff\xfe" or (len(raw) > 2 and raw[1] == 0):
        return raw.decode("utf-16-le", errors="replace").replace("\x00", "")
    return raw.decode("utf-8", errors="replace")


def _run(args: list[str], *, timeout: float = 120.0) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        args,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    return subprocess.CompletedProcess(
        args=proc.args,
        returncode=proc.returncode,
        stdout=_decode_wsl_bytes(proc.stdout or b""),
        stderr=_decode_wsl_bytes(proc.stderr or b""),
    )


def _clear_readonly(path: Path) -> None:
    """WSL refuses to attach ReadOnly VHDX files (MountDisk/E_ACCESSDENIED)."""
    if not path.is_file():
        return
    try:
        os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
    except OSError:
        pass
    if os.name == "nt":
        subprocess.run(
            ["attrib", "-R", str(path)],
            capture_output=True,
            timeout=30,
            check=False,
        )


def list_relay_distros() -> list[str]:
    proc = _run([_wsl_exe(), "-l", "-q"], timeout=60.0)
    names: list[str] = []
    for line in (proc.stdout or "").splitlines():
        name = line.strip()
        if name.startswith("relay-"):
            names.append(name)
    return names


def unregister_relay_distros() -> list[str]:
    """Unregister every relay-* team distro. Does not touch the golden vhdx."""
    removed: list[str] = []
    for name in list_relay_distros():
        _run([_wsl_exe(), "--unregister", name], timeout=180.0)
        removed.append(name)
    return removed


def _distro_registered(name: str) -> bool:
    return name in list_relay_distros()


def _shutdown_wsl() -> None:
    _run([_wsl_exe(), "--shutdown"], timeout=60.0)
    time.sleep(1.0)


def _import_in_place(name: str, child: Path) -> None:
    _clear_readonly(child)
    _shutdown_wsl()
    proc = _run([_wsl_exe(), "--import-in-place", name, str(child.resolve())], timeout=180.0)
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise ShellError(f"import-in-place failed for {name}:\n{detail}")


def _create_differencing_child(gold: Path, child: Path) -> None:
    child.parent.mkdir(parents=True, exist_ok=True)
    _clear_readonly(gold)
    _shutdown_wsl()
    ps = (
        f"$ErrorActionPreference = 'Stop'; "
        f"New-VHD -ParentPath '{gold.resolve()}' -Path '{child.resolve()}' "
        f"-Differencing -BlockSizeBytes 1MB | Out-Null"
    )
    proc = _run(["powershell", "-NoProfile", "-Command", ps], timeout=120.0)
    if proc.returncode != 0:
        raise ShellError(
            f"New-VHD differencing clone failed:\n{(proc.stderr or proc.stdout or '').strip()}"
        )
    _clear_readonly(child)


def _create_full_copy_child(gold: Path, child: Path) -> None:
    """Full copy of the golden VHDX (reliable with WSL import-in-place)."""
    child.parent.mkdir(parents=True, exist_ok=True)
    _clear_readonly(gold)
    if child.is_file():
        _clear_readonly(child)
        child.unlink()
    shutil.copy2(gold, child)
    _clear_readonly(child)


def _remove_child(child: Path) -> None:
    if child.is_file():
        _clear_readonly(child)
        child.unlink(missing_ok=True)


def create_linked_clone(repo_root: Path, team_name: str) -> str:
    """Create a team disk from the golden parent and import it in place.

    Tries a Hyper-V differencing (linked) clone first. WSL often refuses those
    because HCS cannot open the parent VHDX (0xc03a0016). In that case we fall
    back to a full copy of the gold disk — slower/larger, but works.
    """
    name = distro_name(team_name)
    gold = gold_vhdx_path(repo_root)
    child = team_vhdx_path(repo_root, team_name)
    _clear_readonly(gold)
    if _distro_registered(name):
        return name
    if child.is_file():
        # Distro registration lost; reattach the same child (do not stack another link).
        try:
            _import_in_place(name, child)
            return name
        except ShellError:
            _remove_child(child)

    used_differencing = False
    try:
        _create_differencing_child(gold, child)
        used_differencing = True
    except ShellError:
        _remove_child(child)
        try:
            _create_full_copy_child(gold, child)
        except OSError as copy_exc:
            raise ShellError(f"Could not create team disk (full copy failed): {copy_exc}") from copy_exc

    try:
        _import_in_place(name, child)
    except ShellError as exc:
        detail = str(exc).casefold()
        parent_denied = (
            used_differencing
            and (
                "parent virtual hard disk" in detail
                or "chain of virtual hard disks" in detail
                or "0xc03a0016" in detail
            )
        )
        _remove_child(child)
        if not parent_denied:
            raise
        # Differencing child is useless to WSL — copy the whole gold disk instead.
        try:
            _create_full_copy_child(gold, child)
            _import_in_place(name, child)
        except (OSError, ShellError) as copy_exc:
            _remove_child(child)
            raise ShellError(
                "WSL cannot use a linked (differencing) clone of the golden image "
                "(no access to the parent VHDX). Full copy also failed.\n"
                f"{copy_exc}"
            ) from copy_exc
    return name


@dataclass
class TeamShell:
    """One interactive bash per team over a real ConPTY (nano/vim/apt TUI work)."""

    distro: str
    repo_root: Path
    on_output: Callable[[str], None] | None = None
    locked: bool = False
    transcript: str = ""
    _cwd_challenge: str | None = None
    _copied: set[str] = field(default_factory=set)
    _pty: Any = None
    _reader: threading.Thread | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _cols: int = 80
    _rows: int = 24

    def start(self) -> None:
        if self._pty is not None and self._pty.isalive():
            return
        try:
            from winpty import PtyProcess
        except ImportError as exc:
            raise ShellError(
                "pywinpty is required for the interactive desk terminal.\n"
                "Install with: pip install pywinpty"
            ) from exc

        # Real TTY so nano/less/apt behave like a normal Linux box.
        # Pass argv as a list — a quoted cmdline makes winpty look for a bogus exe name.
        wsl = _wsl_exe()
        self._pty = PtyProcess.spawn(
            [
                wsl,
                "-d",
                self.distro,
                "-u",
                "player",
                "--",
                "bash",
                "-l",
            ],
            dimensions=(self._rows, self._cols),
        )
        self._reader = threading.Thread(target=self._read_loop, name="relay-pty-out", daemon=True)
        self._reader.start()

    def close(self) -> None:
        pty = self._pty
        self._pty = None
        if pty is None:
            return
        try:
            if pty.isalive():
                pty.write("\x04")  # Ctrl-D best-effort
                pty.terminate(force=True)
        except Exception:
            try:
                pty.terminate(force=True)
            except Exception:
                pass

    def set_locked(self, locked: bool) -> None:
        self.locked = locked

    def resize(self, cols: int, rows: int) -> None:
        cols = max(20, int(cols))
        rows = max(8, int(rows))
        self._cols = cols
        self._rows = rows
        pty = self._pty
        if pty is None or not pty.isalive():
            return
        try:
            pty.setwinsize(rows, cols)
        except Exception:
            pass

    def ensure_challenge(self, challenge_id: str, public_dir: Path) -> None:
        """Copy public/ once into the distro, then cd there."""
        self.start()
        if challenge_id not in self._copied:
            self._copy_public(challenge_id, public_dir)
            self._copied.add(challenge_id)
        if self._cwd_challenge != challenge_id:
            # Visible in the terminal so teammates see the folder switch.
            # Force it: a baton lock would otherwise swallow the cd and
            # leave the shell in the previous challenge.
            folder = challenge_id.replace("'", "")
            self.write_keys(f"cd '/challenges/{folder}' && pwd\r", force=True)
            self._cwd_challenge = challenge_id

    def send_line(self, line: str) -> None:
        """Compatibility helper: type a full line and press Enter."""
        text = (line or "").rstrip("\r\n")
        self.write_keys(text + "\r")

    def write_keys(self, data: str, *, force: bool = False) -> None:
        """Send raw keystrokes to the PTY (blocked while baton is out)."""
        if (self.locked and not force) or not data:
            return
        pty = self._pty
        if pty is None or not pty.isalive():
            raise ShellError(f"bash for {self.distro} is not running")
        with self._lock:
            pty.write(data)

    def _read_loop(self) -> None:
        pty = self._pty
        if pty is None:
            return
        # Hand each read to the GUI before blocking again. pty.read() waits
        # for the next byte, so holding a chunk here hides command output
        # until the next key — usually Ctrl+C. The widget already coalesces paints.
        while True:
            try:
                if not pty.isalive():
                    break
                chunk = pty.read(4096)
            except EOFError:
                break
            except Exception:
                break
            if not chunk:
                time.sleep(0.01)
                continue
            text = chunk if isinstance(chunk, str) else chunk.decode("utf-8", errors="replace")
            self._append_transcript(text)
            callback = self.on_output
            if callback is None:
                continue
            try:
                callback(text)
            except Exception:
                pass

    def _append_transcript(self, text: str) -> None:
        with self._lock:
            self.transcript += text
            # Cap memory so day-long events don't balloon.
            if len(self.transcript) > 400_000:
                self.transcript = self.transcript[-300_000:]

    def _copy_public(self, challenge_id: str, public_dir: Path) -> None:
        root = Path(public_dir).resolve()
        if not root.is_dir():
            raise ShellError(f"public directory missing: {root}")
        # Windows writes into the distro; the distro never mounts the repo.
        dest = Path(rf"\\wsl$\{self.distro}\challenges\{challenge_id}")
        # Ensure /challenges exists as player (or root once).
        mkdir = _run(
            [
                _wsl_exe(),
                "-d",
                self.distro,
                "-u",
                "root",
                "--",
                "bash",
                "-c",
                "mkdir -p /challenges && chown player:player /challenges",
            ],
            timeout=60.0,
        )
        if mkdir.returncode != 0:
            raise ShellError(
                f"could not prepare /challenges:\n{(mkdir.stderr or mkdir.stdout or '').strip()}"
            )
        # Wait briefly for \\wsl$ to appear after the first command.
        for _ in range(40):
            if Path(rf"\\wsl$\{self.distro}\challenges").is_dir():
                break
            time.sleep(0.25)
        else:
            raise ShellError(f"\\\\wsl$\\{self.distro} is not reachable yet")

        if dest.exists():
            shutil.rmtree(dest)
        dest.mkdir(parents=True, exist_ok=True)
        for path in sorted(root.rglob("*")):
            rel = path.relative_to(root)
            target = dest.joinpath(*rel.parts)
            if path.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            elif path.is_file():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target)
        # Make challenge bin/ runnable as bare names when present.
        fix = _run(
            [
                _wsl_exe(),
                "-d",
                self.distro,
                "-u",
                "root",
                "--",
                "bash",
                "-c",
                (
                    f"chown -R player:player /challenges/{challenge_id} && "
                    f"if [ -d /challenges/{challenge_id}/bin ]; then "
                    f"  chmod +x /challenges/{challenge_id}/bin/* 2>/dev/null || true; "
                    f"  for f in /challenges/{challenge_id}/bin/*.py; do "
                    f"    [ -f \"$f\" ] || continue; "
                    f"    base=$(basename \"$f\" .py); "
                    f"    ln -sfn \"$f\" /challenges/{challenge_id}/bin/\"$base\"; "
                    f"  done; "
                    f"fi"
                ),
            ],
            timeout=60.0,
        )
        if fix.returncode != 0:
            raise ShellError(
                f"could not finalize challenge tree:\n{(fix.stderr or fix.stdout or '').strip()}"
            )


def open_team_shell(
    repo_root: Path,
    team_name: str,
    *,
    on_output: Callable[[str], None] | None = None,
) -> TeamShell:
    require_desk_runtime(repo_root)
    name = create_linked_clone(repo_root, team_name)
    shell = TeamShell(distro=name, repo_root=repo_root, on_output=on_output)
    shell.start()
    return shell


def repo_root_from_config(config_path: Path) -> Path:
    """config/config.toml → repo root."""
    path = config_path.resolve()
    if path.parent.name == "config":
        return path.parent.parent
    return path.parent
