# Challenge ideas (not built)

Same shape as the current desk packs: work in `public/`, talk across the baton, no plaintext accepted `TR{...}` sitting in an obvious file, about ~1.25 turns.

## Forensics / dumps

- **PCAP lite** — tiny text “packet log”; flag is a hostname reassembled from DNS queries split across lines
- **Auth log** — failed SSH attempts; flag is `TR{` + the only username that succeeded once `}`
- **Git crumbs** — `.git_log.txt` fake; flag buried in a commit message that was “amended away” but still in the dump
- **CSV of badge scans** — find the one row where entry != exit door; door id is part of the flag
- **Exif story** — image metadata fields (as a dumped text export) hold order/index of flag chunks
- **Deleted line** — file with `#` comments; real clue is the only line that was “removed” but left in a `.bak`
- **Timezone trap** — timestamps in UTC vs local; the matching hour is a numeric chunk of the flag

## Crypto / encoding (keep short)

- **ROT chain** — note says “rot13 then rot13 again” (identity) or “rot13 then reverse”
- **Multi-b64** — base64 nested 2–3 times; each stage looks like noise
- **Hex dump postcard** — `xxd`-style text; flag bytes at a stated offset
- **Vigenère with key in filename** — ciphertext in `body.txt`, key is the challenge folder theme word from a second file
- **Atbash / keyboard shift** — one page of ciphertext, hint is a SaintCon meme
- **Checksum pick** — five candidate strings; only one has the listed crc32/md5 prefix
- **Bit flip** — almost-flag string with one XOR’d character; note gives which index

## Stego / files that lie

- **Zip comment 2** — empty-looking zip; comment is b64 not plaintext
- **Polyglot** — file named `.txt` that is actually a tiny zip or vice versa
- **LSB as numbers** — not real LSB; a `pixels.csv` of 0/1 that spells ASCII
- **Append after PDF `%EOF`** — same trick as stego tail, different container
- **Two images** — difference of two hex dumps is the flag (they must align lines)
- **Whitespace stego** — trailing spaces/tabs encode bits (show with a python one-liner)
- **ID3 / fake mp3 header** — text file pretending to be tags; title field is encoded

## Web / markup (local only)

- **robots.txt** — points at a path that is another file in `public/`
- **HTML entities** — flag spelled with `&#x..;` only
- **CSS content** — `content: "..."` in a stylesheet file, not visible in rendered page
- **JS char codes** — `String.fromCharCode(84,82,...)` needs evaluation or manual decode
- **Hidden form value** — `value=` on a hidden input is b64
- **SVG title** — flag in `<title>` or `<desc>` of an SVG opened as text
- **Comment maze** — ten HTML comments; only the one that is valid b64 matters

## Code / reverse-lite

- **Wrong salt** — script hashes `password + salt` but uses the wrong salt variable; derive intended token from comments
- **Off-by-slice** — like Broken Check but the bug is `[:-1]` on the password
- **Assert never fires** — `assert False` before print; they must read what *would* print
- **Dead branch** — `if False:` block contains the derivation formula
- **Eval bait** — script prints a decoy; real flag is `sha256` of a constant defined above
- **Order of operations** — three small scripts; must run A then B then C and combine outputs (handoff gold)
- **Bytecode tease** — ship `challenge.pyc` disassembly as text (no real marshal pain)—opcodes spell the password length + hint

## Passwords / wordlists

- **Rules** — wordlist + “capitalize first, append year”; hash in a file
- **User:pass pairs** — crack one of five hashes; flag is that username
- **PIN** — 4-digit, hash given, brute with python `-c` loop (keep range tiny)
- **Keyboard walk** — password is on the wordlist but looks like `qwerty` adjacent keys
- **Leet** — `password` → `p@ssw0rd` rule stated in a sticky note file

## SaintCon / lore flavored

- **Dead community** — flyer text; “which contest never happened”; answer is a slug in `TR{slug}`
- **Committee initials** — match public handles to initials; order by badge number
- **AOL sound** — not audio: a file of modem handshake hex; decode a short phrase (or skip if too cute)
- **Badge layers** — ASCII art of a badge; flag in the layer labeled `silkscreen` in a companion json
- **Potato canon** — short lore doc; the year the potato first appeared is part of the flag

## Relay-first (built for talking)

- **Two halves** — `a.txt` / `b.txt`; neither contains `TR{`; concat then b64-decode
- **Phone tree** — three files; each has one digit of a 3-step cipher key; must share out loud
- **Map + legend** — map is ASCII; legend is separate; cell (3,5) is a letter
- **Checksum callout** — A computes md5 of file1, B of file2; flag is first 4 of each concatenated
- **Hot/cold** — `probe.py` takes a guess string and prints warmer/colder toward a secret (no flag in source—binary search by talking)

## Probably too hard / save for later

- Tiny local TCP “protocol” that errors verbosely (needs container wave)
- Full zip crypto with rockyou
- Real RSA toy with tiny primes (math time vs leg time)

## Author rules (so new packs don’t suck)

- Accepted `TR{...}` must not appear in `public/` plaintext
- Decoys that look like flags are encouraged
- Prefer two mental steps (find → transform)
- Aim ~1.25 baton turns; leave something yellable mid-solve
- Keep tools inside desk: `cat`, `grep`, `b64`, `md5`/`sha256`, `python -c`
