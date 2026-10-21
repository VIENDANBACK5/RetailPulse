param([switch]$SkipBuild)

$ErrorActionPreference = 'Stop'
Push-Location (Split-Path -Parent $PSScriptRoot)
try {
    if (-not (Test-Path .env)) { Copy-Item .env.lake.example .env }
    $composeFiles = @('compose', '-f', 'docker-compose.yml', '-f', 'compose.lake.yml', '-f', 'compose.airflow.yml')
    function Invoke-RetailAirflow {
        & docker @composeFiles @args
        if ($LASTEXITCODE -ne 0) { throw "Docker command failed (exit $LASTEXITCODE)." }
    }
    if (-not $SkipBuild) { Invoke-RetailAirflow build airflow-apiserver }
    Invoke-RetailAirflow up -d minio oltp-db dwh-db app airflow-db
    Invoke-RetailAirflow exec -T app python seed_data.py
    Invoke-RetailAirflow up -d --wait --wait-timeout 180 airflow-apiserver airflow-scheduler airflow-dag-processor
    $airflowAddress = Invoke-RetailAirflow port airflow-apiserver 8080
    Write-Host "Airflow: http://$airflowAddress | user: admin"
    Write-Host 'Default local password: retail-airflow-local-only (or AIRFLOW_ADMIN_PASSWORD in .env)'
    Write-Host 'DAGs start paused. Trigger retailpulse_operations to test App/API.'
    Write-Host 'Trigger retailpulse_historical once to import UCI and train K-means.'
} finally {
    Pop-Location
}
