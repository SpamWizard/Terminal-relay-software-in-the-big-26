# Wrong Salt — writeup

**Flag:** `TR{salt_file_wins}`

## Solve
1. Read check.py — `REAL_SALT = "desk"` (script prints a hash decoy with `ops`)
2. `cat salts/desk.txt` → `TR{salt_file_wins}`
3. Do not submit the printed hash token or salts/ops.txt
