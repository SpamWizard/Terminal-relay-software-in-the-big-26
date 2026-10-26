# Bash Crumbs — writeup

**Flag:** `TR{crumbs_service}`  
**Password:** `flipper` (md5 `d22778374cd88052bf19282a2a698eba`)

## Solve

1. History shows target md5; crack against `wordlist.txt` → `flipper`.
2. `grep flipper services.txt` → `TR{crumbs_service}`.
3. Do not submit `TR{flipper}`.
