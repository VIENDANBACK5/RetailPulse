param([switch]$SkipHistorical, [switch]$WithAirflow, [switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$projectDirectory = Split-Path -Parent $PSScriptRoot
$startup = @{ WithLake = $true; NoBrowser = [bool]$NoBrowser }
if ($WithAirflow) { $startup.WithAirflow = $true }
if (!$SkipHistorical) { $startup.DownloadData = $true; $startup.RunETL = $true; $startup.RunMining = $true }
& (Join-Path $projectDirectory 'START_RETAILPULSE.ps1') @startup
if ($SkipHistorical) {
    python -m src.etl.pipeline --sources app api
    if ($LASTEXITCODE -ne 0) { throw 'Operational ETL failed; inspect its run registry.' }
}
python (Join-Path $projectDirectory 'scripts/prepare_dashboard.py')
if ($LASTEXITCODE -ne 0) { throw 'Dashboard SQL preparation failed.' }
Write-Host 'Primary portal: http://127.0.0.1:8010/frontend/index.html'
Write-Host 'Analytics dashboard: http://127.0.0.1:8001/frontend/dashboard.html'
