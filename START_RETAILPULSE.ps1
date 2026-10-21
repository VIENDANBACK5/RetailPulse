param([switch]$DownloadData, [switch]$RunETL, [switch]$RunMining, [switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$rootPath = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $rootPath
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONUTF8 = '1'
$env:PYTHONPATH = $rootPath
function Check-Exit([string]$label) {
    if ($LASTEXITCODE -ne 0) { throw "$label failed with exit code $LASTEXITCODE" }
}
Get-Command docker -ErrorAction Stop | Out-Null
Get-Command python -ErrorAction Stop | Out-Null
function Test-DockerEngine {
    $priorPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        docker info --format '{{.ServerVersion}}' 2>$null | Out-Null
        return $LASTEXITCODE -eq 0
    } finally { $ErrorActionPreference = $priorPreference }
}
if (!(Test-DockerEngine)) {
    $desktopPath = 'C:\Program Files\Docker\Docker\Docker Desktop.exe'
    if (!(Test-Path -LiteralPath $desktopPath)) { throw 'Docker Desktop is required; no executable found.' }
    Start-Process -FilePath $desktopPath -WindowStyle Hidden
    $deadline = (Get-Date).AddSeconds(120)
    do {
        Start-Sleep -Seconds 2
        $dockerReady = Test-DockerEngine
    } while (!$dockerReady -and (Get-Date) -lt $deadline)
    if (!$dockerReady) { throw 'Docker engine startup timed out.' }
}
python -c "import pandas, numpy, sklearn, sqlalchemy, psycopg2, fastapi, uvicorn, httpx"
if ($LASTEXITCODE -ne 0) {
    python -m pip install -r requirements.txt
    Check-Exit 'Python dependencies'
}
docker compose up -d --build oltp-db dwh-db app
Check-Exit 'Compose startup'
$deadline = (Get-Date).AddSeconds(90)
do {
    $oltpState = docker inspect --format '{{.State.Health.Status}}' retail-oltp-db
    $dwhState = docker inspect --format '{{.State.Health.Status}}' retail-dwh-db
    if ($oltpState -eq 'healthy' -and $dwhState -eq 'healthy') { break }
    Start-Sleep -Seconds 2
} while ((Get-Date) -lt $deadline)
if ($oltpState -ne 'healthy' -or $dwhState -ne 'healthy') { throw 'Database health check failed.' }
$apiDeadline = (Get-Date).AddSeconds(45)
$sourceHealthy = $false
do {
    try {
        $sourceResponse = Invoke-WebRequest 'http://127.0.0.1:8001/api/v1/inventory/HN' -UseBasicParsing -TimeoutSec 3
        $sourceHealthy = $sourceResponse.StatusCode -eq 200
    } catch { Start-Sleep -Seconds 1 }
} while (!$sourceHealthy -and (Get-Date) -lt $apiDeadline)
if (!$sourceHealthy) { throw 'Inventory source API readiness check failed.' }
python scripts/bootstrap_system.py
Check-Exit 'Schema and verified BI bootstrap'
if ($DownloadData) { python src/utils/data_downloader.py; Check-Exit 'Official dataset preparation' }
if ($RunETL) { python -m src.etl.pipeline --sources uci app api; Check-Exit 'ETL execution' }
if ($RunMining) { python -m src.mining.pipeline; Check-Exit 'Mining execution' }
$controlHealthy = $false
try { $health = Invoke-RestMethod 'http://127.0.0.1:8010/api/health' -TimeoutSec 5; $controlHealthy = $health.execution -eq 'REAL' } catch {}
if (!$controlHealthy) {
    New-Item -ItemType Directory -Force -Path (Join-Path $rootPath 'evidence') | Out-Null
    $pythonPath = (Get-Command python).Source
    Start-Process -FilePath $pythonPath -ArgumentList @('-m','uvicorn','src.web.app:app','--host','127.0.0.1','--port','8010') -WorkingDirectory $rootPath -WindowStyle Hidden -RedirectStandardOutput (Join-Path $rootPath 'evidence/control.stdout.log') -RedirectStandardError (Join-Path $rootPath 'evidence/control.stderr.log')
    $deadline = (Get-Date).AddSeconds(30)
    do {
        Start-Sleep -Seconds 1
        try { $health = Invoke-RestMethod 'http://127.0.0.1:8010/api/health' -TimeoutSec 3; $controlHealthy = $health.execution -eq 'REAL' } catch {}
    } while (!$controlHealthy -and (Get-Date) -lt $deadline)
}
if (!$controlHealthy) { throw 'Control API could not be verified; inspect evidence/control.stderr.log.' }
Write-Host 'VERIFIED: PostgreSQL OLTP/DWH and real control API are reachable.'
Write-Host 'Portal: http://127.0.0.1:8010/frontend/index.html'
Write-Host 'OLAP: http://127.0.0.1:8010/frontend/dashboard.html'
Write-Host 'API docs: http://127.0.0.1:8010/docs'
Write-Host 'Sources, ETL and mining are executed from the portal or CLI; old runs remain available.'
if (!$NoBrowser) { Start-Process 'http://127.0.0.1:8010/frontend/index.html' -WindowStyle Hidden }
