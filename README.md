# Terminal Relay

Needs Python 3.11 or newer.

## Setup

```bash
python -m venv .venv
```

Turn the venv on:

```bash
# Windows (PowerShell)
.\.venv\Scripts\Activate.ps1

# Windows (cmd)
.venv\Scripts\activate

# Linux / macOS
source .venv/bin/activate
```

Install it:

```bash
pip install -e ".[dev]"
```

## Start

Real baton (board plugged in):

```bash
relay run
```

Fake baton (no board, use the keyboard):

```bash
relay run --fake-device
```

With the fake baton, click the game window, then press `1`–`6` to put a baton in and `P` to pull it out.
