# Challenge ideas — merged, deduplicated, and rated against your current board

**Sources:** `argon.txt`, `fable 5.1.txt`, `grok.txt`, `sonnet.txt`
**Duplicate removed:** `muse.txt` is a byte-for-byte copy of `argon.txt` (same file hash), so it counts as the same source.

**Suggested by:** A = Argon/Muse · F = Fable 5.1 · G = Grok · S = Sonnet
More letters = more models independently suggested the same idea — that's the best signal for what to build.

**Result:** ~98 idea mentions across the 4 unique lists → **46 genuinely new ideas** + **9 ideas that are really just variants of tiles you already have** (Section 2).

---

## 1. Your current board — the difficulty baseline

All 12 tiles are `desk` type, 100 points, `panes: ["files", "terminal"]`. Rated 1–5 by steps needed, tools needed, and how much the prompt gives away (checked against `challenges/*/challenge.json`, `staff/writeups.md`, and the actual source files):

| Rating | Tile | What the player actually does |
|---|---|---|
| 1 | Crackme | Read 8 lines of Python, reverse `emkcor` → `rockme` |
| 1 | Steghide | One command; tool *and* passphrase are both in the prompt |
| 1 | Gate | `xxd`/`strings` a binary, read ASCII in the dump |
| 1.5 | Hashcat | `hashcat -m 0` against an 8-word list |
| 1.5 | Wordlist | `john --format=raw-md5` against a short list |
| 1.5 | Telenet | Read source, build `TELENET <text> <char-count>` |
| 2 | Photo Note | `exiftool`, then base64-decode the comment |
| 2 | Anthem | `file` says zip, `unzip -P anthem` (password given) |
| 2 | Regex | `grep -E '^[a-z]+[0-9]$'` over 400 near-miss lines |
| 2 | XOR | Brute 256 keys with the supplied `xor.py` helper |
| 2 | Hangman | Play with 5 misses (or XOR-decode the phrase in source) |
| 2.5 | Unwrap | base64 → hex → ROT13, three chained steps |

**The board spans 1 to 2.5 out of 5.** Nothing on it requires: picking a second tool yourself, writing a script from scratch, a GUI program, or a new domain (git, network, database, audio, web). Every prompt names the tool or the passphrase. Sonnet's line — *"your current set is mostly easy"* — is accurate.

### Difficulty labels used for the new ideas

| Label | Meaning | Points if you build it |
|---|---|---|
| **Easier** | Easier than your easiest tile (Crackme) | 50–100 |
| **Same** | Fits the current board, 1–2.5 | 100 |
| **Step up** | ~3 — two tools, a short loop you write yourself, or a tool the prompt *doesn't* name | 150–200 |
| **Big step** | 4+ — GUI, real scripting, or a whole new domain | 250–300 |

> ⚠️ **Fit warning:** your harness only has `files` + `terminal` panes. Ideas marked 🎧/🌐 need a GUI (Audacity, Wireshark, image editor) or a running local server (Flask) — they don't drop into the current `desk` format without new infrastructure. Everything else does.

---

## 2. Not new — variants of tiles you already have

Building these as-is would feel like a repeat of an existing tile. Listed so you don't build them by accident:

| Idea | It's really just… | From |
|---|---|---|
| Wrong extension — `file` reveals the real type ("Magic", "Wrong Name") | Anthem, minus the password | F, S |
| Flag in a PNG `tEXt` chunk | Photo Note, but on a PNG instead of JPEG | F |
| Flag in `docProps/core.xml` inside a `.docx` | Photo Note + Anthem (unzip, read metadata) | S |
| Compiled binary, `strings \| grep TR{` ("Strings Only", "ELF strings/symbols") | Gate | F, S |
| `checker.py` compares `b64encode(input)` to a constant — decode the constant | Crackme | F |
| Single Caesar, unknown shift ("Caesar Brute") | Layer 3 of Unwrap, on its own | F, S |
| Single-step Base32 / ROT47 / URL-decode | One layer of Unwrap with a different alphabet | F, S |
| `grep TR{` in a huge log ("Grep count") | Regex, but with no regex needed | F |
| Three-message handshake / port-knock sequence | Telenet, with a sequence instead of a format | F, S |

