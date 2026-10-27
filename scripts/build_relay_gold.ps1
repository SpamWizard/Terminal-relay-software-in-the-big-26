# Build images/relay-gold.vhdx from Kali Linux. Golden parent for team linked clones.
# Prerequisites: WSL2, Kali WSL installed once, New-VHD (Hyper-V PowerShell tools).
# Run from an elevated PowerShell if feature enables are still pending.
#
# -SeedOnly refreshes an existing golden image (packages + /challenges) without
# re-exporting Kali. Team disks already cloned stay on the old image until reset.
param(
    [switch]$SeedOnly
)
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

if ($SeedOnly) {
    if (-not (Test-Path $Gold)) {
        throw "Golden image missing: $Gold. Run this script once without -SeedOnly."
    }
    Write-Host "SeedOnly: copying the existing golden image (no Kali re-export)."
    wsl.exe --shutdown
    Start-Sleep -Seconds 2
    $workVhdx = Join-Path $WorkDir "ext4.vhdx"
    if (Test-Path $workVhdx) {
        attrib -R $workVhdx 2>$null
        Remove-Item -Force $workVhdx
    }
    Copy-Item -Force $Gold $workVhdx
    attrib -R $workVhdx 2>$null
    Write-Host "Importing build distro $WorkDistro in place ..."
    wsl.exe --import-in-place $WorkDistro $workVhdx
    if ($LASTEXITCODE -ne 0) { throw "import-in-place failed for $WorkDistro" }
} else {
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
}

Write-Host "Configuring player user, sudo apt, wsl.conf (network open for apt) ..."
$setup = @'
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
# Kali already ships a full toolbox; keep apt working for anything extra.
apt-get update
apt-get install -y sudo ca-certificates steghide exif libimage-exiftool-perl john hashcat zip unzip xxd binutils file openssl python3
id -u player >/dev/null 2>&1 || useradd -m -s /bin/bash player
# john often lands in /usr/sbin, which a player login shell may not search.
if [ -x /usr/sbin/john ] && [ ! -x /usr/local/bin/john ]; then
  ln -sfn /usr/sbin/john /usr/local/bin/john
fi
# Passwordless apt only - players install tools during the match when needed.
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
# Write setup as UTF-8 (no BOM). Do not Copy-Item into \\wsl$\...\tmp —
# Windows often returns Access denied on that sticky path (SeedOnly or not).
# Stream bytes into `cat` so PowerShell never re-encodes the script as UTF-16.
function Send-WslBytes {
    param(
        [Parameter(Mandatory = $true)][string]$Distro,
        [Parameter(Mandatory = $true)][string]$RemotePath,
        [Parameter(Mandatory = $true)][byte[]]$Bytes
    )
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = "wsl.exe"
    $psi.Arguments = "-d $Distro -u root -- bash -c `"mkdir -p `$(dirname '$RemotePath') && cat > '$RemotePath'`""
    $psi.RedirectStandardInput = $true
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    $p = [System.Diagnostics.Process]::Start($psi)
    $p.StandardInput.BaseStream.Write($Bytes, 0, $Bytes.Length)
    $p.StandardInput.Close()
    $stdout = $p.StandardOutput.ReadToEnd()
    $stderr = $p.StandardError.ReadToEnd()
    $p.WaitForExit()
    if ($p.ExitCode -ne 0) {
        throw "failed to write $RemotePath into $Distro (exit $($p.ExitCode)): $stderr$stdout"
    }
}

$setupPath = Join-Path $WorkDir "setup.sh"
$utf8 = New-Object System.Text.UTF8Encoding $false
$setupUnix = ($setup -replace "`r`n", "`n") -replace "`r", "`n"
[System.IO.File]::WriteAllText($setupPath, $setupUnix, $utf8)
Write-Host "Running setup inside $WorkDistro"
wsl.exe -d $WorkDistro -u root -- bash -c "true"
if ($LASTEXITCODE -ne 0) { throw "could not start $WorkDistro" }
Send-WslBytes -Distro $WorkDistro -RemotePath "/tmp/setup.sh" -Bytes ([System.IO.File]::ReadAllBytes($setupPath))
wsl.exe -d $WorkDistro -u root -- bash /tmp/setup.sh
if ($LASTEXITCODE -ne 0) {
    throw "gold setup script failed inside $WorkDistro (exit $LASTEXITCODE)"
}

Write-Host "Copying challenges/*/public into /challenges/<id> ..."
$share = "\\wsl$\$WorkDistro\challenges"
$deadline = (Get-Date).AddSeconds(40)
while (-not (Test-Path $share)) {
    if ((Get-Date) -gt $deadline) { throw "\\wsl$\$WorkDistro\challenges is not reachable" }
    Start-Sleep -Milliseconds 250
}
Get-ChildItem (Join-Path $RepoRoot "challenges") -Directory | ForEach-Object {
    $pub = Join-Path $_.FullName "public"
    if (-not (Test-Path $pub)) { return }
    $id = $_.Name
    $metaPath = Join-Path $_.FullName "challenge.json"
    if (Test-Path $metaPath) {
        $meta = Get-Content -Raw -Path $metaPath | ConvertFrom-Json
        if ($meta.id) { $id = [string]$meta.id }
    }
    if ($id -notmatch '^[A-Za-z0-9_-]+$') { throw "refusing challenge id: $id" }
    $dest = Join-Path $share $id
    if (Test-Path $dest) { Remove-Item -Recurse -Force $dest }
    New-Item -ItemType Directory -Force -Path $dest | Out-Null
    Copy-Item -Path (Join-Path $pub "*") -Destination $dest -Recurse -Force
    Write-Host "  /challenges/$id"
}
wsl.exe -d $WorkDistro -u root -- bash -c "chown -R player:player /challenges"
if ($LASTEXITCODE -ne 0) { throw "chown /challenges failed" }

