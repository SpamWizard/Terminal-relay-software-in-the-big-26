# Find The Line — writeup

**Flag:** `TR{6677ac63}`  
**Points:** 150  
**Skills:** reading a dump, ignoring decoys, hashing

## Intent

Force a handoff-friendly two-step: person A finds the right SSID, person B runs the hash. A decoy ESSID and a fake `TR{...}` punish “submit the first thing that looks like a flag.”

## Solve

1. `cat briefing.txt` — token is `TR{` + first 8 hex of `sha256(SSID)` + `}`.
2. `cat scan.txt` (or `grep ESSID scan.txt`) — several networks.
3. Use **SaintconGuest**, not `SaintconStaff-DoNotUse`, not the `# TR{decoy_not_this}` comment.
4. `sha256 SaintconGuest` → digest starts with `6677ac63`.
5. Submit `TR{6677ac63}`.

## Common traps

- Staff SSID
- Decoy flag in the comment
- Hashing the whole ESSID line including quotes
