# Checksum Pick — writeup

**Flag:** `TR{correct_horse}`  
**Matching id:** `CASE-4401` (crc32 `426b7e2c`)

## Solve
1. crc32 each candidates.txt line → `CASE-4401`
2. `grep CASE-4401 casebook.txt` → `TR{correct_horse}`
