"""Rebuild public files for the desk challenges on the board.

Writes challenges/*/public artifacts for binary, morse, whitespace, zero_width,
lsb, broken_png, log_hunt, patch_it, and identify.
"""

from __future__ import annotations

import base64
import codecs
import hashlib
import os
import random
import struct
import subprocess
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHALLENGES = ROOT / "challenges"

FLAG_PHOTO = b"TR{comment_section}"
FLAG_ANTHEM = b"TR{not_an_mp3}\n"
FLAG_UNWRAP = "TR{three_layers}"
WORD = b"lantern"


def _noise_jpeg(path: Path, seed: int, width: int, height: int) -> None:
    """Random-pixel JPEG via System.Drawing so steghide has coefficients to use."""
    path.parent.mkdir(parents=True, exist_ok=True)
    code = r"""
using System;
using System.Drawing;
using System.Drawing.Imaging;
using System.Linq;
using System.Runtime.InteropServices;
public static class NoiseJpeg {
    public static void Save(string path, int seed, int w, int h) {
        using (var bmp = new Bitmap(w, h, PixelFormat.Format24bppRgb)) {
            var rect = new Rectangle(0, 0, w, h);
            var data = bmp.LockBits(rect, ImageLockMode.WriteOnly, PixelFormat.Format24bppRgb);
            int bytes = Math.Abs(data.Stride) * h;
            byte[] buf = new byte[bytes];
            new Random(seed).NextBytes(buf);
            Marshal.Copy(buf, 0, data.Scan0, bytes);
            bmp.UnlockBits(data);
            var jpeg = ImageCodecInfo.GetImageEncoders().First(c => c.FormatID == ImageFormat.Jpeg.Guid);
            var ep = new EncoderParameters(1);
            ep.Param[0] = new EncoderParameter(Encoder.Quality, 90L);
            bmp.Save(path, jpeg, ep);
        }
    }
}
"""
    ps = (
        "Add-Type -AssemblyName System.Drawing; "
        f"Add-Type -TypeDefinition @'\n{code}\n'@ -ReferencedAssemblies System.Drawing; "
        f"[NoiseJpeg]::Save('{path}', {seed}, {width}, {height})"
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps],
        check=True,
    )


def _insert_jpeg_comment(path: Path, comment: str) -> None:
    data = path.read_bytes()
    if not data.startswith(b"\xff\xd8"):
        raise SystemExit(f"{path} is not a JPEG")
    payload = comment.encode("ascii")
    seg = b"\xff\xfe" + (len(payload) + 2).to_bytes(2, "big") + payload
    path.write_bytes(data[:2] + seg + data[2:])


def _crctable() -> list[int]:
    table = []
    for n in range(256):
        crc = n
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xEDB88320
            else:
                crc >>= 1
        table.append(crc)
    return table


def _zipcrypto_encrypt(password: bytes, data: bytes) -> bytes:
    table = _crctable()
    key0 = 305419896
    key1 = 591751049
    key2 = 878082192

    def crc32(ch: int, crc: int) -> int:
        return ((crc >> 8) ^ table[(crc ^ ch) & 0xFF]) & 0xFFFFFFFF

    def update(c: int) -> None:
        nonlocal key0, key1, key2
        key0 = crc32(c, key0)
        key1 = (key1 + (key0 & 0xFF)) & 0xFFFFFFFF
        key1 = (key1 * 134775813 + 1) & 0xFFFFFFFF
        key2 = crc32(key1 >> 24, key2)

    for p in password:
        update(p)

    out = bytearray()
    for p in data:
        k = key2 | 2
        c = p ^ (((k * (k ^ 1)) >> 8) & 0xFF)
        update(p)
        out.append(c & 0xFF)
    return bytes(out)


