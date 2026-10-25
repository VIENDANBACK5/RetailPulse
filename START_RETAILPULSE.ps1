param([switch]$DownloadData, [switch]$RunETL, [switch]$RunMining, [switch]$NoBrowser, [switch]$WithLake, [switch]$WithAirflow)
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
python -c "import pandas, numpy, sklearn, sqlalchemy, psycopg2, fastapi, uvicorn, httpx, boto3"
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
if ($WithAirflow) { $WithLake = $true }
if ($WithLake) {
    docker compose -f docker-compose.yml -f compose.lake.yml up -d --build --wait --wait-timeout 240 minio
    Check-Exit 'MinIO startup and health'
    # Host runner/control API uses the same bucket as containerized Airflow.
    if (Test-Path .env) {
        foreach ($line in Get-Content .env) {
            if ($line -match '^\s*(LAKE_ACCESS_KEY|LAKE_SECRET_KEY|LAKE_BUCKET)\s*=\s*(.*)$') {
                [Environment]::SetEnvironmentVariable($matches[1], $matches[2].Trim().Trim([char]34).Trim([char]39), 'Process')
            }
        }
    }
    $env:LAKE_BACKEND = 's3'
    $env:LAKE_ENDPOINT_URL = 'http://127.0.0.1:9000'
    if (!$env:LAKE_ACCESS_KEY) { $env:LAKE_ACCESS_KEY = 'retailpulse' }
    if (!$env:LAKE_SECRET_KEY) { $env:LAKE_SECRET_KEY = 'retailpulse-local-only' }
    if (!$env:LAKE_BUCKET) { $env:LAKE_BUCKET = 'retailpulse-raw' }
    python -c "from src.storage.lake import RawLake; lake=RawLake(); print('Verified lake backend:', lake.backend); lake.client.head_bucket(Bucket=lake.bucket)"
    Check-Exit 'MinIO authentication and bucket readiness'
}
python scripts/bootstrap_system.py
Check-Exit 'Schema and verified BI bootstrap'
if ($WithAirflow) {
    & (Join-Path $rootPath 'scripts/run_airflow.ps1')
}
if ($DownloadData) { python src/utils/data_downloader.py; Check-Exit 'Official dataset preparation' }
if ($RunETL) { python -m src.etl.pipeline --sources uci app api; Check-Exit 'ETL execution' }
if ($RunMining) { python -m src.mining.pipeline; Check-Exit 'Mining execution' }
$controlHealthy = $false
try { $health = Invoke-RestMethod 'http://127.0.0.1:8010/api/health' -TimeoutSec 5; $controlHealthy = $health.execution -eq 'REAL' } catch {}
if ($controlHealthy) {
    $expectedBackend = if ($env:LAKE_BACKEND) { $env:LAKE_BACKEND } else { 'local' }
    if ($health.lake_backend -ne $expectedBackend -or $health.app_id -ne 'retailpulse-control-v6') {
        if ($health.active_run) { throw "Control API is processing $($health.active_run). Wait before changing lake mode." }
        # Only restart the verified RetailPulse uvicorn listener, never an unrelated port owner.
        $listeners = @(Get-NetTCPConnection -LocalPort 8010 -State Listen -ErrorAction SilentlyContinue)
        $ownedPids = @($listeners | Select-Object -ExpandProperty OwningProcess -Unique)
        foreach ($ownedPid in $ownedPids) {
            $ownedProcess = Get-CimInstance Win32_Process -Filter "ProcessId=$ownedPid"
            if ($ownedProcess.CommandLine -notmatch 'uvicorn\s+src\.web\.app:app') {
                throw 'Port 8010 belongs to a process whose RetailPulse ownership cannot be verified.'
            }
            Stop-Process -Id $ownedPid
        }
        $controlHealthy = $false
    }
}
if (!$controlHealthy) {
    New-Item -ItemType Directory -Force -Path (Join-Path $rootPath 'evidence') | Out-Null
    $pythonPath = (Get-Command python).Source
    $controlProcess = Start-Process -FilePath $pythonPath -ArgumentList @('-m','uvicorn','src.web.app:app','--host','127.0.0.1','--port','8010') -WorkingDirectory $rootPath -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $rootPath 'evidence/control.stdout.log') -RedirectStandardError (Join-Path $rootPath 'evidence/control.stderr.log')
    $controlProcess.Id | Set-Content (Join-Path $rootPath 'evidence/control.pid')
    $deadline = (Get-Date).AddSeconds(30)
    do {
        Start-Sleep -Seconds 1
        try { $health = Invoke-RestMethod 'http://127.0.0.1:8010/api/health' -TimeoutSec 3; $controlHealthy = $health.execution -eq 'REAL' } catch {}
    } while (!$controlHealthy -and (Get-Date) -lt $deadline)
}
if (!$controlHealthy) { throw 'Control API could not be verified; inspect evidence/control.stderr.log.' }
if ($WithLake -and $health.lake_backend -ne 's3') { throw 'Control API did not enable the verified MinIO backend.' }
Write-Host 'VERIFIED: PostgreSQL OLTP/DWH and real control API are reachable.'
Write-Host 'Portal: http://127.0.0.1:8010/frontend/index.html'
Write-Host 'OLAP: http://127.0.0.1:8010/frontend/dashboard.html'
Write-Host 'Danh frontend: http://127.0.0.1:8010/frontend/etl-monitor.html'
Write-Host 'API docs: http://127.0.0.1:8010/docs'
if ($WithLake) { Write-Host 'MinIO: http://127.0.0.1:9001 (Raw bucket shared by CLI and Airflow)' }
if ($WithAirflow) { Write-Host 'Airflow: http://127.0.0.1:18082 (DAGs paused until manually triggered)' }
Write-Host 'Danh workspace: Sources / Raw / ETL / DWH / OLAP / Mining / BI use the real control API.'
if (!$NoBrowser) { Start-Process 'http://127.0.0.1:8010/frontend/index.html' -WindowStyle Hidden }
