# Terminal Relay

Timed team game for Windows. Players rotate on a physical baton (or a stand-in), pick categories from a board, and answer either a picture question or a real Linux shell challenge.

Needs Python 3.11 or newer. Desk challenges also need WSL2 — see [docs/wsl-desk.md](docs/wsl-desk.md).

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

Build the golden Kali WSL image once, after WSL2, `kali-linux`, and `New-VHD` are available:

```powershell
wsl --install -d kali-linux
wsl -d kali-linux   # finish first-time setup, then exit
powershell -ExecutionPolicy Bypass -File scripts\build_relay_gold.ps1
```

## Start

```powershell
relay run
relay run --fake-device
relay quick
```

With the fake baton, click the game window, press `1`–`6` to insert a baton, and `P` to pull it out.

## Layout

| Path | What it is |
|------|------------|
| `src/baton_relay/` | Application |
| `tests/` | pytest |
| `config/config.toml` | Event settings. The in-app CONFIG screen edits this file |
| `questions/` | Board categories stored as JSON, plus their pictures |
| `challenges/<id>/` | One desk category. `public/` is copied into the team shell. `private/` stays on the host |
| `staff/` | Solutions. Not loaded by the game, and not copied into a team shell |
| `docs/` | Config, questions, results, WSL, controller, baton wiring, serial protocol |
| `firmware/` | CircuitPython for the RP2040 baton reader |
| `scripts/` | Build the Kali image; regenerate desk challenge files |
| `images/` | Local golden disk (`relay-gold.vhdx`). Not in git |
| `data/`, `results/` | Local runs. Not in git |

`[questions].files` in `config/config.toml` lists the board. Each entry is one category: a JSON file or a challenge folder.

Desk categories: Steghide, Photo Note, Anthem, Unwrap, Wordlist, Hashcat, Regex, Crackme, Telenet, XOR Pair, One Byte, Repeat Key. Picture category: Fake Logos (`questions/fake_logos.json`).

Default game length is 25 minutes. Pulling the baton pauses the leg timer and leaves the terminal transcript in place.
