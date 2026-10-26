"""Team Linux shell: linked-clone WSL disk + one long-lived bash piped through the GUI."""

from __future__ import annotations

import os
import shutil
import subprocess
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

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


def _run(args: list[str], *, timeout: float = 120.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        encoding="utf-8",
        errors="replace",
    )


def list_relay_distros() -> list[str]:
    # `wsl -l` writes UTF-16LE on Windows; decode explicitly.
    proc = subprocess.run(
        [_wsl_exe(), "-l", "-q"],
        capture_output=True,
        timeout=60.0,
        check=False,
    )
    raw = proc.stdout or b""
    text = raw.decode("utf-16-le", errors="ignore") if raw[:2] == b"\xff\xfe" or b"\x00" in raw[:64] else raw.decode("utf-8", errors="ignore")
    names: list[str] = []
    for line in text.splitlines():
        name = line.replace("\x00", "").strip()
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


def create_linked_clone(repo_root: Path, team_name: str) -> str:
    """Create a differencing VHDX from the golden parent and import it in place."""
    name = distro_name(team_name)
    gold = gold_vhdx_path(repo_root)
    child = team_vhdx_path(repo_root, team_name)
    if _distro_registered(name):
        return name
    if child.is_file():
        # Distro registration lost; reattach the same child (do not stack another link).
        _shutdown_wsl()
        proc = _run([_wsl_exe(), "--import-in-place", name, str(child)], timeout=180.0)
        if proc.returncode != 0:
            raise ShellError(
                f"import-in-place failed for {name}:\n{(proc.stderr or proc.stdout or '').strip()}"
            )
        return name

    child.parent.mkdir(parents=True, exist_ok=True)
    _shutdown_wsl()
    ps = (
        f"$ErrorActionPreference = 'Stop'; "
        f"New-VHD -ParentPath '{gold}' -Path '{child}' -Differencing -BlockSizeBytes 1MB | Out-Null"
    )
    proc = _run(["powershell", "-NoProfile", "-Command", ps], timeout=120.0)
    if proc.returncode != 0:
        raise ShellError(
            f"New-VHD differencing clone failed:\n{(proc.stderr or proc.stdout or '').strip()}"
        )
    proc = _run([_wsl_exe(), "--import-in-place", name, str(child)], timeout=180.0)
    if proc.returncode != 0:
        if child.is_file():
            child.unlink(missing_ok=True)
        raise ShellError(
            f"import-in-place failed for {name}:\n{(proc.stderr or proc.stdout or '').strip()}"
        )
    return name


@dataclass
class TeamShell:
    """One bash per team. GUI writes lines; a reader thread delivers stdout."""

    distro: str
    repo_root: Path
    on_output: Callable[[str], None] | None = None
    locked: bool = False
    transcript: str = ""
    _cwd_challenge: str | None = None
    _copied: set[str] = field(default_factory=set)
    _proc: subprocess.Popen[bytes] | None = None
    _reader: threading.Thread | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def start(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            return
        # Non-interactive bash: the GUI owns the prompt. Keep a login so PATH is sane.
        self._proc = subprocess.Popen(
            [
                _wsl_exe(),
                "-d",
                self.distro,
                "-u",
                "player",
                "--",
                "bash",
                "--noprofile",
                "--norc",
                "-c",
                "export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin; "
                "export HOME=/home/player; cd \"$HOME\"; exec bash --noprofile --norc",
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=0,
        )
        self._reader = threading.Thread(target=self._read_loop, name="relay-bash-out", daemon=True)
        self._reader.start()
        # Quiet boot: drop bash's empty first prompt noise by sending a no-op.
        self._write_raw(":\n")

    def close(self) -> None:
        proc = self._proc
        self._proc = None
        if proc is None:
            return
        try:
            if proc.stdin and not proc.stdin.closed:
                proc.stdin.close()
        except OSError:
            pass
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            try:
                proc.kill()
            except OSError:
                pass

    def set_locked(self, locked: bool) -> None:
        self.locked = locked

    def ensure_challenge(self, challenge_id: str, public_dir: Path) -> None:
        """Copy public/ once into the distro, then cd there."""
        self.start()
        if challenge_id not in self._copied:
            self._copy_public(challenge_id, public_dir)
            self._copied.add(challenge_id)
        if self._cwd_challenge != challenge_id:
            # Visible in the transcript so teammates see the folder switch.
            self.send_line(f"cd /challenges/{challenge_id} && pwd")
            self._cwd_challenge = challenge_id

    def send_line(self, line: str) -> None:
        if self.locked:
            return
        text = (line or "").rstrip("\r\n")
        self._append_transcript(f"› {text}\n")
        self._write_raw(text + "\n")

    def _write_raw(self, data: str) -> None:
        proc = self._proc
        if proc is None or proc.stdin is None or proc.poll() is not None:
            raise ShellError(f"bash for {self.distro} is not running")
        raw = data.encode("utf-8", errors="replace")
        with self._lock:
            proc.stdin.write(raw)
            proc.stdin.flush()

    def _read_loop(self) -> None:
        proc = self._proc
        if proc is None or proc.stdout is None:
            return
        while True:
            chunk = proc.stdout.read(1)
            if not chunk:
                break
            try:
                text = chunk.decode("utf-8", errors="replace")
            except Exception:
                continue
            self._append_transcript(text)
            if self.on_output is not None:
                try:
                    self.on_output(text)
                except Exception:
                    pass

    def _append_transcript(self, text: str) -> None:
        with self._lock:
            self.transcript += text

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
