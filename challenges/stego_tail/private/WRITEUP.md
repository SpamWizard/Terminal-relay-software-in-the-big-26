# Stego Tail — writeup

**Flag:** `TR{stego_xor_tail}`  
**Points:** 250  
**Skills:** binary trailer, single-byte XOR

## Intent

`cat logo.png` shows PNG garbage — no readable `TR{`. Note says key is decimal 66. Needs a short python one-liner; natural place for A to find the note and B to run the XOR.

## Solve

1. `cat note.txt` — XOR trailer with **66** (`0x42`).
2. Payload sits after the PNG `IEND` chunk.
3. Example:

```text
python -c "d=open('logo.png','rb').read(); i=d.rfind(b'IEND'); c=d[i+8:].strip(); print(bytes(b^66 for b in c))"
```

4. Prints `TR{stego_xor_tail}` — submit that.

## Common traps

- XOR with ASCII `'66'` or the string `"baton"` instead of integer 66
- XOR-ing the whole file instead of the trailer after `IEND`
- Stopping after seeing binary noise from `cat`