def _write_encrypted_zip(path: Path, name: str, data: bytes, password: bytes) -> None:
    crc = zlib.crc32(data) & 0xFFFFFFFF
    comp = zlib.compress(data)[2:-4]
    header = os.urandom(11) + bytes([(crc >> 24) & 0xFF])
    payload = _zipcrypto_encrypt(password, header + comp)
    name_b = name.encode("utf-8")
    local = struct.pack(
        "<IHHHHHIIIHH",
        0x04034B50,
        20,
        1,
        8,
        0,
        0,
        crc,
        len(payload),
        len(data),
        len(name_b),
        0,
    ) + name_b + payload
    central = struct.pack(
        "<IHHHHHHIIIHHHHHII",
        0x02014B50,
        20,
        20,
        1,
        8,
        0,
        0,
        crc,
        len(payload),
        len(data),
        len(name_b),
        0,
        0,
        0,
        0,
        0,
        0,
    ) + name_b
    eocd = struct.pack("<IHHHHIIH", 0x06054B50, 0, 0, 1, 1, len(central), len(local), 0)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(local + central + eocd)


def _write_gate() -> None:
    """ELF-shaped blob whose only English phrase is the flag body.

    xxd's ASCII column should show one readable phrase and nothing else.
    """
    import re

    phrase = b"TR{pass the baton}"
    # Dense non-letters so the dump still looks "binary", not empty.
    noise = bytes((i * 37 + 0x91) & 0xFF for i in range(0xA0))
    noise = bytes(b if b < 0x41 or b > 0x7A else (b ^ 0x80) for b in noise)

    # Tiny exit(0) stub so `file` still says ELF, then noise, then the phrase.
    code = bytes(
        [
            0xB8, 0x3C, 0x00, 0x00, 0x00,  # mov eax, 60
            0x31, 0xFF,                    # xor edi, edi
            0x0F, 0x05,                    # syscall
        ]
    )
    text_off = 64 + 56
    body = code + noise + phrase + b"\x00" + noise[::-1]
    load_end = text_off + len(body)
    entry = 0x400000 + text_off
    ident = b"\x7fELF" + bytes([2, 1, 1, 0]) + bytes(8)
    eh = struct.pack(
        "<16sHHIQQQIHHHHHH",
        ident,
        2,          # ET_EXEC
        62,         # EM_X86_64
        1,
        entry,
        64,         # e_phoff
        0,          # no section headers (avoids .text / .rodata names)
        0,
        64,
        56,
        1,
        0,
        0,
        0,
    )
    ph = struct.pack(
        "<IIQQQQQQ",
        1,          # PT_LOAD
        5,          # R+X
        0,
        0x400000,
        0x400000,
        load_end,
        load_end,
        0x1000,
    )
    blob = eh + ph + body
    if blob.count(phrase) != 1:
        raise SystemExit("gate phrase missing or duplicated")
    # Letter runs of length 4+ must be only the words inside the flag.
    allowed = {w for w in b"pass the baton".split() if len(w) >= 4}
    found = set(re.findall(rb"[A-Za-z]{4,}", blob))
    if found != allowed:
        raise SystemExit(f"unexpected english in gate: {sorted(found)}")
    out = CHALLENGES / "gate" / "public" / "bin" / "gate"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(blob)
    print("wrote", out, "phrase", phrase.decode())


FLAG_BINARY = "TR{eight_bits}"
FLAG_MORSE = "TR{clear_signal}"
FLAG_SPACE = "TR{trailing_off}"
FLAG_ZERO = "TR{thin_space}"
FLAG_LSB = "TR{low_bits}"
FLAG_BROKEN = "TR{magic_bytes}"
FLAG_LOG = "TR{marigold}"
FLAG_PATCH = "TR{flip_the_check}"
FLAG_IDENTIFY = "TR{compass}"

