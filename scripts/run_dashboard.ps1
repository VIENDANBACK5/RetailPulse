param([switch]$SkipHistorical)

$ErrorActionPreference = 'Stop'
$projectDirectory = Split-Path -Parent $PSScriptRoot
Push-Location $projectDirectory
try {
    $composeFiles = @('compose', '-f', 'docker-compose.yml', '-f', 'compose.lake.yml')
    function Invoke-RetailDocker {
        & docker @composeFiles @args
        if ($LASTEXITCODE -ne 0) { throw "Docker command failed (exit $LASTEXITCODE)." }
    }

    Invoke-RetailDocker up -d --build minio oltp-db dwh-db app
    Invoke-RetailDocker build pipeline
    Invoke-RetailDocker exec -T app python seed_data.py
    if ($SkipHistorical) {
        Invoke-RetailDocker run --rm --no-deps pipeline python -m src.etl.pipeline --sources app api
    } else {
        Invoke-RetailDocker run --rm --no-deps pipeline python scripts/import_uci.py
        Invoke-RetailDocker run --rm --no-deps pipeline python -m src.etl.pipeline --sources uci app api
        Invoke-RetailDocker run --rm --no-deps pipeline python -m src.mining.pipeline --k 4
    }
    Invoke-RetailDocker run --rm --no-deps pipeline python scripts/prepare_dashboard.py
    Write-Host 'Dashboard: http://localhost:8001/frontend/dashboard.html | MinIO: http://localhost:9001'
    Write-Host 'Refresh reads the warehouse. Run ETL to collect new source data.'
} finally {
    Pop-Location
}
