# Staff writeups

Solutions for the board. The game does not load this file, and nothing here is copied into a team shell.

Flags are `TR{...}`. Desk challenges are 100 points.

## Binary

`bits.txt` is the flag as 8-bit groups, high bit on the left, with no separators.

```bash
python3 -c "b=open('bits.txt').read().strip(); print(''.join(chr(int(b[i:i+8],2)) for i in range(0,len(b),8)))"
```

Flag: `TR{eight_bits}`

## Morse

`signal.txt` is Morse. Spaces separate letters and ` / ` separates words. The message is `CLEAR SIGNAL`. Lowercase it and join the words with an underscore.

Flag: `TR{clear_signal}`

## Whitespace

Each line of `letter.txt` ends with eight spaces and tabs. A space is 0, a tab is 1, left bit first. `cat -A` shows a tab as `^I` and the end of the line as `$`.

Flag: `TR{trailing_off}`

## Zero Width

`memo.txt` has U+200B (0) and U+200C (1) mixed through the letters. In file order, eight bits are one character, high bit first.

```bash
python3 -c "t=open('memo.txt',encoding='utf-8').read(); b=''.join('0' if c=='\u200b' else '1' for c in t if c in '\u200b\u200c'); print(''.join(chr(int(b[i:i+8],2)) for i in range(0,len(b),8)))"
```

Flag: `TR{thin_space}`

## LSB

`postcard.png` is a real PNG. steghide reads JPEG, BMP, and WAV, so it has nothing to do here. The flag is in the least significant bit of the red, green, and blue bytes, in that order, row by row, high bit first. A zero byte ends it. `zsteg` calls that order `b1,rgb,lsb,xy`. Install it with `sudo gem install zsteg` if the command is missing. Kali does not always ship an apt package for it.

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
