"""Team Linux shell: linked-clone WSL disk + one long-lived bash piped through the GUI."""

from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from baton_relay.deps import INSTALL_COMMAND
from baton_relay.results.log import team_slug


class ShellError(RuntimeError):
    """WSL / linked-clone / bash pipe failure."""


_ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b\][^\x07]*\x07|\x1b.")


def _looks_like_prompt(text: str) -> bool:
    visible = _ANSI.sub("", text).rstrip()
    return bool(visible) and visible[-1] in "$#%"


def _in_python_repl(text: str) -> bool:
    """True when the latest line is a Python prompt (``>>>`` or ``...``).

    A bare ``python3`` stays in the REPL. Ctrl-C only reprints ``>>>``, so a
    later ``cd`` is typed into Python and the next challenge never opens.
    """
    visible = _ANSI.sub("", text)
    lines = [line.strip() for line in visible.splitlines() if line.strip()]
    if not lines:
        return False
    last = lines[-1]
    return last in {">>>", "..."} or last.endswith(">>>") or last.endswith("...")


def distro_name(team_name: str) -> str:
    return f"relay-{team_slug(team_name)}"


def gold_vhdx_path(repo_root: Path) -> Path:
    return repo_root / "images" / "relay-gold.vhdx"


def team_vhdx_path(repo_root: Path, team_name: str) -> Path:
    return repo_root / "data" / "wsl" / team_slug(team_name) / "ext4.vhdx"


# Pre-copied gold child. Claimed (moved) when a team starts so the first
# desk open is a rename instead of a multi-hundred-MB copy.
STANDBY_SLUG = "_standby"


def standby_vhdx_path(repo_root: Path) -> Path:
    return repo_root / "data" / "wsl" / STANDBY_SLUG / "ext4.vhdx"


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


def _standby_ready(repo_root: Path) -> bool:
    path = standby_vhdx_path(repo_root)
    if not path.is_file():
        return False
    try:
        return path.stat().st_size > 0
    except OSError:
        return False


def ensure_standby_disk(repo_root: Path) -> Path:
    """Make sure a full gold copy sits at the standby path (not registered with WSL).

    Claiming this file on team start is a move, so the first desk open does not
    wait on a multi-hundred-MB copy from ``images/relay-gold.vhdx``.
    """
    require_desk_runtime(repo_root)
    gold = gold_vhdx_path(repo_root)
    child = standby_vhdx_path(repo_root)
    if _standby_ready(repo_root):
        gold_size = gold.stat().st_size
        try:
            if child.stat().st_size == gold_size:
                return child
        except OSError:
            pass
        # Stale/partial standby — rebuild.
        _remove_child(child)
    try:
        _create_full_copy_child(gold, child)
    except OSError as copy_exc:
        raise ShellError(f"Could not pre-copy golden disk: {copy_exc}") from copy_exc
    return child


def warm_standby_async(repo_root: Path) -> None:
    """Kick off a background gold copy. Safe to call often; no-ops if ready."""
    if _standby_ready(repo_root):
        gold = gold_vhdx_path(repo_root)
        child = standby_vhdx_path(repo_root)
        try:
            if gold.is_file() and child.stat().st_size == gold.stat().st_size:
                return
        except OSError:
            pass

    def _worker() -> None:
        try:
            ensure_standby_disk(repo_root)
        except Exception:
            # Warm is best-effort; team start still falls back to a live copy.
            pass

    threading.Thread(target=_worker, name="relay-warm-standby", daemon=True).start()


def _claim_standby(repo_root: Path, team_name: str) -> Path | None:
    """Move the standby disk into the team's path. Returns the child path or None."""
    standby = standby_vhdx_path(repo_root)
    if not _standby_ready(repo_root):
        return None
    child = team_vhdx_path(repo_root, team_name)
    if child.is_file():
        return None
    child.parent.mkdir(parents=True, exist_ok=True)
    try:
        _clear_readonly(standby)
        shutil.move(str(standby), str(child))
        _clear_readonly(child)
    except OSError:
        return None
    try:
        standby.parent.rmdir()
    except OSError:
        pass
    return child


