# Bootstrap installer for the launcher-managed Employee Monitor agent.
# Windows counterpart to installer/install.sh.
#
# Usage (PowerShell):
#   .\install.ps1 `
#     -Launcher 'C:\path\to\EmployeeMonitor-windows-amd64.exe' `
#     -Agent    'C:\path\to\EmployeeMonitorAgent-1.2.0-windows-amd64.zip' `
#     -Version  '1.2.0'
#
# Layout produced:
#   %LOCALAPPDATA%\EmployeeMonitor\
#     EmployeeMonitor.exe              (launcher)
#     bin\<version>\...                (agent archive extracted here)
#
# Then runs the launcher in the foreground for first-time setup. After
# successful login the agent registers the autostart Run-key entry
# pointing at the launcher binary (see agent\autostart.py).

[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$Launcher,
    [Parameter(Mandatory)][string]$Agent,
    [Parameter(Mandatory)][string]$Version
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path -LiteralPath $Launcher)) {
    Write-Error "Launcher not found: $Launcher"
    exit 1
}
if (-not (Test-Path -LiteralPath $Agent)) {
    Write-Error "Agent archive not found: $Agent"
    exit 1
}

# Resolve install dir. EMPLOYEE_MONITOR_HOME wins for testing; otherwise
# %LOCALAPPDATA%\EmployeeMonitor matches agent\paths.py and the launcher.
$installDir = $env:EMPLOYEE_MONITOR_HOME
if (-not $installDir) {
    $installDir = Join-Path $env:LOCALAPPDATA 'EmployeeMonitor'
}
$launcherDst = Join-Path $installDir 'EmployeeMonitor.exe'
$binDir = Join-Path $installDir "bin\$Version"
$expectedAgent = Join-Path $binDir 'EmployeeMonitorAgent.exe'

Write-Host "install_dir: $installDir"

New-Item -ItemType Directory -Force -Path $binDir | Out-Null

Write-Host "Installing launcher -> $launcherDst"
Copy-Item -Force -LiteralPath $Launcher -Destination $launcherDst

Write-Host "Extracting agent -> $binDir"
# Force overwrite — re-installs should replace, not append.
Expand-Archive -Force -LiteralPath $Agent -DestinationPath $binDir

if (-not (Test-Path -LiteralPath $expectedAgent)) {
    Write-Error @"
Agent binary missing at $expectedAgent.
The archive root should contain EmployeeMonitorAgent.exe + _internal\
directly (see agent\build.sh).
"@
    exit 1
}

Write-Host ""
Write-Host "Installed v$Version at $installDir" -ForegroundColor Green
Write-Host ""
Write-Host "Layout:"
Get-ChildItem -Path $installDir -Directory -Depth 2 |
    Select-Object FullName | Format-Table -AutoSize | Out-String | Write-Host

Write-Host "Launching the agent for first-time setup..." -ForegroundColor Cyan
Write-Host "(The launcher will spawn the agent; first run will prompt for login.)"
# Foreground so the user sees any startup errors immediately. Background
# auto-start kicks in next login via the Run key the agent writes after
# successful auth.
& $launcherDst
