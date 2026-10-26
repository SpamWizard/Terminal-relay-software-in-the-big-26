# WSL desk (Kali linked clones)

Desk challenges run a real bash inside a private copy of a **Kali Linux** golden WSL2 disk. The fullscreen relay window is the only console: each line is written to that bash, and its output is pasted back. Baton lock disables typing; bash stays up.

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

That writes a read-only `images/relay-gold.vhdx` (Kali exports are large — several GB; expect a long first build).

Network stays up so players can `sudo apt install …` during a desk challenge. Kali already ships a full toolbox; apt is for extras. Player sudo is limited to `apt` / `apt-get` / `dpkg` (passwordless).

Your everyday `Ubuntu` WSL distro (if any) is left alone — only Kali is exported into gold.

## Per team

On first start of a team name, the app:

1. `New-VHD -ParentPath images\relay-gold.vhdx -Path data\wsl\<slug>\ext4.vhdx -Differencing`
2. `wsl --import-in-place relay-<slug> …\ext4.vhdx`
3. Opens one long-lived `bash` as user `player`
4. Copies each challenge’s `public/` into `/challenges/<id>/` the first time that challenge opens

`relay reset` unregisters every `relay-*` distro (deletes child disks) and clears `data/wsl/`. It never deletes `images/relay-gold.vhdx`.

## Rules

- Do not move or rewrite `relay-gold.vhdx` after the first clone. Rebuild gold ⇒ discard every team disk.
- Do not `wsl --unregister` against the golden file. It is not registered; only team children are.
- `private/` is never copied into the distro.
