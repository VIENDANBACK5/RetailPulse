"""Finite CLI jobs. Airflow invokes these with the isolated project interpreter."""
import argparse
import datetime
import json
import os
from pathlib import Path
import sys
import urllib.request


def execute(action, *, batch_id, source=None, ingested_at=None, manifest=None, k=None):
    if action == 'collect':
        from src.etl.ingestion import ingest_source
        from src.storage.lake import RawLake
        instant = datetime.datetime.fromisoformat(ingested_at)
        if instant.tzinfo is None:
            raise ValueError('Ingestion timestamp must have a timezone')
        key = ingest_source(RawLake(), source, batch_id, ingested_at=instant)
        return {'manifest_key': key, 'batch_id': batch_id, 'status': 'SUCCESS'}
    if action == 'load':
        if not manifest:
            raise ValueError('A verified Raw manifest is required')
        from src.etl.pipeline import run_etl_pipeline
        return run_etl_pipeline(manifests=[manifest], batch_id=batch_id)
    if action == 'mine':
        from src.mining.pipeline import run_mining_pipeline
        result = run_mining_pipeline(k_clusters=k)
        from src.runtime.runs import update_run
        update_run(result['run_id'], metadata={'orchestration_batch_id': batch_id})
        return result
    if action == 'download':
        from src.utils.data_downloader import prepare_uci_data
        path = prepare_uci_data()
        return {'status': 'SUCCESS', 'path': path}
    if action == 'read_models':
        from scripts.prepare_dashboard import prepare_dashboard
        prepare_dashboard()
        return {'status': 'SUCCESS'}
    if action == 'verify':
        host, port = os.getenv('APP_HOST', 'localhost'), os.getenv('APP_PORT', '8001')
        with urllib.request.urlopen(f'http://{host}:{port}/api/v1/analytics/status', timeout=30) as response:
            data = json.load(response)
        if data.get('warehouse') != 'connected':
            raise RuntimeError(f'Dashboard warehouse unavailable: {data}')
        return {'status': 'SUCCESS', 'dashboard': data}
    raise ValueError('Unknown orchestration action')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['collect', 'load', 'mine', 'download', 'read_models', 'verify'])
    parser.add_argument('--batch-id', required=True)
    parser.add_argument('--source', choices=['uci', 'app', 'api'])
    parser.add_argument('--ingested-at')
    parser.add_argument('--manifest')
    parser.add_argument('--k', type=int, default=None)
    parser.add_argument('--output', required=True)
    args = vars(parser.parse_args())
    output = Path(args.pop('output'))
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        result = execute(**args)
    except Exception as error:
        output.write_text(json.dumps({'status': 'FAILED', 'error': f'{type(error).__name__}: {error}'}), encoding='utf-8')
        raise
    output.write_text(json.dumps(result, default=str), encoding='utf-8')
    print(json.dumps(result, default=str), flush=True)
    return 0 if result['status'] in ('SUCCESS', 'FULL_SUCCESS') else (2 if result['status'] == 'PARTIAL' else 1)


if __name__ == '__main__':
    sys.exit(main())