---

## 3. New ideas, deduplicated and rated

### Encoding & classic ciphers

| Idea | What the player does | Tool | Difficulty | Closest tile | From |
|---|---|---|---|---|---|
| **Binary** | `bits.txt` is 0s and 1s; group by 8 → ASCII | any converter | **Easier** | Crackme | A |
| **Morse (text)** | `.`/`-` groups → letters → word | Morse table | **Easier** | Unwrap | A, G |
| **Rail Fence** | 3-rail transposition cipher | CyberChef / script | **Same** | Unwrap | S |
| **Keyboard shift** | Text typed one key right on QWERTY; shift back by hand | eyes only | **Same** | Unwrap | A, G |
| **Vigenère, key given** | Keyword is in the prompt/title/`key.txt`; decrypt | CyberChef / script | **Same** | Unwrap | A, F, S |
| **Encoding stack v2** | Base32 → ROT47 → URL-encoding (same shape, new alphabets) | `base32 -d`, CyberChef | **Same** | Unwrap | F, S |
| **JWT** | Base64url-decode the middle segment, read the `flag` claim | `base64 -d`, jwt.io | **Same** | Photo Note | A, F, S |
| **Case bits** | Uppercase = 1, lowercase = 0; 8 letters = 1 byte | short Python | **Step up** | — | A |
| **Repeating-key XOR** | 3-byte key; plaintext known to start `TR{`; loop keys until prefix matches | Python | **Step up** | XOR | F, G |
| **Small RSA** 🎧 | Factor small `n`, compute `d`, decrypt `c` | factordb / sympy | **Big step** | — | S |

### Hidden text (stego)

| Idea | What the player does | Tool | Difficulty | Closest tile | From |
|---|---|---|---|---|---|
| **Acrostic** | First letter of each poem line spells the flag | eyes only | **Easier** | — | A |
| **Whitespace** | Trailing spaces/tabs in a paragraph are the hidden bits | `stegsnow -C` or `cat -A` | **Same** | Steghide | A, G, S |
| **Zero-width** | Invisible U+200B/U+200C characters between letters are bits | `xxd` to spot them, then Python | **Step up** | Steghide | A, F, G |
| **LSB in PNG** | Steghide *fails* on PNG — `zsteg` pulls text from low bits instead | `zsteg` | **Step up** | Steghide | A, F, S |
| **Spectrogram** 🎧 | `.wav` looks like noise; flag is drawn in the spectrogram view | Audacity / `sox` | **Big step** | — | A, F, S |
| **Reversed speech** 🎧 | Reverse a garbled clip; a voice spells the flag | Audacity / `sox reverse` | **Big step** | — | A |
| **Morse (audio)** 🎧 | Beeps spell the flag; decode by ear or script | ear / Morse tool | **Big step** | — (audio form of Morse above) | A, F, S |

> **Disagreement worth knowing:** Grok explicitly says skip anything needing a GUI, to keep the board "one terminal skill per tile." Argon/Fable/Sonnet all love Spectrogram as a "wow" tile. Given your `files`+`terminal`-only panes, Grok's position matches your current build — Spectrogram is only cheap if you add an audio/GUI pane.

### Files, archives & forensics

