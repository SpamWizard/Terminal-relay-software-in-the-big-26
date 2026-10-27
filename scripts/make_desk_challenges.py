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
    """Static ELF64 crackme. Check is xor 0xA7, then add the index.

    Password bytes never appear in the file. objdump -d -M intel shows the loop;
    objdump -s -j .rodata shows the compare table.
    """
    password = b"relay9x"
    table = bytes(((c ^ 0xA7) + i) & 0xFF for i, c in enumerate(password))
    if any(32 <= b < 127 for b in table):
        run = 0
        for b in table:
            run = run + 1 if 32 <= b < 127 else 0
            if run >= 4:
                raise SystemExit("gate table would show up in strings")

    code = bytearray()
    labels: dict[str, int] = {}
    fixups: list[tuple[int, str, int]] = []

    def label(name: str) -> None:
        labels[name] = len(code)

    def emit(*xs: int) -> None:
        code.extend(xs)

    def rel8(name: str) -> None:
        fixups.append((len(code), name, 1))
        emit(0)

    def rel32(name: str) -> None:
        fixups.append((len(code), name, 4))
        emit(0, 0, 0, 0)

    n = len(password)
    label("start")
    emit(0x48, 0x8B, 0x04, 0x24)          # mov rax, [rsp]      ; argc
    emit(0x48, 0x83, 0xF8, 0x02)          # cmp rax, 2
    emit(0x75); rel8("usage")             # jne usage
    emit(0x48, 0x8B, 0x74, 0x24, 0x10)    # mov rsi, [rsp+0x10] ; argv[1]
    emit(0x31, 0xC9)                      # xor ecx, ecx
    emit(0x4C, 0x8D, 0x05); rel32("table")  # lea r8, [rip+table]
    label("loop")
    emit(0x83, 0xF9, n)                   # cmp ecx, len
    emit(0x74); rel8("end")               # je end
    emit(0x8A, 0x04, 0x0E)                # mov al, [rsi+rcx]
    emit(0x84, 0xC0)                      # test al, al
    emit(0x74); rel8("fail")              # jz fail
    emit(0x34, 0xA7)                      # xor al, 0xa7
    emit(0x00, 0xC8)                      # add al, cl
    emit(0x41, 0x3A, 0x04, 0x08)          # cmp al, [r8+rcx]
    emit(0x75); rel8("fail")              # jne fail
    emit(0xFF, 0xC1)                      # inc ecx
    emit(0xEB); rel8("loop")              # jmp loop
    label("end")
    emit(0x80, 0x3C, 0x0E, 0x00)          # cmp byte [rsi+rcx], 0
    emit(0x75); rel8("fail")              # jne fail
    label("ok")
    emit(0xB8, 0x01, 0x00, 0x00, 0x00)    # mov eax, 1          ; write
    emit(0xBF, 0x01, 0x00, 0x00, 0x00)    # mov edi, 1
    emit(0x48, 0x8D, 0x35); rel32("okmsg")
    emit(0xBA, 0x08, 0x00, 0x00, 0x00)    # mov edx, 8          ; "correct\n"
    emit(0x0F, 0x05)                      # syscall
    emit(0xE9); rel32("exit0")
    label("fail")
    emit(0xB8, 0x01, 0x00, 0x00, 0x00)
    emit(0xBF, 0x01, 0x00, 0x00, 0x00)
    emit(0x48, 0x8D, 0x35); rel32("nopemsg")
    emit(0xBA, 0x05, 0x00, 0x00, 0x00)    # "nope\n"
    emit(0x0F, 0x05)
    emit(0xE9); rel32("exit1")
    label("usage")
    emit(0xB8, 0x01, 0x00, 0x00, 0x00)
    emit(0xBF, 0x01, 0x00, 0x00, 0x00)
    emit(0x48, 0x8D, 0x35); rel32("usemsg")
    emit(0xBA, 0x17, 0x00, 0x00, 0x00)    # len("usage: gate <password>\n")
    emit(0x0F, 0x05)
    label("exit1")
    emit(0xB8, 0x3C, 0x00, 0x00, 0x00)    # mov eax, 60         ; exit
    emit(0xBF, 0x01, 0x00, 0x00, 0x00)    # mov edi, 1
    emit(0x0F, 0x05)
    label("exit0")
    emit(0xB8, 0x3C, 0x00, 0x00, 0x00)
    emit(0x31, 0xFF)                      # xor edi, edi
    emit(0x0F, 0x05)

    usemsg = b"usage: gate <password>\n"
    if len(usemsg) != 0x17:
        raise SystemExit(f"usage string length changed: {len(usemsg)}")
    ro = bytearray()
    ro_labels = {
        "table": len(code) + len(ro),
    }
    ro += table
    ro_labels["okmsg"] = len(code) + len(ro)
    ro += b"correct\n"
    ro_labels["nopemsg"] = len(code) + len(ro)
    ro += b"nope\n"
    ro_labels["usemsg"] = len(code) + len(ro)
    ro += usemsg

    for pos, name, size in fixups:
        target = labels[name] if name in labels else ro_labels[name]
        rel = target - (pos + size)
        if size == 1:
            if not -128 <= rel <= 127:
                raise SystemExit(f"rel8 {name} out of range: {rel}")
            code[pos] = rel & 0xFF
        else:
            struct.pack_into("<i", code, pos, rel)

    text = bytes(code)
    rodata = bytes(ro)
    text_off = 64 + 56
    ro_off = text_off + len(text)
    load_end = ro_off + len(rodata)
    shstr = b"\x00.text\x00.rodata\x00.shstrtab\x00"
    shstr_off = load_end
    shoff = (shstr_off + len(shstr) + 7) & ~7
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
        shoff,
        0,
        64,
        56,
        1,
        64,
        4,
        3,          # .shstrtab
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

    def shdr(name: int, typ: int, flags: int, addr: int, off: int, size: int, align: int) -> bytes:
        return struct.pack("<IIQQQQIIQQ", name, typ, flags, addr, off, size, 0, 0, align, 0)

    sections = b"".join(
        [
            shdr(0, 0, 0, 0, 0, 0, 0),
            shdr(1, 1, 6, 0x400000 + text_off, text_off, len(text), 16),
            shdr(7, 1, 2, 0x400000 + ro_off, ro_off, len(rodata), 1),
            shdr(15, 3, 0, 0, shstr_off, len(shstr), 1),
        ]
    )
    blob = eh + ph + text + rodata + shstr
    blob += bytes(shoff - len(blob))
    blob += sections
    if password in blob or b"TR{" in blob:
        raise SystemExit("gate binary leaked the secret")
    if table not in blob:
        raise SystemExit("gate table missing")
    out = CHALLENGES / "gate" / "public" / "bin" / "gate"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(blob)
    print("wrote", out, "table", table.hex())


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