MORSE = {
    "A": ".-",
    "B": "-...",
    "C": "-.-.",
    "D": "-..",
    "E": ".",
    "F": "..-.",
    "G": "--.",
    "H": "....",
    "I": "..",
    "J": ".---",
    "K": "-.-",
    "L": ".-..",
    "M": "--",
    "N": "-.",
    "O": "---",
    "P": ".--.",
    "Q": "--.-",
    "R": ".-.",
    "S": "...",
    "T": "-",
    "U": "..-",
    "V": "...-",
    "W": ".--",
    "X": "-..-",
    "Y": "-.--",
    "Z": "--..",
}

LETTER_LINES = [
    "Hello from the night desk.",
    "The south gate was quiet.",
    "I walked the fence once.",
    "Nothing moved in the yard.",
    "The lamp by the dock is out.",
    "I left a note for the next shift.",
    "Please check the lock.",
    "The key is on the hook.",
    "Weather is clear and cold.",
    "Radios are charged.",
    "No visitors after dark.",
    "I will be back at dawn.",
    "Thanks for covering.",
    "See you in the morning.",
    "Keep the log updated.",
    "All quiet otherwise.",
]

MEMO = (
    "Please file the dock report before the next shift starts. "
    "The lamp on the south pier is still out, and the spare bulbs are in the top drawer. "
    "Leave the radio on channel two. I will close the gate when I get back from the yard."
)


def _staff_flag(folder: str, flag: str) -> None:
    private = CHALLENGES / folder / "private"
    private.mkdir(parents=True, exist_ok=True)
    (private / "flag.txt").write_bytes(flag.encode("ascii") + b"\n")


def _public(folder: str) -> Path:
    path = CHALLENGES / folder / "public"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _bits(text: str) -> str:
    return "".join(f"{ord(ch):08b}" for ch in text)


def _morse_line(message: str) -> str:
    words = [" ".join(MORSE[ch] for ch in word) for word in message.split(" ")]
    return " / ".join(words)


def _png_chunk(tag: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(tag + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)


def _png_bytes(width: int, height: int, rgb: bytes) -> bytes:
    stride = width * 3
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        raw.extend(rgb[y * stride : (y + 1) * stride])
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + _png_chunk(b"IEND", b"")
    )


def _embed_lsb(rgb: bytearray, message: bytes) -> None:
    bits: list[int] = []
    for byte in message + b"\x00":
        for shift in range(7, -1, -1):
            bits.append((byte >> shift) & 1)
    if len(bits) > len(rgb):
        raise SystemExit("lsb image is too small for the flag")
    for i, bit in enumerate(bits):
        rgb[i] = (rgb[i] & 0xFE) | bit
    for i in range(len(bits), len(rgb)):
        rgb[i] &= 0xFE


def _write_broken_png() -> None:
    """PNG with a compressed comment, then the 8-byte signature zeroed."""
    width, height = 32, 32
    rng = random.Random(8)
    rgb = bytes(rng.getrandbits(8) for _ in range(width * height * 3))
    stride = width * 3
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        raw.extend(rgb[y * stride : (y + 1) * stride])
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    ztxt = b"Comment\x00\x00" + zlib.compress(FLAG_BROKEN.encode("latin-1"), 9)
    png = (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"zTXt", ztxt)
        + _png_chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + _png_chunk(b"IEND", b"")
    )
    broken = b"\x00" * 8 + png[8:]
    if FLAG_BROKEN.encode("ascii") in broken or b"TR{" in broken:
        raise SystemExit("broken png still contains the flag")
    if broken[:8] != b"\x00" * 8 or png[8:16] != broken[8:16]:
        raise SystemExit("broken png header was not the only change")
    (_public("broken_png") / "broken.png").write_bytes(broken)
    _staff_flag("broken_png", FLAG_BROKEN)


def _write_binary() -> None:
    text = _bits(FLAG_BINARY) + "\n"
    (_public("binary") / "bits.txt").write_bytes(text.encode("ascii"))
    _staff_flag("binary", FLAG_BINARY)