| Idea | What the player does | Tool | Difficulty | Closest tile | From |
|---|---|---|---|---|---|
| **Appended zip** | Image views fine, but a zip is glued after the image's end marker | `binwalk -e` or `unzip photo.png` | **Same** | Anthem | A, F, G, S |
| **Nested archives** | zip → tar → gz … 3–8 layers; `file` names each next layer | `file`, `tar`, `gunzip` | **Same** (longer, not harder) | Anthem | A, G |
| **QR code** | `badge.png` is a QR code; scan it, base64-decode the result | `zbarimg` | **Same** | Photo Note | G |
| **Git history** | Flag was committed, then deleted in a later commit | `git log -p` / `git show` | **Same** | Anthem | A, G, S |
| **SQLite** | `.tables`, then one `SELECT` among ~20 decoy rows | `sqlite3` | **Same** | Anthem | A, G |
| **File modes** | Empty files; their octal permission bits *are* the flag characters | `stat -c '%a'` | **Step up** | Photo Note | G |
| **Broken PNG header** | First 8 bytes zeroed; `file` says "data"; repair the magic bytes | hex editor / `xxd -r` | **Step up** | Gate | A, F |
| **Packet capture** | One HTTP request among noise carries the flag in plain text | `tshark -Y http` / Wireshark 🎧 | **Step up** with tshark, **Big step** with Wireshark | — | A, S |
| **QR quadrants** 🎧 | 4 shuffled quarter-images of one QR code; reassemble, then scan | PIL / image editor | **Big step** | — (harder form of QR code) | A |
| **Deleted file** | Tiny FAT `disk.img` with a deleted file to recover | `photorec` / `testdisk` / `strings` | **Big step** | — | S |

### Text processing & logs

| Idea | What the player does | Tool | Difficulty | Closest tile | From |
|---|---|---|---|---|---|
| **Word that appears once** | Every word repeats except one | `sort \| uniq -u` | **Same** | Regex | F, G, S |
| **CSV column/filter** | Rows in a CSV; filter by status/column, print one field (e.g. latest `OK` user) | `awk`, `cut`, `sort -u` | **Same** | Regex | F, G |
| **Log hunt** | 500–10,000 log lines; exactly one success/`/admin` 200 line — flag is that user/IP | `grep`, `awk` | **Same** | Regex | A, S |
| **CSV sum** | Flag is `TR{total of one column}` over a large CSV | `awk` / `pandas` | **Step up** | Regex | S |

### Reversing & scripting

| Idea | What the player does | Tool | Difficulty | Closest tile | From |
|---|---|---|---|---|---|
| **Math gate (sqrt)** | Source says `n*n == <bignum>`; take the square root | Python | **Same** | Crackme | F |
| **Luhn checksum** | Readable source; find a number that passes the Luhn check | Python | **Same** | Telenet | F |
| **Vault (PIN brute-force)** | PIN isn't in the source — only its SHA256 is; loop 0000–9999 | Python loop | **Step up** | Crackme → Hashcat | A |
| **Ltrace** | Binary builds password at runtime (`strings` misses it); `ltrace` shows the `strcmp` | `ltrace` | **Step up** | Gate / Crackme | G, S |
| **Compiled Python (.pyc)** | Only `check.pyc` given; inspect constants/disassemble to recover the password | `dis`, `pycdc` | **Step up** | Crackme | G, S |
| **Patch it** | `check.py` has an `if` that always fails; edit/bypass it to print the flag | text editor | **Step up** | Crackme | S |
| **Obfuscated JS** | `page.js` builds the flag with `String.fromCharCode`; just run it | `node` | **Step up** | Crackme | S |
| **Timed math quiz** | 5 arithmetic questions with a time limit — too fast by hand, so script it | Python + pipes | **Big step** | Telenet | S |
| **Latin square** | Program prints the flag only for a valid 4×4 Latin square input | reasoning / script | **Big step** | Telenet | S |

### Password cracking

| Idea | What the player does | Tool | Difficulty | Closest tile | From |
|---|---|---|---|---|---|
| **Identify-then-crack** | Prompt never says the algorithm; identify SHA-1 first, *then* crack | `hashid` + `hashcat -m 100` / john | **Step up** | Hashcat / Wordlist | F, G, S |
| **Zip crack** | ZipCrypto `secret.zip`; crack against the small wordlist | `zip2john` / `fcrackzip` | **Step up** | Anthem / Hashcat | F, S |
| **Hash + mangling rules** | Wordlist has the base word; password is `word2024` — needs `--rules` | hashcat / john rules | **Big step** | Hashcat | F |
| **Shadow file** | One `/etc/shadow`-style line with a weak `$1$`/`$6$` hash | john | **Big step** | Wordlist | F |

