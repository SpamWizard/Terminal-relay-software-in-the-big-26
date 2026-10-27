# Terminal Relay — fresh Windows install

Timed team game for one Windows PC. Players pass a baton (or use the keyboard as a stand-in), pick a category, and answer a picture question or a real Linux shell challenge.

Do these steps on a PC that just finished a clean Windows setup. Steps 1–3 only install tools. The game files stay put until step 4, because downloading them asks for a GitHub password.

You need Windows 11 or Windows 10 22H2, edition **Pro, Education, or Enterprise** (Home has no `New-VHD`, and the Linux challenges will not run), CPU virtualization turned on, an admin login, internet, and **40 GB free on C:**. The project will live at `C:\relay`. Documents is often OneDrive on a new PC, and WSL cannot mount a Linux disk that lives in a synced folder.

Check virtualization before anything else. Press `Ctrl+Shift+Esc`, click **Performance**, click **CPU**, and read **Virtualization**. It has to say **Enabled**. If it says Disabled: Start, power icon, hold Shift and click Restart, then Troubleshoot, Advanced options, UEFI Firmware Settings, Restart. Turn on **Intel Virtualization Technology**, **VT-x**, **SVM Mode**, or **AMD-V**, save, and boot back to Windows.

There are two windows in this guide:

- **PowerShell** — right-click Start, click **Terminal** (Windows 10: **Windows PowerShell**). Title bar does not say Administrator.
- **Admin PowerShell** — right-click Start, click **Terminal (Admin)** (Windows 10: **Windows PowerShell (Admin)**), click **Yes**. Title bar starts with `Administrator:`.

Run the blocks in PowerShell, not the black Command Prompt. Click the window, `Ctrl+V`, Enter. Wait until the prompt comes back before the next step.

## 1. Install Git and Python 3.12.10

