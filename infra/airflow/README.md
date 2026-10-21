# RetailPulse Airflow integration

Airflow 3.3.1 isolates project dependencies in `/opt/retail-venv`. DAG parsing opens no warehouse or lake connection. Metadata, authentication and task logs use separate project volumes. Existing warehouse and operational data are preserved.

## Start

```powershell
.\START_RETAILPULSE.ps1 -WithLake -WithAirflow -NoBrowser
```

Portal: http://127.0.0.1:8010/frontend/index.html. Analytics: http://127.0.0.1:8001/frontend/dashboard.html. MinIO: http://127.0.0.1:9001. Airflow: http://127.0.0.1:18082. Local Airflow login: admin; password comes from AIRFLOW_ADMIN_PASSWORD (default retail-airflow-local-only). These are local demonstration credentials.

All DAGs start paused. Do not unpause the operational schedule until a manual run succeeds. The write pool has one slot shared by all DAGs, preventing simultaneous Airflow warehouse writers.

## Data contract

Collection freezes a source/batch manifest in MinIO. Loading passes exactly that manifest to ETL. The pipeline verifies its payload checksum and materializes a local immutable mirror for lineage; it does not collect unrelated sources. Each execution has a fresh registry run_id; the original source batch_id remains linked. Retrying collection reuses the same validated manifest. Retrying loading creates a new execution against the same input.

Historical import uses the canonical official UCI downloader and provenance sidecar. Mining selects K automatically unless an explicit nullable k DAG parameter is provided. A manual override is labelled in the result.

## Real verification

```powershell
python scripts/verify_airflow.py --dag retailpulse_operations --output evidence/airflow_operations.json
python scripts/verify_airflow.py --dag retailpulse_historical --timeout 1800 --output evidence/airflow_historical.json
python scripts/verify_airflow.py --dag retailpulse_replay --manifest raw/missing/manifest.json --expected failed --output evidence/airflow_missing_manifest.json
```

For successful replay, pass an existing manifest object key with --manifest. The verifier authenticates, triggers a DAG, waits for terminal task states, saves evidence and restores the original paused state. An expected failed missing-manifest run is a negative safety test, never a successful pipeline.

PARTIAL requires restoring the source and a new collection. FAILED retries once with a fresh pipeline execution ID. A successful DAG requires successful loading, canonical SQL preparation and a live Analytics warehouse check.

## Boundaries

Task-state success alone does not prove data correctness. Inspect registry reconciliation, inserted/updated/unchanged counts, source manifests and SQL results. HN/DN/SG are three branches of one FastAPI service, not independent machines. Avoid a separate million-row CLI job during a historical DAG.
