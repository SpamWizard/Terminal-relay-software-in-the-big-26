# Broken Check — writeup

**Flag:** `TR{broken_vault}`

## Solve

1. Read `check.py` — `PASSWORD = "baton"`. Running with `aton` prints a hash decoy.
2. `cat vault/baton.txt` → `TR{broken_vault}`.
3. Do not submit the printed hash or `vault/aton.txt`.
