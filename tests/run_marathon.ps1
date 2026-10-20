# Detached hour-scale test marathon. Safe to close the IDE shell.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$env:RELAY_MARATHON_SECONDS = if ($env:RELAY_MARATHON_SECONDS) { $env:RELAY_MARATHON_SECONDS } else { "3300" }
$env:PYTHONUNBUFFERED = "1"
$env:PYTHONPATH = "src"

$log = Join-Path $PSScriptRoot "_marathon_run.log"
$started = Get-Date -Format o
"Marathon started $started  seconds=$($env:RELAY_MARATHON_SECONDS)" | Set-Content -Path $log -Encoding utf8

# cmd redirect keeps UTF-8; PowerShell *>> writes UTF-16.
$cmd = "python -u -m pytest tests/ -o addopts= -m `"marathon or not marathon`" -v --tb=line -s >> `"$log`" 2>&1"
cmd.exe /c $cmd
$code = $LASTEXITCODE
"Marathon finished $(Get-Date -Format o) exit=$code" | Add-Content -Path $log -Encoding utf8
exit $code
