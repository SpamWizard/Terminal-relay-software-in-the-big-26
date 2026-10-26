# PDF EOF — writeup

**Flag:** `TR{pdf_trailer}`

## Solve
1. XOR trailer with 90 → `annex/tail.txt`
2. `cat annex/tail.txt` → `TR{pdf_trailer}`
