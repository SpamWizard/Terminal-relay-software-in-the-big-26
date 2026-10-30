# Staff writeups

Solutions for the board. The game does not load this file, and nothing here is copied into a team shell.

Flags are `TR{...}`. Desk challenges are 100 points.

## Backwards

`note.txt` is one long line, reversed last character first. It is too long to read backwards by eye. `rev` restores the line. The flag is the `TR{...}` in that line.

```bash
rev note.txt
```

Flag: `TR{too_long_to_read}`

## Dot

`ls` shows nothing. `ls -a` shows the folder `.local`. The flag is in `.local/note.txt`. The file rail hides that path too.

```bash
ls -a
cat .local/note.txt
```

Flag: `TR{look_deeper}`

## Acrostic

`poem.txt` has a title, two stanzas, and a signature. Skip the title and the signature. The first letter of each remaining line spells one word per stanza: `QUIET` and `MARGIN`. The space between those words is an underscore.

Flag: `TR{quiet_margin}`

## Telnet

`telnet.py` is a pretend telnet client. It answers the RFC 854 command table: SE, NOP, DM, BRK, IP, AO, AYT, EC, EL, GA, SB, WILL, WONT, DO, DONT, and IAC. Are You There is the one that replies with the flag.

```bash
python3 telnet.py AYT
```

`python3 telnet.py "Are you there?"` and byte `246` are the same command. `help` prints the table.

Flag: `TR{are_you_there}`

## Plus One

`shift.txt` is the flag with every letter moved one step forward. `a` becomes `b`, and `z` wraps to `a`. Braces stay put. The word inside is long enough that shifting by hand is the slow way.

```bash
tr 'b-zaB-ZA' 'a-zA-Z' < shift.txt
```

Flag: `TR{onomatopoeia}`

## Binary

`bits.txt` is the flag as 8-bit groups, high bit on the left, with no separators.

```bash
python3 -c "b=open('bits.txt').read().strip(); print(''.join(chr(int(b[i:i+8],2)) for i in range(0,len(b),8)))"
```

Flag: `TR{eight_bits}`

## Railroad

`fence.txt` is three rails. A dot is an empty spot. Each column has one letter. Read those letters from left to right.

```bash
python3 -c "lines=open('fence.txt').read().splitlines(); print(''.join(next(ch for ch in col if ch!='.') for col in zip(*lines)))"
```

Flag: `TR{three_rails}`

## Whitespace

Each line of `letter.txt` ends with four spaces and then one character of the flag. `cat -A` shows the end of the line as `$`. The character just before each `$`, in order, is the flag.

```bash
cat -A letter.txt
```

Flag: `TR{trailing_off}`

## Zero Width

`memo.txt` reads as a normal note. A zero-width space (U+200B, bytes `e2 80 8b`) sits immediately before each flag character. Read the character after every mark.

```bash
python3 -c "t=open('memo.txt',encoding='utf-8').read(); print(''.join(t[i+1] for i,c in enumerate(t) if c=='\u200b'))"
```

Flag: `TR{thin_space}`

## LSB

`postcard.png` is a real PNG. steghide reads JPEG, BMP, and WAV, so it has nothing to do here. The flag is in the least significant bit of the red, green, and blue bytes, in that order, row by row, high bit first. A zero byte ends it. `zsteg` is installed on the desk image. It calls that order `b1,rgb,lsb,xy`.

```bash
python3 - <<'PY'
import struct, zlib, pathlib
data = pathlib.Path("postcard.png").read_bytes()
pos, idat = 8, b""
while pos + 12 <= len(data):
    n = int.from_bytes(data[pos:pos+4], "big")
    tag, chunk = data[pos+4:pos+8], data[pos+8:pos+8+n]
    pos += 12 + n
    if tag == b"IHDR":
        w, h = struct.unpack(">II", chunk[:8])
    elif tag == b"IDAT":
        idat += chunk
    elif tag == b"IEND":
        break
raw = zlib.decompress(idat)
stride = w * 3
rgb = b"".join(raw[y*(stride+1)+1:(y+1)*(stride+1)] for y in range(h))
acc = n = 0
out = []
for byte in rgb:
    acc = (acc << 1) | (byte & 1)
    n += 1
    if n == 8:
        if acc == 0:
            break
        out.append(chr(acc))
        acc = n = 0
print("".join(out))
PY
```

Flag: `TR{low_bits}`

## Broken PNG

`broken.png` is a PNG whose first 8 bytes are zeros. The signature is `89 50 4E 47 0D 0A 1A 0A`. The flag is a compressed `Comment`, so it shows up after the header is repaired.

```bash
python3 - <<'PY'
from pathlib import Path
path = Path("broken.png")
data = bytearray(path.read_bytes())
data[:8] = bytes.fromhex("89504e470d0a1a0a")
path.write_bytes(data)
PY
exiftool broken.png
```

Flag: `TR{magic_bytes}`

## Log Hunt

`access.log` has one line whose path is exactly `/admin` and whose status is `200`. `/administrator` and `/admin/` are near misses. The username on the real line is the flag.

```bash
awk '$5=="/admin" && $6==200 { print $2 }' access.log
```

Flag: `TR{marigold}`

## Patch It

`check.py` returns false on both branches, so no pin is accepted. Change the `return False` under `pin == "2468"` to `return True`, then run it. The flag is built in `reveal` and is not stored as text.

```bash
python3 check.py 2468
```

Flag: `TR{flip_the_check}`

## Identify

`hash.txt` is 40 hex characters, which is SHA-1. The prompt does not name the algorithm. `wordlist.txt` is short.

```bash
hashcat -m 100 -a 0 hash.txt wordlist.txt
```

Or:

```bash
john --format=raw-sha1 --wordlist=wordlist.txt hash.txt
john --show --format=raw-sha1 hash.txt
```

The password is `compass`.

Flag: `TR{compass}`
