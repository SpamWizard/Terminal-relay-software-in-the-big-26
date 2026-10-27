# Sync this station with GitHub: pull, reinstall the app, refresh the golden
# Kali disk, then clear team disks so the next team gets the new image.
# Run from a normal PowerShell. Leave the PC on and online until it finishes.
#
#   powershell -ExecutionPolicy Bypass -File C:\relay\scripts\update_station.ps1

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $RepoRoot

$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$VenvPip = Join-Path $RepoRoot ".venv\Scripts\pip.exe"
$Relay = Join-Path $RepoRoot ".venv\Scripts\relay.exe"
$Gold = Join-Path $RepoRoot "images\relay-gold.vhdx"
$Build = Join-Path $RepoRoot "scripts\build_relay_gold.ps1"

Write-Host "=== Station update: $RepoRoot ==="

if (-not (Test-Path $VenvPython)) {
    throw "Missing .venv. Finish the install in the README (step 4) first."
}

Write-Host "`n--- git pull ---"
git pull
if ($LASTEXITCODE -ne 0) {
    throw "git pull failed (exit $LASTEXITCODE). Sign in to GitHub if asked, then run this script again."
}

Write-Host "`n--- pip install ---"
& $VenvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed." }
& $VenvPip install -e ".[dev]"
if ($LASTEXITCODE -ne 0) { throw "pip install failed." }

Write-Host "`n--- golden Kali disk ---"
if (Test-Path $Gold) {
    Write-Host "Refreshing existing gold (SeedOnly)."
    & powershell -ExecutionPolicy Bypass -File $Build -SeedOnly
} else {
    Write-Host "No gold image yet; full build."
    & powershell -ExecutionPolicy Bypass -File $Build
}
if ($LASTEXITCODE -ne 0) { throw "Golden disk build failed." }

Write-Host "`n--- relay reset ---"
& $Relay reset
if ($LASTEXITCODE -ne 0) { throw "relay reset failed." }

Write-Host "`n--- warm standby desk disk ---"
& $Relay warm
if ($LASTEXITCODE -ne 0) { throw "relay warm failed." }

Write-Host "`nDone. Station matches GitHub. Start with:"
Write-Host "  cd C:\relay"
Write-Host "  .\.venv\Scripts\Activate.ps1"
Write-Host "  relay run --fake-device"
Write-Host "Or skip the name screen:  relay quick"
