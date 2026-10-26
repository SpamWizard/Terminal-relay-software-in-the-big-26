# PCAP DNS — writeup

**Flag:** `TR{dns_badge_desk}`

## Solve
1. `grep label dns.log` → badge + ops + local → `badge.ops.local`
2. `grep badge.ops.local inventory.txt` → `TR{dns_badge_desk}`
3. Ignore decoy hosts and `TR{decoy_not_dns}`
