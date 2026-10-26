# Stego Tail — writeup

**Flag:** `TR{stego_found}`  
**Points:** 250

## Solve

1. `cat note.txt` — XOR key decimal 66; result is a path.
2. After IEND, XOR trailer → `cache/tail_note.txt`.
3. `cat cache/tail_note.txt` → `TR{stego_found}`.