def _write_morse() -> None:
    message = FLAG_MORSE[3:-1].replace("_", " ").upper()
    line = _morse_line(message)
    if line != "-.-. .-.. . .- .-. / ... .. --. -. .- .-..":
        raise SystemExit(f"morse table drifted: {line}")
    (_public("morse") / "signal.txt").write_bytes(line.encode("ascii") + b"\n")
    _staff_flag("morse", FLAG_MORSE)


def _write_whitespace() -> None:
    if len(LETTER_LINES) != len(FLAG_SPACE):
        raise SystemExit("whitespace letter needs one line per flag character")
    out: list[str] = []
    for visible, ch in zip(LETTER_LINES, FLAG_SPACE):
        if not visible or visible[-1] in " \t":
            raise SystemExit(f"visible line ends with whitespace: {visible!r}")
        hidden = "".join("\t" if bit == "1" else " " for bit in f"{ord(ch):08b}")
        out.append(visible + hidden)
    (_public("whitespace") / "letter.txt").write_bytes(("\n".join(out) + "\n").encode("ascii"))
    _staff_flag("whitespace", FLAG_SPACE)


def _write_zero_width() -> None:
    bits = _bits(FLAG_ZERO)
    if len(MEMO) < len(bits):
        raise SystemExit("memo is shorter than the zero-width bit stream")
    zw = {"0": "\u200b", "1": "\u200c"}
    chars: list[str] = []
    for i, ch in enumerate(MEMO):
        chars.append(ch)
        if i < len(bits):
            chars.append(zw[bits[i]])
    (_public("zero_width") / "memo.txt").write_bytes(("".join(chars) + "\n").encode("utf-8"))
    _staff_flag("zero_width", FLAG_ZERO)


def _write_lsb() -> None:
    width, height = 160, 100
    flag = FLAG_LSB.encode("ascii")
    png = b""
    for seed in range(2026, 2066):
        rng = random.Random(seed)
        rgb = bytearray(rng.getrandbits(8) for _ in range(width * height * 3))
        _embed_lsb(rgb, flag)
        png = _png_bytes(width, height, bytes(rgb))
        if flag not in png and b"TR{" not in png:
            break
    else:
        raise SystemExit("could not build an lsb png that hides the flag bytes")
    (_public("lsb") / "postcard.png").write_bytes(png)
    _staff_flag("lsb", FLAG_LSB)


def _write_log() -> None:
    rng = random.Random(26)
    users = [
        "alice", "bob", "carol", "dave", "erin", "frank", "grace", "hector",
        "iris", "jules", "ken", "lena", "marco", "nora", "omar", "priya",
        "quinn", "rosa", "sam", "tina", "ulrich", "vera", "wes", "xena", "yuri", "zoe",
    ]
    paths = [
        "/index", "/health", "/static/app.js", "/login", "/home",
        "/api/status", "/logout", "/search", "/about", "/favicon.ico",
    ]
    statuses = [200, 200, 200, 204, 301, 302, 404]
    seconds = 8 * 3600
    lines: list[str] = []
    for _ in range(1600):
        seconds += rng.randint(8, 35)
        day, rem = divmod(seconds, 86400)
        hh, rem = divmod(rem, 3600)
        mm, ss = divmod(rem, 60)
        stamp = f"2026-04-{11 + day:02d}T{hh:02d}:{mm:02d}:{ss:02d}Z"
        ip = f"10.{rng.randint(0, 31)}.{rng.randint(0, 31)}.{rng.randint(1, 254)}"
        lines.append(
            f"{stamp} {rng.choice(users)} {ip} GET {rng.choice(paths)} {rng.choice(statuses)}"
        )

    def rewrite(index: int, user: str, ip: str, path: str, status: int) -> None:
        stamp = lines[index].split()[0]
        lines[index] = f"{stamp} {user} {ip} GET {path} {status}"

    success_at = 1042
    for index in range(80, 1560, 37):
        if index == success_at:
            continue
        rewrite(index, rng.choice(users), "10.8.8.8", "/admin", (401, 403, 404, 302)[index % 4])
    for index in (220, 450, 770, 1100, 1360):
        rewrite(index, rng.choice(users), "10.8.8.9", "/admin/", 403)
    for index in (640, 980, 1410):
        rewrite(index, rng.choice(users), "10.8.8.10", "/administrator", 200)
    rewrite(success_at, "marigold", "10.4.4.19", "/admin", 200)

    exact = [line for line in lines if line.split()[4:] == ["/admin", "200"]]
    if exact != [lines[success_at]] or lines[success_at].split()[1] != "marigold":
        raise SystemExit("log hunt does not have exactly one /admin 200")
    if sum("marigold" in line for line in lines) != 1:
        raise SystemExit("marigold appears more than once")
    (_public("log_hunt") / "access.log").write_bytes(("\n".join(lines) + "\n").encode("ascii"))
    _staff_flag("log_hunt", FLAG_LOG)