1. Open [https://ninite.com](https://ninite.com).
2. Under **Developer Tools**, check **Git** only. Do not check Python — Ninite’s newest Python breaks the pygame install later.
3. Click **Get Installer** and run the downloaded exe. Wait until Ninite finishes and closes.
4. Download [Python 3.12.10 (64-bit)](https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe) and run it.
5. On the first screen, check **Add python.exe to PATH**, then click **Install Now**. Wait until it finishes.
6. Press the Windows key, type `App execution aliases`, press Enter, and switch **off** `python.exe` and `python3.exe`.

Close every terminal window, open a new PowerShell, and run this block:

```powershell
git --version
python --version
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned -Force
```

You want a git version line and `Python 3.12.10`. The last line lets the later scripts run for this Windows user.

## 2. Install WSL and the Hyper-V disk tools

Open an **Admin PowerShell** and run this block:

```powershell
wsl --install
Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V-Management-PowerShell -All
```

When it finishes, restart the PC. Start, power icon, Restart. Do this even if only one of the two commands asked for a restart.

If an Ubuntu window opens after reboot and asks for a UNIX username, type `setup`, press Enter, type a password twice (nothing shows as you type), then type `exit` and press Enter. This project does not use Ubuntu.

Open a normal PowerShell and run this block:

```powershell
wsl --status
Get-Command New-VHD
```

The status text should say the default version is **2**, and `Get-Command` should print `New-VHD`. If `wsl` is not recognized, restart once more and run that block again.

## 3. Install Kali

Open a **PowerShell** and run this block:

```powershell
wsl --install -d kali-linux
```

A Kali window opens when the download finishes. Click that window.

1. At `Enter new UNIX username:` type `setup` and press Enter.
2. Type a password and press Enter. Type it again and press Enter. Characters are hidden.
3. At the `$` prompt, type `exit` and press Enter.

Back in PowerShell, run this block:

```powershell
wsl -l -v
```

`kali-linux` has to be in the list at version **2**. If the version is 1, run this block and wait, then run `wsl -l -v` again:

```powershell
wsl --set-version kali-linux 2
```

The `setup` user is only for this stock Kali. The game makes its own user, `player`, inside the disk you build in step 5.

Stop here until you have the GitHub password. Steps 1–3 are the whole machine setup.

## 4. Download the game

Open a **PowerShell**. Git will ask you to sign in to GitHub. Use the password you were given. Run this block:

```powershell
cd C:\
git clone https://github.com/SpamWizard/Terminal-relay-software-in-the-big-26.git relay
cd C:\relay
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
relay --help
```

The prompt should show `(.venv)` and the help text should list `run`, `quick`, `probe`, and `reset`. The download takes a few minutes.

Any later window that needs the `relay` command starts with this block:

```powershell
cd C:\relay
.\.venv\Scripts\Activate.ps1
```

## 5. Build the golden Kali disk

Leave the PC on, plugged in, and online. This often takes 20–60 minutes. It installs the challenge tools, copies the public challenge files in, and writes `C:\relay\images\relay-gold.vhdx`. During the build, Windows holds two copies of Kali, which is why you wanted 40 GB free.

Close any Kali or Ubuntu window (`exit` at its prompt). Open a **PowerShell** and run this block:

```powershell
cd C:\relay
powershell -ExecutionPolicy Bypass -File scripts\build_relay_gold.ps1
```

Wait until the prompt comes back. The last lines include:

```text
Done. Kali golden parent: C:\relay\images\relay-gold.vhdx
```

Leave that file writable. A read-only copy makes WSL say `Access is denied` when a team starts. Team disks are separate files under `C:\relay\data\wsl\`.

If the script stops early, fix the one thing it named and run the build block again:

- `wsl.exe not found` — repeat step 2 and restart.
- `New-VHD not found` — repeat the Admin PowerShell block in step 2 and restart.
- `No Kali distro found`, or a note that Kali still needs first-time setup — repeat step 3, then build again.
- `gold setup script failed` or `challenge check failed` — the network dropped during `apt`. Reconnect and run the build block again.

## 6. Start the game

Open a **PowerShell** and run this block:

```powershell
cd C:\relay
.\.venv\Scripts\Activate.ps1
relay run --fake-device
```

The game opens fullscreen. Leave that PowerShell window open; closing it closes the game.

1. Click the game window.
2. Type a team name and a name in the `#1`, `#2`, and `#3` boxes. All three are required.
3. Click **START**.
4. Press `1` to plug in player 1. The category board opens.
5. Click a category. A desk category opens a Linux terminal. The first team waits about a minute while Windows copies the golden disk.
6. Press `P` to pull the baton. Press `2` or `3` to hand it to the next player.

| Key | Action |
|---|---|
| `1` `2` `3` | Plug in that player |
| `P` | Pull the baton. Space and Backspace do the same |
| `F6` | Skip, or show categories that are waiting |
| `Esc` | Leave fullscreen. `F11` toggles it. `Alt+F4` quits |

To skip the name screen, run this block in the same window. That also uses the keyboard baton.

```powershell
relay quick
```

## Optional hardware

**Xbox pad.** Plug it in before you start. On the launch screen click **CONFIG**, open Xbox, click **Save**. Hold **LT + D-pad up** for one second to unlock it. Button list: [docs/controller.md](docs/controller.md).

**Pico baton reader.** Skip this if the keyboard is enough. Flash CircuitPython, then copy `C:\relay\firmware\boot.py` and `C:\relay\firmware\code.py` onto the `CIRCUITPY` drive. Wiring is in [docs/firmware.md](docs/firmware.md). Then run this block:

```powershell
cd C:\relay
.\.venv\Scripts\Activate.ps1
relay probe
```

`HB` lines mean the board is alive. Press `Ctrl+C`, then run this block. It has no `--fake-device`. The port setting in `config\config.toml` is `auto`.

```powershell
relay run
```

## Next time, and between teams

Run this block:

```powershell
cd C:\relay
.\.venv\Scripts\Activate.ps1
relay run --fake-device
```

Use `relay run` when the Pico is plugged in. Between teams, with `(.venv)` on the prompt, run this block:

```powershell
relay reset
```

That archives checkpoints and deletes team Linux disks. It leaves `images\relay-gold.vhdx` in place. Scores land in `C:\relay\results\<team>\<timestamp>\summary.json`. See [docs/results.md](docs/results.md).

Match length and roster are the **CONFIG** button on the launch screen, which writes `config\config.toml`. Default game is 25 minutes (`game_seconds = 1500`), a leg is 100 seconds, team size is 3. The rest of the file is in [docs/config.md](docs/config.md).

Tests, from the same `(.venv)` prompt: `pytest`.

Rebuilding the golden disk after a challenge edit is the same block as step 5. Details: [docs/wsl-desk.md](docs/wsl-desk.md). Run `relay reset` afterward so the next team gets the new disk.
