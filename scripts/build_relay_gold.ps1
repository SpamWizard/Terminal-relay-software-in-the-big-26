# Build images/relay-gold.vhdx from Kali Linux — read-only parent for team linked clones.
# Prerequisites: WSL2, Kali WSL installed once, New-VHD (Hyper-V PowerShell tools).
# Run from an elevated PowerShell if feature enables are still pending.
#
# Install Kali first (once):
#   wsl --install -d kali-linux
#   wsl -d kali-linux   # finish first-time setup, then exit

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$Images = Join-Path $RepoRoot "images"
$Gold = Join-Path $Images "relay-gold.vhdx"
$WorkDistro = "relay-gold-build"
$WorkDir = Join-Path $RepoRoot "data\wsl\_gold_build"
$StockPattern = '(?i)^kali'

Write-Host "Repo: $RepoRoot"
Write-Host "Golden image base: Kali Linux"

if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) {
    throw "wsl.exe not found. Install WSL2 first."
}
if (-not (Get-Command New-VHD -ErrorAction SilentlyContinue)) {
    throw "New-VHD not found. Enable Microsoft-Hyper-V-Management-PowerShell (or Hyper-V), then reboot if asked."
}

New-Item -ItemType Directory -Force $Images | Out-Null
New-Item -ItemType Directory -Force $WorkDir | Out-Null

# `wsl -l` prints UTF-16LE; PowerShell often sees NULs between letters.
function Get-WslDistroNames {
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = "wsl.exe"
    $psi.Arguments = "-l -q"
    $psi.RedirectStandardOutput = $true
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    $p = [System.Diagnostics.Process]::Start($psi)
    $ms = New-Object System.IO.MemoryStream
    $p.StandardOutput.BaseStream.CopyTo($ms)
    $p.WaitForExit()
    $raw = $ms.ToArray()
    if ($raw.Length -ge 2 -and $raw[0] -eq 0xFF -and $raw[1] -eq 0xFE) {
        $text = [System.Text.Encoding]::Unicode.GetString($raw, 2, $raw.Length - 2)
    } elseif ($raw.Length -gt 2 -and $raw[1] -eq 0) {
        $text = [System.Text.Encoding]::Unicode.GetString($raw)
    } else {
        $text = [System.Text.Encoding]::UTF8.GetString($raw)
    }
    $names = @()
    foreach ($line in ($text -split "`r?`n")) {
        $name = ($line -replace "`0", "").Trim()
        if ($name) { $names += $name }
    }
    return $names
}

$existing = @(Get-WslDistroNames)
Write-Host ("Installed distros: " + (($existing -join ", ")))

if ($existing -contains $WorkDistro) {
    Write-Host "Unregistering leftover $WorkDistro ..."
    wsl.exe --unregister $WorkDistro | Out-Null
    $existing = @(Get-WslDistroNames)
}

# Prefer exporting from an installed Kali; else install kali-linux.
$stock = $existing | Where-Object { $_ -match $StockPattern } | Select-Object -First 1
if (-not $stock) {
    Write-Host "No Kali distro listed yet; installing kali-linux ..."
    wsl.exe --install -d kali-linux --no-launch
    Write-Host @"

If Kali still needs first-time setup, open another window, run:
  wsl -d kali-linux
Then exit and re-run this script.

"@
    $existing = @(Get-WslDistroNames)
    $stock = $existing | Where-Object { $_ -match $StockPattern } | Select-Object -First 1
    if (-not $stock) {
        throw "No Kali distro found. Run: wsl --install -d kali-linux   then wsl -d kali-linux (finish setup), then re-run this script."
    }
}

Write-Host "Using stock distro: $stock"
Write-Host "Note: Kali exports are large (often several GB). This can take a while."

$Tar = Join-Path $WorkDir "kali-export.tar"
Write-Host "Exporting $stock -> $Tar ..."
wsl.exe --shutdown
wsl.exe --export $stock $Tar
if (-not (Test-Path $Tar)) { throw "export failed" }

Write-Host "Importing build distro $WorkDistro ..."
wsl.exe --import $WorkDistro $WorkDir $Tar --version 2
Remove-Item -Force $Tar -ErrorAction SilentlyContinue

Write-Host "Configuring player user, sudo apt, wsl.conf (network open for apt) ..."
$setup = @'
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
# Kali already ships a full toolbox; keep apt working for anything extra.
apt-get update
apt-get install -y sudo ca-certificates
id -u player >/dev/null 2>&1 || useradd -m -s /bin/bash player
# Passwordless apt only — players install tools during the match when needed.
echo 'player ALL=(root) NOPASSWD: /usr/bin/apt, /usr/bin/apt-get, /usr/bin/dpkg' >/etc/sudoers.d/player-apt
chmod 440 /etc/sudoers.d/player-apt
mkdir -p /challenges
chown player:player /challenges
# Make sure player can use common Kali paths
if [ -d /usr/share/kali-menu ] || true; then
  true
fi
cat >/etc/wsl.conf <<'EOF'
[automount]
enabled = false

[interop]
enabled = false
appendWindowsPath = false

[user]
default = player
EOF
'@
# Write setup as UTF-8 (no BOM). Run via /mnt/c/... while stock automount is still on.
$setupPath = Join-Path $WorkDir "setup.sh"
$utf8 = New-Object System.Text.UTF8Encoding $false
$setupUnix = ($setup -replace "`r`n", "`n") -replace "`r", "`n"
[System.IO.File]::WriteAllText($setupPath, $setupUnix, $utf8)
$full = [System.IO.Path]::GetFullPath($setupPath)
$drive = $full.Substring(0, 1).ToLowerInvariant()
$unixSetup = "/mnt/$drive/" + (($full.Substring(3)) -replace "\\", "/")
Write-Host "Running setup via $unixSetup"
wsl.exe -d $WorkDistro -u root -- bash -c "true" | Out-Null
& wsl.exe -d $WorkDistro -u root -- bash $unixSetup
if ($LASTEXITCODE -ne 0) {
    throw "gold setup script failed inside $WorkDistro (exit $LASTEXITCODE)"
}

Write-Host "Exporting configured disk to $Gold ..."
wsl.exe --shutdown
Start-Sleep -Seconds 2
$buildVhdx = Get-ChildItem -Path $WorkDir -Filter "ext4.vhdx" -Recurse -ErrorAction SilentlyContinue |
    Select-Object -First 1
if (-not $buildVhdx) { throw "build ext4.vhdx not found under $WorkDir" }

if (Test-Path $Gold) {
    # WSL cannot mount a ReadOnly VHDX (E_ACCESSDENIED). Keep gold writable on disk;
    # never wsl --import / --import-in-place this file itself.
    attrib -R $Gold 2>$null
    Remove-Item -Force $Gold
}
Copy-Item -Force $buildVhdx.FullName $Gold
attrib -R $Gold 2>$null

Write-Host "Unregistering build distro (keeps $Gold) ..."
wsl.exe --unregister $WorkDistro | Out-Null
Remove-Item -Recurse -Force $WorkDir -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "Done. Kali golden parent: $Gold"
Write-Host "IMPORTANT: Do not mark this VHDX ReadOnly — WSL will refuse to attach clones."
Write-Host "Never register the gold file with wsl. Only team children get import-in-place."
Write-Host "Team clones: New-VHD -ParentPath images\relay-gold.vhdx -Differencing ..."
