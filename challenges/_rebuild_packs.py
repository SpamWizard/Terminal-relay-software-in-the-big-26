"""One-shot author helper to regenerate challenge public/private content."""

from __future__ import annotations

import base64
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def main() -> None:
    # find_the_line
    ssid = "SaintconGuest"
    flag = f"TR{{{hashlib.sha256(ssid.encode()).hexdigest()[:8]}}}"
    d = ROOT / "find_the_line"
    write(
        d / "challenge.json",
        f"""{{
  "id": "find_the_line",
  "set_id": "find_the_line",
  "title": "Find The Line",
  "type": "desk",
  "prompt": "Ops left a briefing and a wifi scan dump. The flag is TR{{X}} where X is the first 8 hex chars of sha256(SSID). Find the conference SSID, then hash it.",
  "points": 150,
  "accepted": ["{flag}"],
  "panes": ["files", "terminal"]
}}
""",
    )
    notes = d / "public" / "notes.txt"
    if notes.exists():
        notes.unlink()
    write(
        d / "public" / "briefing.txt",
        """INTERNAL — do not post to Discord

Badge printers authenticate against the guest SSID.
Token format for the desk check-in app:

  TR{ first 8 hex chars of sha256(SSID) }

SSID is somewhere in the scan dump. Ignore BSSIDs.
""",
    )
    write(
        d / "public" / "scan.txt",
        """# iwlist fake dump
Cell 01 - Address: AA-AA-AA-AA-AA-01
          ESSID:"FreeAirportWiFi"
          Quality=20/70
Cell 02 - Address: AA-AA-AA-AA-AA-02
          ESSID:"xfinitywifi"
          Quality=18/70
Cell 03 - Address: AA-AA-AA-AA-AA-03
          ESSID:"AndroidAP_8821"
          Quality=12/70
Cell 04 - Address: AA-AA-AA-AA-AA-04
          ESSID:"SaintconGuest"
          Quality=55/70
Cell 05 - Address: AA-AA-AA-AA-AA-05
          ESSID:"SaintconStaff-DoNotUse"
          Quality=40/70
Cell 06 - Address: AA-AA-AA-AA-AA-06
          ESSID:"HP-Print-42"
          Quality=10/70
# decoy token that is NOT the flag
# TR{decoy_not_this}
""",
    )
    write(d / "private" / "flag.txt", flag + "\n")
    write(d / "private" / "solution.md", f"SSID {ssid} → {flag}\n")
    print("find_the_line", flag)

    # bash_crumbs
    pwd_word = "flipper"
    md5 = hashlib.md5(pwd_word.encode(), usedforsecurity=False).hexdigest()
    flag = f"TR{{{pwd_word}}}"
    d = ROOT / "bash_crumbs"
    write(
        d / "challenge.json",
        f"""{{
  "id": "bash_crumbs",
  "set_id": "bash_crumbs",
  "title": "Bash Crumbs",
  "type": "desk",
  "prompt": "Shell history from a volunteer laptop. They hashed a service password and never wrote it down in cleartext. Crack it. Flag is TR{{password}}.",
  "points": 250,
  "accepted": ["{flag}"],
  "panes": ["files", "terminal"]
}}
""",
    )
    write(
        d / "public" / "history.txt",
        f"""cd ~
ls
ping 8.8.8.8
# trying to remember the svc account password
echo -n oreo | md5sum
echo -n potato | md5sum
echo -n baton | md5sum
# finally stored the hash we need to match:
# svc_acct md5={md5}
cd /opt/desk
cat wordlist.txt
# note to self: password is ON the wordlist, stop guessing random snacks
exit
""",
    )
    words = [
        "oreo",
        "mint",
        "potato",
        "baton",
        "relay",
        "sheep",
        "goose",
        "crt",
        "flipper",
        "legos",
        "badge",
        "saintcon",
        "guest",
        "staff",
        "konami",
        "temple",
        "router",
        "cdrom",
        "modem",
        "pager",
        "beeper",
        "squish",
        "beanie",
        "velcro",
        "cone",
    ]
    write(d / "public" / "wordlist.txt", "\n".join(words) + "\n")
    write(d / "private" / "flag.txt", flag + "\n")
    write(d / "private" / "solution.md", f"md5 {md5} → {pwd_word} → {flag}\n")
    print("bash_crumbs", flag)

    # page_source
    payload = "relay_view_source"
    flag = f"TR{{{payload}}}"
    b64 = base64.b64encode(payload.encode()).decode()
    d = ROOT / "page_source"
    write(
        d / "challenge.json",
        f"""{{
  "id": "page_source",
  "set_id": "page_source",
  "title": "Page Source",
  "type": "desk",
  "prompt": "The page looks empty on purpose. The real token is base64-encoded in the markup. Decode it and wrap as TR{{...}}.",
  "points": 200,
  "accepted": ["{flag}"],
  "panes": ["page", "files", "terminal"],
  "page_file": "index.html"
}}
""",
    )
    write(
        d / "public" / "index.html",
        f"""<!DOCTYPE html>
<html>
<head><title>Status</title>
<style>
  body {{ font-family: sans-serif; background: #111; color: #ccc; }}
  .hidden {{ display: none; }}
</style>
</head>
<body>
  <h1>All systems nominal</h1>
  <p>Nothing to see in the rendered view.</p>
  <div class="hidden" data-token="{b64}"></div>
  <script>
  // decoy — this is not the flag
  const decoy = "TR{{look_in_the_markup_not_here}}";
  </script>
</body>
</html>
""",
    )
    write(d / "private" / "flag.txt", flag + "\n")
    write(d / "private" / "solution.md", f"data-token {b64} → {payload} → {flag}\n")
    print("page_source", flag)

    # stego_tail
    inner = "stego_xor_tail"
    flag = f"TR{{{inner}}}"
    key = 0x42
    xored = bytes(b ^ key for b in flag.encode())
    d = ROOT / "stego_tail"
    png = (REPO / "questions" / "images" / "logos" / "radioshack.png").read_bytes()
    (d / "public" / "logo.png").write_bytes(png + b"\n" + xored + b"\n")
    write(
        d / "challenge.json",
        f"""{{
  "id": "stego_tail",
  "set_id": "stego_tail",
  "title": "Stego Tail",
  "type": "desk",
  "prompt": "Something was appended after logo.png. It is not plaintext. Read the note for how to recover it.",
  "points": 250,
  "accepted": ["{flag}"],
  "panes": ["files", "terminal"]
}}
""",
    )
    write(
        d / "public" / "note.txt",
        """Artist said they "keyed" the trailer with decimal 66.
You will need to XOR every appended byte with that value.
Python in this terminal is fine.
""",
    )
    write(d / "private" / "flag.txt", flag + "\n")
    write(
        d / "private" / "solution.md",
        "Read trailer after IEND, XOR each byte with 66 (0x42). "
        f"python -c works. → {flag}\n",
    )
    hint = d / "public" / "xor_hint.py"
    if hint.exists():
        hint.unlink()
    print("stego_tail", flag)

    # broken_check
    flag = f"TR{{{hashlib.sha256(b'baton').hexdigest()[:12]}}}"
    d = ROOT / "broken_check"
    write(
        d / "challenge.json",
        f"""{{
  "id": "broken_check",
  "set_id": "broken_check",
  "title": "Broken Check",
  "type": "desk",
  "prompt": "check.py is supposed to print TR{{sha256(real_password)[:12]}} when the password is right. The compare is buggy and you cannot rely on running it as-is. Read the source, figure out the intended token, submit that.",
  "points": 300,
  "accepted": ["{flag}"],
  "panes": ["files", "terminal"]
}}
""",
    )
    write(
        d / "public" / "check.py",
        '''"""Password check — prints a derived token when the password is right.

Usage:
  python check.py <password>
"""

import hashlib
import sys

# Real password for the desk station
PASSWORD = "baton"

# Decoy — this is NOT accepted by scoring
# FLAG = "TR{nope_read_the_prompt}"


def token_for(password: str) -> str:
    digest = hashlib.sha256(password.encode()).hexdigest()[:12]
    return f"TR{{{digest}}}"


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: python check.py <password>")
        raise SystemExit(1)
    guess = sys.argv[1].strip()
    # BUG: compares against a slice, so the real password never matches
    if guess == PASSWORD[1:]:
        print(token_for(guess))
    else:
        print("nope")


if __name__ == "__main__":
    main()
''',
    )
    write(d / "private" / "flag.txt", flag + "\n")
    write(
        d / "private" / "solution.md",
        "Change PASSWORD[1:] to PASSWORD, run: python check.py baton → "
        + flag
        + "\nBuggy path with 'aton' prints a different TR{} that does not score.\n",
    )
    print("broken_check", flag)


if __name__ == "__main__":
    main()
