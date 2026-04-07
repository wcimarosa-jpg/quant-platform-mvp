# Sprint loop runner (PowerShell wrapper)
# Usage: .\scripts\run_sprint_loop.ps1 [--claim]
param([switch]$claim)

$scriptPath = Join-Path $PSScriptRoot "run_sprint_loop.py"
if ($claim) {
    python $scriptPath --claim
} else {
    python $scriptPath
}
