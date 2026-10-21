param([switch]$SkipBuild)

$ErrorActionPreference = 'Stop'
Push-Location (Split-Path -Parent $PSScriptRoot)
try {
    $composeFiles = @('compose', '-f', 'docker-compose.yml', '-f', 'compose.lake.yml', '-f', 'compose.airflow.yml')
    function Invoke-RetailAirflow {
        & docker @composeFiles @args
        if ($LASTEXITCODE -ne 0) { throw "Docker command failed (exit $LASTEXITCODE)." }
    }
    if (-not $SkipBuild) { Invoke-RetailAirflow build airflow-apiserver }
    Invoke-RetailAirflow up -d minio oltp-db dwh-db app airflow-db
    python scripts/bootstrap_system.py
    if ($LASTEXITCODE -ne 0) { throw 'Warehouse/schema bootstrap failed.' }
    Invoke-RetailAirflow up -d --wait --wait-timeout 300 airflow-apiserver airflow-scheduler airflow-dag-processor
    $analytics = Invoke-RestMethod 'http://127.0.0.1:8001/api/v1/analytics/status' -TimeoutSec 30
    if ($analytics.warehouse -ne 'connected') { throw 'Airflow is up but analytics warehouse readiness failed.' }
    $importErrors = Invoke-RetailAirflow exec -T airflow-apiserver airflow dags list-import-errors --output json
    $parsedErrors = ($importErrors -join [Environment]::NewLine) | ConvertFrom-Json
    if ($null -ne $parsedErrors -and @($parsedErrors).Count -gt 0) { throw 'Airflow DAG import errors detected; run airflow dags list-import-errors for details.' }
    $airflowAddress = Invoke-RetailAirflow port airflow-apiserver 8080
    Write-Host "Airflow: http://$airflowAddress | user: admin"
    Write-Host 'Default local password: retail-airflow-local-only (or AIRFLOW_ADMIN_PASSWORD in .env)'
    Write-Host 'DAGs start paused. Trigger retailpulse_operations to test App/API.'
    Write-Host 'Trigger retailpulse_historical once to import UCI and train K-means.'
} finally {
    Pop-Location
}
