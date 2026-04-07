# Bootstrap script (PowerShell)
# Usage: .\scripts\bootstrap.ps1
param([switch]$SkipNpm)

$scriptPath = Join-Path $PSScriptRoot "bootstrap.py"
if ($SkipNpm) {
    python $scriptPath --skip-npm
} else {
    python $scriptPath
}
