# WSL desk (Kali linked clones)

Desk challenges run a real bash inside a private copy of a **Kali Linux** golden WSL2 disk. The desk terminal is a real TTY (ConPTY) — `nano`, `vim`, `less`, and interactive `apt` work like a normal Linux box. Baton lock stops keyboard input; the shell stays up.

## Operator setup (once per event PC)

1. Install WSL2 and reboot if Windows asks.
2. Install Kali and finish first-time setup:

```powershell
wsl --install -d kali-linux
wsl -d kali-linux
# create user if asked, then: exit
```

3. Enable linked clones: `Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V-Management-PowerShell -All` (reboot if asked). Confirm with `Get-Command New-VHD`.
4. Build the golden parent (never register this file with WSL after teams exist):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_relay_gold.ps1
```

That writes `images/relay-gold.vhdx` (Kali exports are large — several GB; expect a long first build).

Do **not** mark that VHDX ReadOnly — WSL will fail with `Access is denied` when attaching team clones. Protect it by never registering the gold file with `wsl`; only team children use `import-in-place`.

Network stays up so players can `sudo apt install …` during a desk challenge. Kali already ships a full toolbox; apt is for extras. The gold build also installs `steghide`, `exiftool`, `john`, `hashcat`, `zip`, `unzip`, `xxd`, and `binutils`, and copies every `challenges/*/public` tree to `/challenges/<id>`. Player sudo is limited to `apt` / `apt-get` / `dpkg` (passwordless).

To refresh an existing `images/relay-gold.vhdx` without re-exporting Kali:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_relay_gold.ps1 -SeedOnly
```

That installs those packages, copies the challenge trees, and replaces the golden VHDX. Existing team disks keep their old filesystems until `relay reset`.

Your everyday `Ubuntu` WSL distro (if any) is left alone — only Kali is exported into gold.

## Per team

On first start of a team name, the app:

1. Tries a linked (differencing) VHDX clone of `images\relay-gold.vhdx`
2. If WSL refuses the parent chain (common: `0xc03a0016`), falls back to a **full copy** of the gold disk (~1 GB, once per team)
3. `wsl --import-in-place relay-<slug> …\ext4.vhdx`
4. Opens one long-lived `bash` as user `player`
5. Copies each challenge’s `public/` into `/challenges/<id>/` the first time that challenge opens

First start of a team can take a minute when it has to full-copy. Later resumes reuse the same disk.

`relay reset` unregisters every `relay-*` distro (deletes child disks) and clears `data/wsl/`. It never deletes `images/relay-gold.vhdx`.

## Rules

- Do not move or rewrite `relay-gold.vhdx` after the first clone. Rebuild gold ⇒ discard every team disk.
- Do not `wsl --unregister` against the golden file. It is not registered; only team children are.
- `private/` is never copied into the distro.
