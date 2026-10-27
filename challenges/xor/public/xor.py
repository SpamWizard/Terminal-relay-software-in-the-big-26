import sys
from pathlib import Path

cipher = bytes.fromhex(Path("cipher.hex").read_text())
if len(sys.argv) != 2:
    print("usage: python3 xor.py <hex byte>")
    print("example: python3 xor.py 41")
    raise SystemExit(1)

key = int(sys.argv[1], 16) & 0xFF
print(bytes(byte ^ key for byte in cipher).decode("latin-1"))
