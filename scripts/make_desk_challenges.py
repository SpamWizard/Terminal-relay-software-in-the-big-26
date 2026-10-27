"""Rebuild the binary/encoded files for the short desk challenges.

Writes challenges/*/public artifacts. Does not run steghide — embed cover.jpg
on a machine that has it:

    steghide embed -cf challenges/steghide/public/cover.jpg \\
        -ef challenges/steghide/private/flag.txt -p rockme -f
"""

from __future__ import annotations

import base64
import codecs
import hashlib
import os
import struct
import subprocess
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


def main() -> None:
    secret = base64.b64encode(codecs.encode(FLAG_UNWRAP, "rot13").encode().hex().encode())
    unwrap = CHALLENGES / "unwrap" / "public" / "secret.txt"
    unwrap.parent.mkdir(parents=True, exist_ok=True)
    unwrap.write_bytes(secret + b"\n")
    digest = hashlib.md5(WORD).hexdigest()
    hash_path = CHALLENGES / "wordlist" / "public" / "hash.txt"
    hash_path.parent.mkdir(parents=True, exist_ok=True)
    hash_path.write_text(digest + "\n", encoding="utf-8")

    cover = CHALLENGES / "steghide" / "public" / "cover.jpg"
    photo = CHALLENGES / "photo_note" / "public" / "photo.jpg"
    _noise_jpeg(cover, 26, 640, 480)
    _noise_jpeg(photo, 90, 480, 320)
    note = base64.b64encode(FLAG_PHOTO).decode("ascii")
    _insert_jpeg_comment(photo, note)

    anthem = CHALLENGES / "anthem" / "public" / "anthem.mp3"
    _write_encrypted_zip(anthem, "flag.txt", FLAG_ANTHEM, b"anthem")
    _write_gate()
    print("wrote", secret.decode(), digest)


if __name__ == "__main__":
    main()