def create_linked_clone(repo_root: Path, team_name: str) -> str:
    """Create a team disk from the golden parent and import it in place.

    Prefers a pre-copied standby disk (near-instant move). Otherwise tries a
    Hyper-V differencing (linked) clone. WSL often refuses those because HCS
    cannot open the parent VHDX (0xc03a0016). In that case we fall back to a
    full copy of the gold disk — slower/larger, but works.
    """
    name = distro_name(team_name)
    gold = gold_vhdx_path(repo_root)
    child = team_vhdx_path(repo_root, team_name)
    _clear_readonly(gold)
    if _distro_registered(name):
        if child.is_file():
            return name
        # The distro entry outlived its disk. Starting it only yields
        # "The system cannot find the path specified."
        _run([_wsl_exe(), "--unregister", name], timeout=180.0)
        _shutdown_wsl()
    if child.is_file():
        # Distro registration lost; reattach the same child (do not stack another link).
        try:
            _import_in_place(name, child)
            return name
        except ShellError:
            _remove_child(child)

    claimed = _claim_standby(repo_root, team_name)
    if claimed is not None:
        child = claimed
        try:
            _import_in_place(name, child)
        except ShellError:
            _remove_child(child)
            # Fall through to a fresh clone from gold.
        else:
            warm_standby_async(repo_root)
            return name

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
    warm_standby_async(repo_root)
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
    _cd_token: int = 0
    _cd_pause: float = 0.8
    _cd_thread: threading.Thread | None = None
    _pty: Any = None
    _reader: threading.Thread | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _cols: int = 80
    _rows: int = 24
    # While True, PTY bytes still go to transcript but not the on-screen terminal.
    _output_muted: bool = False

    def start(self) -> None:
        if self._pty is not None and self._pty.isalive():
            return
        try:
            from winpty import PtyProcess
        except ImportError as exc:
            raise ShellError(
                "pywinpty is required for the interactive desk terminal.\n"
                f"Install all project dependencies with: {INSTALL_COMMAND}"
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
        # Always re-enter. A previous cd can be typed into a running program
        # or a half-finished line and never run, and marking it done would
        # leave the next visit stuck in the old challenge folder.
        folder = challenge_id.replace("'", "").replace("/", "")
        with self._lock:
            self._cd_token += 1
            token = self._cd_token
        worker = threading.Thread(
            target=self._switch_dir,
            args=(token, folder),
            name="relay-cd",
            daemon=True,
        )
        self._cd_thread = worker
        self._cwd_challenge = challenge_id
        worker.start()

    def _switch_dir(self, token: int, folder: str) -> None:
        """Stop leftover input from the previous challenge, then cd quietly.

        The cd still runs in the real bash so the next command is in the right
        folder; Ctrl-C / cd / path checks stay off the on-screen terminal.

        Ctrl-C has to finish before the cd. This shell eats one typed
        character after an interrupt, and a Ctrl-U glued to the front of
        ``cd`` turns it into ``d`` (``d: command not found``) so the
        directory never changes. The leading space is the character that
        gets eaten instead.
        """
        self._output_muted = True
        ok = False
        try:
            self.write_keys("\x03", force=True)
            if self._cd_pause > 0 and not self._wait_for_prompt(token):
                return
            if token != self._cd_token:
                return
            # Ctrl-C does not leave ``python3``. Exit the REPL before cd, or
            # the directory change is executed as Python and never happens.
            for _ in range(2):
                if token != self._cd_token or not _in_python_repl(self.transcript):
                    break
                self.write_keys("exit()\r", force=True)
                if self._cd_pause > 0 and not self._wait_for_prompt(token):
                    return
            if token != self._cd_token:
                return
            # No `pwd` — we verify via a muted marker, then show one clean prompt.
            marker = f"__relay_cd_{token}__"
            self.write_keys(
                f" cd '/challenges/{folder}' && printf '%s\\n' '{marker}'\r",
                force=True,
            )
            if not self._wait_for_marker(token, marker):
                return
            if token != self._cd_token:
                return
            ok = True
        except ShellError:
            return
        finally:
            self._output_muted = False
        if not ok or token != self._cd_token:
            return
        # One fresh prompt on screen (correct path) without the cd echo.
        try:
            self.write_keys("\r", force=True)
        except ShellError:
            return

    def _wait_for_prompt(self, token: int) -> bool:
        """Wait until Ctrl-C's prompt redraw has settled, or the pause elapses."""
        deadline = time.monotonic() + self._cd_pause
        baseline = self.transcript
        previous = baseline
        stable = 0
        saw_new = False
        while time.monotonic() < deadline:
            if token != self._cd_token:
                return False
            time.sleep(0.05)
            current = self.transcript
            if current != baseline:
                saw_new = True
            if current == previous:
                stable += 1
                # The prompt that was already on screen does not count.
                # Wait until Ctrl-C prints a new one and it stops moving.
                if saw_new and stable >= 2 and _looks_like_prompt(current):
                    return True
            else:
                previous = current
                stable = 0
        return token == self._cd_token

    def _wait_for_marker(self, token: int, marker: str) -> bool:
        """Wait until the muted cd printed its success marker (or time out)."""
        if self._cd_pause <= 0:
            # Unit tests with a mock PTY skip the real settle wait.
            return token == self._cd_token
        deadline = time.monotonic() + max(self._cd_pause, 0.8) + 1.5
        while time.monotonic() < deadline:
            if token != self._cd_token:
                return False
            if marker in self.transcript:
                # Let the prompt after printf settle before unmuting.
                time.sleep(0.05)
                return True
            time.sleep(0.05)
        return marker in self.transcript

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
            if self._output_muted:
                continue
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
