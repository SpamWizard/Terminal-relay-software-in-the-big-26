# Terminal Relay

Needs Python 3.11 or newer on Windows, plus WSL2 for desk challenges (see [docs/wsl-desk.md](docs/wsl-desk.md)).

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

Build the golden **Kali** WSL image once (after WSL2 + `kali-linux` + `New-VHD` work):

```powershell
wsl --install -d kali-linux
wsl -d kali-linux   # finish first-time setup, then exit
powershell -ExecutionPolicy Bypass -File scripts\build_relay_gold.ps1
```

See [docs/wsl-desk.md](docs/wsl-desk.md).

## Start

```powershell
relay run
relay run --fake-device
relay quick
```

With the fake baton, click the game window, then press control `1`–`6` to put a baton in and `P` to pull it out.

## Content

- **Desk challenges** under `challenges/` — real Linux shell per team (linked clone of `images/relay-gold.vhdx`).
- **Fake Logos** — picture multiple-choice in `questions/06_fake_logos.json`.

Default game length is 25 minutes. Baton freeze keeps the terminal transcript; teammates talk across the handoff.
