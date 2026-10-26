# Broken Check — writeup

**Flag:** `TR{418c01e89060}`  
**Points:** 300  
**Skills:** reading buggy code, deriving the intended token

## Intent

`PASSWORD = "baton"` but the compare uses `PASSWORD[1:]` (`aton`). Running the script with `aton` prints a **different** derived token that does **not** score. Intended solve: read `token_for`, hash the **real** password, wrap it. Decoy comment `TR{nope_read_the_prompt}` is junk.

## Solve

1. `cat check.py`.
2. Real password is `baton`. Token format is `TR{` + `sha256(password)[:12]` + `}`.
3. `sha256 baton` → digest starts with `418c01e89060`.
4. Submit `TR{418c01e89060}`.

Alternate: mentally fix the bug (`guess == PASSWORD`), then know `python check.py baton` would print the same — you still don’t need a working edit if you hash yourself.

## Common traps

- `python check.py aton` and submitting that output
- Submitting the decoy `TR{nope_read_the_prompt}`
- Hashing `aton` or `PASSWORD[1:]` on purpose