# Embed the steghide payload if this cover is still the plain JPEG, then
# prove each short challenge actually solves. Clean up so the image does
# not ship a cracked pot file or an extracted flag.
$checkPath = Join-Path $WorkDir "check.sh"
$check = @'
set -euo pipefail
command -v exif >/dev/null
command -v exiftool >/dev/null
command -v hashcat >/dev/null
rm -rf /tmp/relay-check
mkdir -p /tmp/relay-check
if ! steghide extract -sf /challenges/steghide/cover.jpg -p rockme -xf /tmp/relay-check/steg.txt >/tmp/relay-check/steghide-extract.log 2>&1; then
  printf '%s\n' 'TR{hidden_in_the_jpeg}' > /tmp/relay-check/payload.txt
  steghide embed -cf /challenges/steghide/cover.jpg -ef /tmp/relay-check/payload.txt -p rockme -f </dev/null
  steghide extract -sf /challenges/steghide/cover.jpg -p rockme -xf /tmp/relay-check/steg.txt </dev/null
fi
grep -qx 'TR{hidden_in_the_jpeg}' /tmp/relay-check/steg.txt
python3 - <<'PY'
import base64, codecs, pathlib
photo = pathlib.Path("/challenges/photo_note/photo.jpg").read_bytes()
start = photo.find(b"\xff\xfe")
length = int.from_bytes(photo[start + 2:start + 4], "big")
comment = photo[start + 4:start + 2 + length]
assert base64.b64decode(comment) == b"TR{comment_section}", comment
secret = pathlib.Path("/challenges/unwrap/secret.txt").read_text().strip()
layer = bytes.fromhex(base64.b64decode(secret).decode())
assert codecs.decode(layer.decode(), "rot13") == "TR{three_layers}"
PY
unzip -P anthem -o /challenges/anthem/anthem.mp3 -d /tmp/relay-check/anthem >/tmp/relay-check/unzip.log
grep -qx 'TR{not_an_mp3}' /tmp/relay-check/anthem/flag.txt
cp /challenges/wordlist/hash.txt /challenges/wordlist/wordlist.txt /tmp/relay-check/
john --pot=/tmp/relay-check/john.pot --format=raw-md5 --wordlist=/tmp/relay-check/wordlist.txt /tmp/relay-check/hash.txt
john --pot=/tmp/relay-check/john.pot --show --format=raw-md5 /tmp/relay-check/hash.txt | grep -q lantern
python3 /challenges/crackme/crackme.py rockme | grep -qx correct
grep -aqo 'TR{pass the baton}' /challenges/gate/bin/gate
test "$(grep -aoE '[A-Za-z]{4,}' /challenges/gate/bin/gate | sort -u | paste -sd' ')" = "baton pass"
rm -rf /tmp/relay-check /root/.john /home/player/.john
find /challenges \( -name '*.pot' -o -name '*.rec' -o -name 'john.log' -o -name '*.john' \) -delete
chown -R player:player /challenges
'@
$checkUnix = ($check -replace "`r`n", "`n") -replace "`r", "`n"
[System.IO.File]::WriteAllText($checkPath, $checkUnix, $utf8)
Send-WslBytes -Distro $WorkDistro -RemotePath "/tmp/check.sh" -Bytes ([System.IO.File]::ReadAllBytes($checkPath))
Write-Host "Checking that each short challenge solves ..."
wsl.exe -d $WorkDistro -u root -- bash /tmp/check.sh
if ($LASTEXITCODE -ne 0) { throw "challenge check failed inside $WorkDistro" }
Copy-Item -Force "\\wsl$\$WorkDistro\challenges\steghide\cover.jpg" (Join-Path $RepoRoot "challenges\steghide\public\cover.jpg")

Write-Host "Exporting configured disk to $Gold ..."
wsl.exe --shutdown
Start-Sleep -Seconds 2
$buildVhdx = Get-ChildItem -Path $WorkDir -Filter "ext4.vhdx" -Recurse -ErrorAction SilentlyContinue |
    Select-Object -First 1
if (-not $buildVhdx) { throw "build ext4.vhdx not found under $WorkDir" }

# Copy aside first so a failed copy cannot delete the only golden image.
$goldNew = "$Gold.new"
Copy-Item -Force $buildVhdx.FullName $goldNew
if (Test-Path $Gold) {
    # WSL cannot mount a ReadOnly VHDX (E_ACCESSDENIED). Keep gold writable on disk;
    # never wsl --import / --import-in-place this file itself.
    attrib -R $Gold 2>$null
    Remove-Item -Force $Gold
}
Move-Item -Force $goldNew $Gold
attrib -R $Gold 2>$null

Write-Host "Unregistering build distro (keeps $Gold) ..."
wsl.exe --unregister $WorkDistro | Out-Null
Remove-Item -Recurse -Force $WorkDir -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "Done. Kali golden parent: $Gold"
Write-Host "IMPORTANT: Do not mark this VHDX ReadOnly - WSL will refuse to attach clones."
Write-Host "Never register the gold file with wsl. Only team children get import-in-place."
Write-Host "Team clones: New-VHD -ParentPath images\relay-gold.vhdx -Differencing ..."
