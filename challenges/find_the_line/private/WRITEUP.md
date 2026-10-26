# Find The Line — writeup

**Flag:** `TR{guest_line_ok}`  
**Points:** 150  
**Skills:** run a challenge tool, read the scan, grep the tree

## Intent

Players must actually run `iwlist` (challenge `bin/iwlist.py`) to see networks — there is no pre-dropped scan dump. Then search the fake laptop for the guest SSID.

## Solve

1. `cat home/ops/sticky.txt` — hint to run `iwlist wlan0 scanning`.
2. `iwlist wlan0 scanning` → guest ESSID **SaintconGuest** (not staff).
3. `grep -r SaintconGuest .` → `etc/NetworkManager/system-connections/guest.nmconnection`.
4. Read that profile → `TR{guest_line_ok}`.

## Common traps

- Staff SSID / staff.nmconnection
- Submitting a random TR{} from syslog
