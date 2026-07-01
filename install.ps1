# Claude Fleet installer (Windows) — registers the fleet hook on every relevant
# Claude Code event by merging into %USERPROFILE%\.claude\settings.json.
#
#   powershell -ExecutionPolicy Bypass -File install.ps1              # install
#   powershell -ExecutionPolicy Bypass -File install.ps1 -Uninstall   # remove
param([switch]$Uninstall)

$ErrorActionPreference = "Stop"
$dir      = Split-Path -Parent $MyInvocation.MyCommand.Path
$settings = Join-Path $env:USERPROFILE ".claude\settings.json"
$hookPath = Join-Path $dir "fleet_hook.py"
$cmd      = "python `"$hookPath`""
$events   = @("PreToolUse","PostToolUse","UserPromptSubmit","Notification","SessionStart","Stop","SubagentStop")

# Write UTF-8 WITHOUT BOM — strict JSON parsers (Node's JSON.parse, used by
# Claude Code) reject a leading BOM. Set-Content -Encoding UTF8 adds one on
# Windows PowerShell 5.1, so write bytes directly instead.
function Write-JsonNoBom($path, $obj) {
    $json = $obj | ConvertTo-Json -Depth 20
    [System.IO.File]::WriteAllText($path, $json, (New-Object System.Text.UTF8Encoding($false)))
}

New-Item -ItemType Directory -Force -Path (Split-Path $settings) | Out-Null
if (-not (Test-Path $settings)) {
    [System.IO.File]::WriteAllText($settings, "{}", (New-Object System.Text.UTF8Encoding($false)))
}
Copy-Item $settings "$settings.fleet-bak.$([int](Get-Date -UFormat %s))"

$data = Get-Content -Raw $settings | ConvertFrom-Json
if ($null -eq $data) { $data = [pscustomobject]@{} }        # empty/"null" file
if (-not $data.PSObject.Properties["hooks"] -or $null -eq $data.hooks) {
    $data | Add-Member -NotePropertyName hooks -NotePropertyValue ([pscustomobject]@{}) -Force
}
$hooks = $data.hooks

function Get-Blocks($ev) {
    if (-not $hooks.$ev) { $hooks | Add-Member -NotePropertyName $ev -NotePropertyValue @() -Force }
    return ,@($hooks.$ev)
}

if ($Uninstall) {
    foreach ($ev in @($hooks.PSObject.Properties.Name)) {
        $kept = @()
        foreach ($b in @($hooks.$ev)) {
            $b.hooks = @($b.hooks | Where-Object { $_.command -notlike "*fleet_hook.py*" })
            if ($b.hooks.Count -gt 0) { $kept += $b }
        }
        if ($kept.Count -gt 0) { $hooks.$ev = $kept } else { $hooks.PSObject.Properties.Remove($ev) }
    }
    Write-JsonNoBom $settings $data
    Write-Host "uninstalled fleet hooks. backup: $settings.fleet-bak.*"
    exit 0
}

$added = @()
foreach ($ev in $events) {
    $blocks = Get-Blocks $ev
    $present = $false
    foreach ($b in $blocks) {
        foreach ($h in @($b.hooks)) { if ($h.command -like "*fleet_hook.py*") { $present = $true } }
    }
    if (-not $present) {
        $hooks.$ev = @($blocks + @([pscustomobject]@{ hooks = @([pscustomobject]@{ type = "command"; command = $cmd }) }))
        $added += $ev
    }
}
Write-JsonNoBom $settings $data
if ($added.Count -gt 0) { Write-Host "added fleet hook to: $($added -join ', ')" } else { Write-Host "(already installed)" }
Write-Host ""
Write-Host "Done. New Claude sessions are tracked. Run the dashboard: fleet.exe"
