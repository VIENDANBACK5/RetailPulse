"""Source -> verified Raw lake -> transformations -> PostgreSQL."""
import argparse
import datetime
import io
import json
from pathlib import Path
import sys
import time
import uuid
from decimal import Decimal
BASE_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE_DIR))
import pandas as pd
from src.storage.lake import RawLake
from src.utils.db_helper import get_dwh_engine, init_dwh_schema, populate_dim_date
from src.etl.ingestion import ingest_source
from src.etl.extractors import read_uci_payload
from src.etl.transformers import transform_sales_data, transform_inventory_snapshots
from src.etl.loaders import load_fact_sales, load_fact_inventory, load_rejected_records
from src.etl.quality_check import reconcile_batch
from src.etl.contracts import utc_instant


def run_etl_pipeline(sources=None, *, uci_file=None, demo=False, manifests=None, batch_id=None):
    sources = list(sources if sources is not None else ['uci', 'app', 'api'])
    if any(source not in ('uci', 'app', 'api') for source in sources):
        raise ValueError('Unknown ETL source')
    batch_id = batch_id or f'BATCH-{datetime.datetime.now(datetime.timezone.utc):%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:8]}'
    started = time.monotonic()
    lake = RawLake()
    engine = get_dwh_engine()
    result = {'batch_id': batch_id, 'lake_backend': lake.backend, 'sources': {}, 'status': 'FAILED'}
    init_dwh_schema(engine)
    populate_dim_date(engine)
    replay = {}
    for key in manifests or []:
        manifest, payload = lake.read_raw(key)
        if manifest['source'] in replay:
            raise ValueError('Only one manifest per source may be replayed')
        replay[manifest['source']] = (key, manifest, payload)
    if manifests:
        sources = list(replay)
    for source in sources:
        entry = {'status': 'FAILED'}
        result['sources'][source] = entry
        try:
            if source in replay:
                key, manifest, payload = replay[source]
            else:
                key = ingest_source(lake, source, batch_id, uci_file=uci_file, demo=demo)
                manifest, payload = lake.read_raw(key)
            entry.update({'manifest_key': key, 'raw_uri': lake.uri(manifest['object_key']),
                          'sha256': manifest['sha256'], 'data_mode': manifest['data_mode']})
            print(f"Raw verified: {entry['raw_uri']}", flush=True)
            observed_at = utc_instant(manifest.get('collected_at', manifest['ingested_at']))
            if source == 'api':
                snapshots = json.loads(payload)
                frame = transform_inventory_snapshots(snapshots, observed_at=observed_at)
                entry['records_loaded'] = load_fact_inventory(engine, frame, manifest['batch_id'])
                entry['offline_nodes'] = frame.loc[frame.node_status != 'ONLINE', 'branch_code'].unique().tolist()
                entry['status'] = 'PARTIAL' if entry['offline_nodes'] else 'SUCCESS'
                continue
            if source == 'uci':
                frame = read_uci_payload(payload, manifest['object_key'], manifest['sha256'])
            else:
                frame = pd.read_csv(io.BytesIO(payload), dtype={'customer_id': str, 'source_record_id': str,
                    'invoice_no': str, 'stock_code': str, 'unit_price': str, 'quantity': str})
            source_code = 'UCI_HISTORICAL' if source == 'uci' else 'APP_OPERATIONAL'
            valid, rejected = transform_sales_data(frame, source_code)
            valid['source_observed_at'] = observed_at
            stats = load_fact_sales(engine, valid, batch_id, return_stats=True)
            load_rejected_records(engine, rejected, batch_id, source_code)
            check = reconcile_batch(engine, batch_id, source_code, len(frame), stats['inserted_count'], len(rejected),
                (sum(valid['total_amount'], Decimal('0.00')) if not valid.empty else Decimal('0.00'))
                    - stats['superseded_source_amount'],
                stats['matched_amount'], dwh_records_existing=stats['existing_count'],
                superseded_records_count=stats['superseded_count'])
            entry.update(stats)
            entry.update({'input_count': len(frame), 'rejected_count': len(rejected),
                          'reconciliation': check['status'],
                          'status': 'SUCCESS' if check['status'] == 'MATCHED' else 'FAILED'})
        except Exception as error:
            entry['error'] = f'{type(error).__name__}: {error}'
            print(f"Source {source} FAILED: {entry['error']}", flush=True)
    states = [entry['status'] for entry in result['sources'].values()]
    result['status'] = 'FULL_SUCCESS' if states and all(s == 'SUCCESS' for s in states) else (
        'PARTIAL' if any(s in ('SUCCESS', 'PARTIAL') for s in states) else 'FAILED')
    result['elapsed_seconds'] = round(time.monotonic() - started, 3)
    result['finished_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    result['result_uri'] = lake.uri(f'runs/{batch_id}.json')
    lake.write_run_result(batch_id, result)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str), flush=True)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sources', nargs='+', default=['uci', 'app', 'api'])
    parser.add_argument('--uci-file')
    parser.add_argument('--demo', action='store_true')
    parser.add_argument('--manifest', action='append', help='Replay verified lake manifests')
    parser.add_argument('--batch-id')
    args = parser.parse_args()
    outcome = run_etl_pipeline(args.sources, uci_file=args.uci_file, demo=args.demo,
                               manifests=args.manifest, batch_id=args.batch_id)
    sys.exit(0 if outcome['status'] == 'FULL_SUCCESS' else 1)
