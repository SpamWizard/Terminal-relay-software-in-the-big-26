"""Generate the 14 desk packs: search → follow clue → find TR{...} (no encode-the-answer)."""

from __future__ import annotations

import base64
import hashlib
import json
import zlib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def meta(
    folder: str,
    *,
    title: str,
    prompt: str,
    points: int,
    flag: str,
    panes: list[str] | None = None,
    page_file: str | None = None,
) -> None:
    d = ROOT / folder
    panes = panes or ["files", "terminal"]
    payload: dict = {
        "id": folder,
        "set_id": folder,
        "title": title,
        "type": "desk",
        "prompt": prompt,
        "points": points,
        "accepted": [flag],
        "panes": panes,
    }
    if page_file:
        payload["page_file"] = page_file
    write(d / "challenge.json", json.dumps(payload, indent=2) + "\n")
    write(d / "private" / "flag.txt", flag + "\n")
    write(d / "private" / "solution.md", "See WRITEUP.md\n")


def main() -> None:
    # ── 1) PCAP DNS: labels → hostname → look up in inventory ─────────────
    host = "badge.ops.local"
    flag = "TR{dns_badge_desk}"
    meta(
        "pcap_dns",
        title="PCAP DNS",
        prompt=(
            "dns.log is a text export of queries. Rebuild the hostname from the "
            "label[] lines (in index order), then find that host in inventory.txt. "
            "The flag is already written there — do not invent one."
        ),
        points=200,
        flag=flag,
    )
    write(
        ROOT / "pcap_dns" / "public" / "dns.log",
        """# truncated text export — not a real pcap
12:01:02.100  UDP  10.0.0.5:53122 > 10.0.0.53:53  DNS Q?
12:01:02.101  query name label[0]=badge
12:01:02.101  (noise) TTL=64 id=0x4a2c
12:01:02.102  query name label[2]=local
12:01:02.103  PTR clutter ignore.me.in-addr.arpa
12:01:02.104  query name label[1]=ops
12:01:02.105  A?  (answer omitted)
# decoy host that is NOT the query target
# seen later: mail.spam.invalid
""",
    )
    write(
        ROOT / "pcap_dns" / "public" / "inventory.txt",
        f"""# asset inventory — grep the hostname you rebuild
mail.spam.invalid     role=mx      note=TR{{decoy_not_dns}}
print.ops.local       role=print  note=ask_facilities
{host}                role=badge  note={flag}
ntp.ops.local         role=time   note=none
ignore.me.in-addr.arpa role=ptr   note=noise
""",
    )
    write(
        ROOT / "pcap_dns" / "private" / "WRITEUP.md",
        f"""# PCAP DNS — writeup

**Flag:** `{flag}`

## Solve
1. `grep label dns.log` → badge + ops + local → `{host}`
2. `grep {host} inventory.txt` → `{flag}`
3. Ignore decoy hosts and `TR{{decoy_not_dns}}`
""",
    )
    print("pcap_dns", flag)

    # ── 2) Auth once: unique Accepted user → their mailbox ────────────────
    user = "relaybot"
    flag = "TR{once_is_enough}"
    meta(
        "auth_once",
        title="Auth Once",
        prompt=(
            "auth.log: find the username that has exactly one successful login. "
            "Then open that user's mail under mailboxes/. The flag is in the message."
        ),
        points=200,
        flag=flag,
    )
    write(
        ROOT / "auth_once" / "public" / "auth.log",
        """sshd: Failed password for root from 10.1.1.9
sshd: Failed password for admin from 10.1.1.9
sshd: Failed password for guest from 10.1.1.2
sshd: Accepted password for relaybot from 10.1.1.40
sshd: Failed password for relaybot from 10.1.1.41
sshd: Failed password for root from 10.1.1.9
sshd: Accepted publickey for deploy from 10.1.1.7
sshd: Accepted publickey for deploy from 10.1.1.7
sshd: Failed password for ubuntu from 10.1.1.3
# deploy succeeded twice — not "once"
""",
    )
    write(
        ROOT / "auth_once" / "public" / "mailboxes" / "deploy" / "inbox.txt",
        "Subject: deploy keys\nTR{wrong_mailbox_deploy}\n",
    )
    write(
        ROOT / "auth_once" / "public" / "mailboxes" / "root" / "inbox.txt",
        "Subject: noise\nno flag here\n",
    )
    write(
        ROOT / "auth_once" / "public" / "mailboxes" / user / "inbox.txt",
        f"Subject: door badge handoff\n\nUse this at the desk:\n{flag}\n",
    )
    write(
        ROOT / "auth_once" / "private" / "WRITEUP.md",
        f"""# Auth Once — writeup

**Flag:** `{flag}`

## Solve
1. Grep `Accepted` — `deploy` twice, `{user}` once
2. `cat mailboxes/{user}/inbox.txt` → `{flag}`
3. Do not submit the deploy mailbox decoy
""",
    )
    print("auth_once", flag)

    # ── 3) Zip comment → filename to open (b64 is a path, not the flag) ───
    path_core = "drops/whisper.txt"
    flag = "TR{zip_whisper}"
    b64 = base64.b64encode(path_core.encode()).decode()
    meta(
        "zip_comment",
        title="Zip Comment",
        prompt=(
            "badge.zip looks empty. Its zip comment is base64 of a *path*, not the flag. "
            "Decode the path, then open that file under public/."
        ),
        points=200,
        flag=flag,
    )
    zpath = ROOT / "zip_comment" / "public" / "badge.zip"
    zpath.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zpath, "w") as zf:
        zf.writestr(".keep", "")
        zf.comment = b64.encode("ascii")
    write(
        ROOT / "zip_comment" / "public" / "drops" / "whisper.txt",
        f"handoff note\n{flag}\n",
    )
    write(
        ROOT / "zip_comment" / "public" / "drops" / "decoy.txt",
        "TR{not_the_zip_path}\n",
    )
    write(
        ROOT / "zip_comment" / "public" / "hint.txt",
        "zipfile.ZipFile(...).comment  →  b64  →  open that relative path\n",
    )
    write(
        ROOT / "zip_comment" / "private" / "WRITEUP.md",
        f"""# Zip Comment — writeup

**Flag:** `{flag}`  
**Comment b64 →** `{path_core}`

## Solve
1. Read zip comment → b64 decode → `{path_core}`
2. `cat {path_core}` → `{flag}`
""",
    )
    print("zip_comment", flag)

    # ── 4) Nested b64 → path → open file ──────────────────────────────────
    path_core = "cases/case_07.txt"
    flag = "TR{triple_wrap}"
    layer = path_core.encode()
    for _ in range(3):
        layer = base64.b64encode(layer)
    blob = layer.decode()
    meta(
        "nested_b64",
        title="Nested B64",
        prompt=(
            "blob.txt is base64 nested a few times. Keep decoding until you get a "
            "relative path, then open that file. The flag is inside — do not wrap yourself."
        ),
        points=200,
        flag=flag,
    )
    write(ROOT / "nested_b64" / "public" / "blob.txt", blob + "\n")
    write(
        ROOT / "nested_b64" / "public" / "cases" / "case_07.txt",
        f"case closed\n{flag}\n",
    )
    write(
        ROOT / "nested_b64" / "public" / "cases" / "case_01.txt",
        "TR{wrong_case}\n",
    )
    write(
        ROOT / "nested_b64" / "public" / "note.txt",
        "If it still looks like base64, decode again. Stop when it looks like a path.\n",
    )
    write(
        ROOT / "nested_b64" / "private" / "WRITEUP.md",
        f"""# Nested B64 — writeup

**Flag:** `{flag}`

## Solve
`b64` ×3 on blob.txt → `{path_core}` → `cat` that → `{flag}`
""",
    )
    print("nested_b64", flag)

    # ── 5) Char codes → filename → open ───────────────────────────────────
    fname = "payload.js"
    flag = "TR{char_codes}"
    codes = ",".join(str(ord(c)) for c in fname)
    meta(
        "char_codes",
        title="Char Codes",
        prompt=(
            "The page looks blank. Markup builds a filename from character codes. "
            "Recover the name, open that file next to the HTML, submit the TR{{}} inside."
        ),
        points=200,
        flag=flag,
        panes=["page", "files", "terminal"],
        page_file="index.html",
    )
    write(
        ROOT / "char_codes" / "public" / "index.html",
        f"""<!DOCTYPE html>
<html><head><title>blank</title>
<style>body{{background:#111;color:#111}}.hid{{display:none}}</style>
</head><body>
<p>Nothing rendered on purpose.</p>
<script>
const decoy = "TR{{not_this_one}}";
const parts = [{codes}];
// String.fromCharCode.apply(null, parts)  → filename beside this page
</script>
</body></html>
""",
    )
    write(
        ROOT / "char_codes" / "public" / fname,
        f"// recovered from fromCharCode\nconst token = \"{flag}\";\n",
    )
    write(
        ROOT / "char_codes" / "public" / "decoy.js",
        'const token = "TR{wrong_file}";\n',
    )
    write(
        ROOT / "char_codes" / "private" / "WRITEUP.md",
        f"""# Char Codes — writeup

**Flag:** `{flag}`

## Solve
1. `parts = [{codes}]` → `{fname}`
2. `cat {fname}` → `{flag}`
3. Ignore HTML decoy and decoy.js
""",
    )
    print("char_codes", flag)

    # ── 6) Two halves → ticket id → look up ───────────────────────────────
    ticket = "TKT-8814"
    flag = "TR{handoff_gold}"
    mid = len(ticket) // 2
    a, b = ticket[:mid], ticket[mid:]
    meta(
        "two_halves",
        title="Two Halves",
        prompt=(
            "a.txt and b.txt each hold half of a ticket id (concat a then b). "
            "Find that ticket in tickets.log and take the flag from that row."
        ),
        points=250,
        flag=flag,
    )
    write(ROOT / "two_halves" / "public" / "a.txt", a + "\n")
    write(ROOT / "two_halves" / "public" / "b.txt", b + "\n")
    write(
        ROOT / "two_halves" / "public" / "tickets.log",
        f"""TKT-1001  status=open   note=TR{{old_ticket}}
TKT-2200  status=closed note=noise
{ticket}  status=ready  note={flag}
TKT-8815  status=open   note=TR{{off_by_one}}
""",
    )
    write(
        ROOT / "two_halves" / "private" / "WRITEUP.md",
        f"""# Two Halves — writeup

**Flag:** `{flag}`

## Solve
1. Concat a+b → `{ticket}`
2. `grep {ticket} tickets.log` → `{flag}`
Yell the first half across the baton swap.
""",
    )
    print("two_halves", flag)

    # ── 7) Rule crack → password unlocks a named vault file ───────────────
    password = "Flipper2026"
    flag = "TR{rule_unlocked}"
    digest = hashlib.sha256(password.encode()).hexdigest()
    meta(
        "rule_crack",
        title="Rule Crack",
        prompt=(
            "hash.txt is sha256 of Capitalize(wordlist_entry)+\"2026\". "
            "Crack the password, then open vault/<password>.txt — flag is inside."
        ),
        points=250,
        flag=flag,
    )
    words = [
        "oreo",
        "mint",
        "potato",
        "baton",
        "relay",
        "sheep",
        "flipper",
        "legos",
        "badge",
        "squish",
        "beanie",
        "modem",
    ]
    write(ROOT / "rule_crack" / "public" / "wordlist.txt", "\n".join(words) + "\n")
    write(ROOT / "rule_crack" / "public" / "hash.txt", digest + "\n")
    write(
        ROOT / "rule_crack" / "public" / "rule.txt",
        "rule: Capitalize(word) + \"2026\"\nthen sha256 hex — that string is also a vault filename stem\n",
    )
    write(
        ROOT / "rule_crack" / "public" / "vault" / f"{password}.txt",
        f"opened with the cracked password\n{flag}\n",
    )
    write(
        ROOT / "rule_crack" / "public" / "vault" / "Flipper2025.txt",
        "TR{wrong_year}\n",
    )
    write(
        ROOT / "rule_crack" / "private" / "WRITEUP.md",
        f"""# Rule Crack — writeup

**Flag:** `{flag}`  
**Password:** `{password}`

## Solve
1. Rule-crack wordlist → `{password}`
2. `cat vault/{password}.txt` → `{flag}`
3. Do not submit the password as the flag
""",
    )
    print("rule_crack", flag)

    # ── 8) PDF EOF → path after XOR → open file ───────────────────────────
    path_core = "annex/tail.txt"
    flag = "TR{pdf_trailer}"
    key = 0x5A
    xored = bytes(b ^ key for b in path_core.encode())
    meta(
        "pdf_eof",
        title="PDF EOF",
        prompt=(
            "fake.pdf has bytes after %%EOF. note.txt gives the XOR key. "
            "Recover a relative path, open it, submit the TR{{}} inside."
        ),
        points=250,
        flag=flag,
    )
    pdf = (
        b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\nstartxref\n0\n%%EOF\n"
        + xored
        + b"\n"
    )
    (ROOT / "pdf_eof" / "public").mkdir(parents=True, exist_ok=True)
    (ROOT / "pdf_eof" / "public" / "fake.pdf").write_bytes(pdf)
    write(
        ROOT / "pdf_eof" / "public" / "note.txt",
        "Trailer after %%EOF is XOR'd with decimal 90 (0x5A). Result is a path.\n",
    )
    write(
        ROOT / "pdf_eof" / "public" / "annex" / "tail.txt",
        f"pulled from past %%EOF\n{flag}\n",
    )
    write(
        ROOT / "pdf_eof" / "public" / "annex" / "other.txt",
        "TR{wrong_annex}\n",
    )
    write(
        ROOT / "pdf_eof" / "private" / "WRITEUP.md",
        f"""# PDF EOF — writeup

**Flag:** `{flag}`

## Solve
1. XOR trailer with 90 → `{path_core}`
2. `cat {path_core}` → `{flag}`
""",
    )
    print("pdf_eof", flag)

    # ── 9) Pipeline A→B→C → path segments → cat ───────────────────────────
    flag = "TR{pipe_found}"
    meta(
        "pipeline_abc",
        title="Pipeline ABC",
        prompt=(
            "Run a.py, b.py, then c.py. Each prints one path segment. "
            "Join them with / and open that file for the flag."
        ),
        points=300,
        flag=flag,
    )
    write(ROOT / "pipeline_abc" / "public" / "a.py", 'print("out")\n')
    write(ROOT / "pipeline_abc" / "public" / "b.py", 'print("box")\n')
    write(ROOT / "pipeline_abc" / "public" / "c.py", 'print("final.txt")\n')
    write(
        ROOT / "pipeline_abc" / "public" / "out" / "box" / "final.txt",
        f"assembled path\n{flag}\n",
    )
    write(
        ROOT / "pipeline_abc" / "public" / "out" / "box" / "decoy.txt",
        "TR{wrong_leaf}\n",
    )
    write(
        ROOT / "pipeline_abc" / "private" / "WRITEUP.md",
        f"""# Pipeline ABC — writeup

**Flag:** `{flag}`

## Solve
1. a→`out` b→`box` c→`final.txt`
2. `cat out/box/final.txt` → `{flag}`
""",
    )
    print("pipeline_abc", flag)

    # ── 10) Probe: secret → points at a locker file ───────────────────────
    secret = "squish"
    flag = "TR{warm_enough}"
    meta(
        "probe_temp",
        title="Probe",
        prompt=(
            "python probe.py <guess> — lower distance is warmer. When distance hits 0 "
            "it prints a path. Open that path for the flag. Talk through guesses."
        ),
        points=300,
        flag=flag,
    )
    write(
        ROOT / "probe_temp" / "public" / "probe.py",
        '''"""Warmer/colder style probe. Usage: python probe.py <guess>"""
import sys

SECRET = "squish"


def distance(guess: str) -> int:
    g = guess.strip()
    n = max(len(g), len(SECRET))
    score = abs(len(g) - len(SECRET)) * 8
    for i in range(n):
        a = ord(g[i]) if i < len(g) else 0
        b = ord(SECRET[i]) if i < len(SECRET) else 0
        score += abs(a - b)
    return score


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: python probe.py <guess>")
        raise SystemExit(1)
    guess = sys.argv[1]
    d = distance(guess)
    if d == 0:
        print("open: locker/" + SECRET + ".txt")
    else:
        print(f"distance={d}  (0 wins)")


if __name__ == "__main__":
    main()
''',
    )
    write(
        ROOT / "probe_temp" / "public" / "locker" / f"{secret}.txt",
        f"hit distance 0\n{flag}\n",
    )
    write(
        ROOT / "probe_temp" / "public" / "locker" / "sheep.txt",
        "TR{cold}\n",
    )
    write(
        ROOT / "probe_temp" / "public" / "hint.txt",
        "Snack-themed mascot word. Short. Talk through guesses with your team.\n",
    )
    write(
        ROOT / "probe_temp" / "private" / "WRITEUP.md",
        f"""# Probe — writeup

**Flag:** `{flag}`  
**Secret:** `{secret}`

## Solve
1. Guess toward `{secret}` (or read SECRET in probe.py)
2. `python probe.py {secret}` → `open: locker/{secret}.txt`
3. `cat locker/{secret}.txt` → `{flag}`
""",
    )
    print("probe_temp", flag)

    # ── 11) Whitespace → filename → open ──────────────────────────────────
    fname = "bitflag.txt"
    flag = "TR{tabs_win}"
    bits = "".join(f"{ord(c):08b}" for c in fname)
    lines = []
    for i, bit in enumerate(bits):
        pad = "\t" if bit == "1" else " "
        lines.append(f"row_{i:02d}{pad}")
    meta(
        "whitespace",
        title="Whitespace",
        prompt=(
            "notes.txt trailing whitespace is a bitstream (space=0, tab=1), 8 bits per "
            "ASCII letter. Recover a filename, open it, submit the TR{{}} inside."
        ),
        points=300,
        flag=flag,
    )
    write(ROOT / "whitespace" / "public" / "notes.txt", "\n".join(lines) + "\n")
    write(
        ROOT / "whitespace" / "public" / fname,
        f"from the trailing tabs\n{flag}\n",
    )
    write(
        ROOT / "whitespace" / "public" / "other.txt",
        "TR{not_bitstream}\n",
    )
    write(
        ROOT / "whitespace" / "public" / "hint.txt",
        "python -c can show repr(line) to see \\t vs space. Result is a filename here.\n",
    )
    write(
        ROOT / "whitespace" / "private" / "WRITEUP.md",
        f"""# Whitespace — writeup

**Flag:** `{flag}`

## Solve
1. Trailing tab/space → bits → `{fname}`
2. `cat {fname}` → `{flag}`
""",
    )
    print("whitespace", flag)

    # ── 12) Checksum pick → case id → look up ─────────────────────────────
    winner = "CASE-4401"
    flag = "TR{correct_horse}"
    target = f"{zlib.crc32(winner.encode()) & 0xFFFFFFFF:08x}"
    decoys = ["CASE-4400", "CASE-4402", "CASE-9911", "CASE-1001", "CASE-7777"]
    meta(
        "checksum_pick",
        title="Checksum Pick",
        prompt=(
            f"Exactly one id in candidates.txt has crc32 hex {target}. "
            "Look that id up in casebook.txt and take the flag from that row."
        ),
        points=200,
        flag=flag,
    )
    write(
        ROOT / "checksum_pick" / "public" / "candidates.txt",
        "\n".join([*decoys[:2], winner, *decoys[2:]]) + "\n",
    )
    write(
        ROOT / "checksum_pick" / "public" / "target.txt",
        f"crc32 hex (unsigned) must equal: {target}\n",
    )
    write(
        ROOT / "checksum_pick" / "public" / "casebook.txt",
        f"""CASE-4400  note=TR{{almost}}
CASE-1001  note=noise
{winner}  note={flag}
CASE-7777  note=TR{{lucky_sevens}}
CASE-9911  note=closed
""",
    )
    write(
        ROOT / "checksum_pick" / "private" / "WRITEUP.md",
        f"""# Checksum Pick — writeup

**Flag:** `{flag}`  
**Matching id:** `{winner}` (crc32 `{target}`)

## Solve
1. crc32 each candidates.txt line → `{winner}`
2. `grep {winner} casebook.txt` → `{flag}`
""",
    )
    print("checksum_pick", flag)

    # ── 13) Map cell → letter → roster row ────────────────────────────────
    letter = "R"
    flag = "TR{map_room_r}"
    meta(
        "map_legend",
        title="Map Legend",
        prompt=(
            "map.txt is a grid (1-indexed rows down, columns right). "
            "What letter is at cell (3,5)? Look that letter up in roster.txt for the flag."
        ),
        points=150,
        flag=flag,
    )
    grid = [
        list("....."),
        list("....."),
        list("....R"),
        list("....."),
        list("....."),
    ]
    write(
        ROOT / "map_legend" / "public" / "map.txt",
        "\n".join("".join(row) for row in grid) + "\n",
    )
    write(
        ROOT / "map_legend" / "public" / "legend.txt",
        """. = empty floor
Letters A-Z mark stations
Cells are (row, column) with 1 = top/left
After you have the letter, check roster.txt
""",
    )
    write(
        ROOT / "map_legend" / "public" / "roster.txt",
        f"""A  station=alpha   note=TR{{not_a}}
B  station=bravo   note=noise
{letter}  station=relay   note={flag}
S  station=south   note=TR{{wrong_letter}}
""",
    )
    write(
        ROOT / "map_legend" / "private" / "WRITEUP.md",
        f"""# Map Legend — writeup

**Flag:** `{flag}`

## Solve
1. Cell (3,5) → `{letter}`
2. `grep ^{letter} roster.txt` (or just read it) → `{flag}`
3. Do not submit `TR{{{letter}}}`
""",
    )
    print("map_legend", flag)

    # ── 14) Wrong salt: REAL_SALT names a file with the flag ───────────────
    password = "baton"
    right_salt = "desk"
    flag = "TR{salt_file_wins}"
    meta(
        "wrong_salt",
        title="Wrong Salt",
        prompt=(
            "check.py hashes with the wrong salt and prints a fake TR{{}}. "
            "Find the real salt name in the source, then open salts/<that_name>.txt for the real flag."
        ),
        points=300,
        flag=flag,
    )
    write(
        ROOT / "wrong_salt" / "public" / "check.py",
        '''"""Usage: python check.py <password>"""
import hashlib
import sys

PASSWORD = "baton"
REAL_SALT = "desk"
# BUG: hash uses the staging salt
STAGING_SALT = "ops"


def token(password: str, salt: str) -> str:
    digest = hashlib.sha256((password + salt).encode()).hexdigest()[:12]
    return "TR{" + digest + "}"


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: python check.py <password>")
        raise SystemExit(1)
    guess = sys.argv[1].strip()
    if guess != PASSWORD:
        print("nope")
        return
    # Intended path was salts/REAL_SALT.txt — this print is a decoy
    print(token(guess, STAGING_SALT))


if __name__ == "__main__":
    main()
''',
    )
    write(
        ROOT / "wrong_salt" / "public" / "salts" / f"{right_salt}.txt",
        f"real salt material\n{flag}\n",
    )
    write(
        ROOT / "wrong_salt" / "public" / "salts" / "ops.txt",
        "TR{staging_salt_decoy}\n",
    )
    write(
        ROOT / "wrong_salt" / "private" / "WRITEUP.md",
        f"""# Wrong Salt — writeup

**Flag:** `{flag}`

## Solve
1. Read check.py — `REAL_SALT = "{right_salt}"` (script prints a hash decoy with `ops`)
2. `cat salts/{right_salt}.txt` → `{flag}`
3. Do not submit the printed hash token or salts/ops.txt
""",
    )
    print("wrong_salt", flag)

    print("done")


if __name__ == "__main__":
    main()