### Web & network 🌐 — needs a local server, not just files

| Idea | What the player does | Difficulty | Closest tile | From |
|---|---|---|---|---|
| **Robots** | `/robots.txt` disallows a path; visit that path for the flag | **Same** (concept) | — | A, S |
| **View source** | Flag sits in an HTML comment | **Easier** (concept) | Gate | S |
| **Cookie** | Change `user=guest` → `admin` (or set `admin=true` cookie), reload | **Step up** | Telenet | A, S |
| **HTTP headers** | Follow `X-Next` headers across responses with `curl`, or send a required `User-Agent`/custom header | **Step up** | Telenet | G, S |

---

## 4. What to build first

**Consensus picks** (suggested by 3–4 of the 4 lists, fit your current format, fill a real gap):

| Priority | Idea | Why |
|---|---|---|
| 1 | **Appended zip** (A,F,G,S) | Only idea all four lists had. One new tool (`binwalk`), zero new infrastructure. |
| 2 | **Git history** (A,G,S) | Real forensic skill, ~5 min to build, nothing like it on the board. |
| 3 | **Word that appears once** (F,G,S) | One-liner solve (`sort \| uniq -u`), pairs with Regex as "shape vs. count." |
| 4 | **JWT** (A,F,S) | Same difficulty as Photo Note, teaches "tokens are just encoded JSON." |
| 5 | **Whitespace stego** (A,G,S) | Same slot as Steghide, different mechanism — and `stegsnow`/`cat -A` stays in-terminal. |
| 6 | **SQLite** (A,G) | First database tile; `.tables` + one `SELECT` is exactly your board's weight. |

**Best "step up" tiles** — these create the medium tier your board doesn't have yet (Sonnet's main criticism):

- **Vault** — the natural sequel to Crackme: you can't just *read* the answer anymore, you loop. (A)
- **LSB in PNG** — teaches "match the tool to the format": Steghide fails, `zsteg` works. (A,F,S)
- **Identify-then-crack** — Hashcat/Wordlist teach cracking; this teaches *naming the hash first*. (F,G,S)
- **Broken PNG header** — Gate teaches reading bytes with `xxd`; this teaches *repairing* them. (A,F)
- **Repeating-key XOR** — XOR is the 1-byte version; this is the real one, using the known `TR{` prefix as a crib. (F,G)

**If you want a full second board of 8** (Grok's set — every tile a different command): Nested archives, Appended zip, Git history, Ltrace, SQLite, Word-that-appears-once, Morse (text), Identify-then-crack.

**Skip / defer:**
- 🎧 **Spectrogram, Morse audio, Reversed speech, QR quadrants, Wireshark** — good challenges, wrong harness. They need a GUI/audio pane you don't have yet.
- 🌐 **All web ideas** — need a running Flask/local server per challenge; your `desk` challenges are static files. Biggest infrastructure cost of anything here.
- **Small RSA, Hash rules, Shadow, Timed quiz, Latin square** — real difficulty jumps (4+); fine as a hard tier later, but they'd be outliers if added now while everything else is 100 pts.
- Anything in **Section 2** — you'd be building the same tile twice.

---

## 5. Bottom line vs. your current challenges

- Your 12 tiles: **difficulty 1–2.5, all one step, tool always named in the prompt, all terminal-only.**
- These 46 new ideas: **~2 easier, ~20 the same, ~17 a step up, ~9 a big step.**
- The single biggest gap in your current set isn't difficulty — it's **coverage**: no git, database, archive-peeling, or binary-tracing tiles. Appended zip, Git history, SQLite, and Nested archives fix that at *the same difficulty you already have*, which is why they rank above the flashier audio/web ideas.
- To grow difficulty without scaring players: add **Vault, LSB, and Broken PNG header** first — each is a direct sequel to a tile players already solved (Crackme, Steghide, Gate), so the step up feels earned instead of sudden.
