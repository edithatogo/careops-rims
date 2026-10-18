[CmdletBinding()]
param([switch]$InitializeConductor, [switch]$OpenReport)
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
Push-Location $Root
try {
    if (-not (Test-Path '.git')) { throw 'The complete Git working copy is required. Do not reinitialise or discard its history.' }
    & git status --short
    if ($LASTEXITCODE -ne 0) { throw 'Unable to inspect Git repository.' }
    & python -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { throw 'Unit tests failed.' }
    & python scripts/validate_project.py
    if ($LASTEXITCODE -ne 0) { throw 'Project validation failed.' }
    if ($InitializeConductor) {
        $Lock = Get-Content 'config/dependencies.lock.json' -Raw | ConvertFrom-Json
        & git submodule update --init --recursive -- $Lock.conductor.path
        if ($LASTEXITCODE -ne 0) { throw 'Conductor checkout failed. Project context remains available; do not claim the plugin was installed.' }
        $Actual = (& git -C $Lock.conductor.path rev-parse HEAD).Trim()
        if ($Actual -ne $Lock.conductor.commit) { throw "Conductor revision mismatch: $Actual" }
        Write-Host "Conductor verified at $Actual"
    }
    if ($OpenReport) { Start-Process -FilePath (Join-Path $Root 'powerbi\CHHHS Research Publications.pbip') }
    Write-Host 'Local checks complete. Native Desktop acceptance and tenant deployment are separate gates.'
} finally { Pop-Location }