def _write_patch() -> None:
    raw = [ord(ch) ^ 88 for ch in FLAG_PATCH]
    if "".join(chr(n ^ 88) for n in raw) != FLAG_PATCH:
        raise SystemExit("patch xor round-trip failed")
    body = [
        "#!/usr/bin/env python3",
        '"""Pin check. The flag prints when the pin is accepted."""',
        "import sys",
        "",
        "",
        "def allowed(pin: str) -> bool:",
        '    if pin == "2468":',
        "        return False",
        "    return False",
        "",
        "",
        "def reveal() -> str:",
        "    raw = [",
        "        " + ", ".join(str(n) for n in raw),
        "    ]",
        "    return \"\".join(chr(n ^ 88) for n in raw)",
        "",
        "",
        "def main() -> None:",
        "    if len(sys.argv) != 2:",
        '        print("usage: python3 check.py <pin>")',
        "        return",
        "    if allowed(sys.argv[1]):",
        "        print(reveal())",
        "    else:",
        '        print("denied")',
        "",
        "",
        'if __name__ == "__main__":',
        "    main()",
        "",
    ]
    text = "\n".join(body)
    if FLAG_PATCH.encode("ascii") in text.encode("ascii"):
        raise SystemExit("patch source contains the flag")
    (_public("patch_it") / "check.py").write_bytes(text.encode("ascii"))
    _staff_flag("patch_it", FLAG_PATCH)


def _write_identify() -> None:
    password = FLAG_IDENTIFY[3:-1]
    words = [
        "birch",
        "cobalt",
        "fiddle",
        "granite",
        "juniper",
        "compass",
        "mosaic",
        "nutmeg",
        "prairie",
        "ripple",
        "thimble",
        "willow",
    ]
    if password not in words or words.count(password) != 1:
        raise SystemExit("identify wordlist is missing the password")
    digest = hashlib.sha1(password.encode("ascii")).hexdigest()
    if len(digest) != 40:
        raise SystemExit("identify hash is not SHA-1 length")
    public = _public("identify")
    (public / "hash.txt").write_bytes(digest.encode("ascii") + b"\n")
    (public / "wordlist.txt").write_bytes(("\n".join(words) + "\n").encode("ascii"))
    _staff_flag("identify", FLAG_IDENTIFY)


def write_extra_challenges() -> None:
    _write_binary()
    _write_morse()
    _write_whitespace()
    _write_zero_width()
    _write_lsb()
    _write_broken_png()
    _write_log()
    _write_patch()
    _write_identify()
    print(
        "wrote extra challenges:",
        FLAG_BINARY,
        FLAG_MORSE,
        FLAG_SPACE,
        FLAG_ZERO,
        FLAG_LSB,
        FLAG_BROKEN,
        FLAG_LOG,
        FLAG_PATCH,
        FLAG_IDENTIFY,
    )


def main() -> None:
    write_extra_challenges()


if __name__ == "__main__":
    main()
