# Bash Crumbs — writeup

**Flag:** `TR{flipper}`  
**Points:** 250  
**Skills:** history forensics, offline hash crack against a tiny wordlist

## Intent

No plaintext password. History shows failed `md5sum` guesses and one stored hash. Wordlist is short enough to grind by hand or with a one-liner — good for yelling “try flipper” across a baton swap.

## Solve

1. `cat history.txt` — find `svc_acct md5=...` (md5 of `flipper`).
2. `cat wordlist.txt` — snack / con themed words.
3. Check candidates with `md5 <word>` until it matches, or:

   `python -c "import hashlib; w=open('wordlist.txt'); h='…'; print([x.strip() for x in w if hashlib.md5(x.strip().encode()).hexdigest()==h])"`

4. Submit `TR{flipper}`.

## Common traps

- Submitting a word they tried in history (`oreo`, `potato`, `baton`) without checking the hash
- Wrapping the md5 itself as the flag
