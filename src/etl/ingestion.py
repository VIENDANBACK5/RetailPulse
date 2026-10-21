"""Collect once per source/run, then reuse the verified manifest on task retries."""
import datetime
import json
import hashlib
from pathlib import Path

from src.etl.extractors import extract_app_db_orders, extract_api_inventory
from src.utils.db_helper import load_config
from src.utils.data_downloader import prepare_uci_data

BASE_DIR = Path(__file__).resolve().parents[2]


def ingest_source(lake, source, batch_id, *, uci_file=None, demo=False, ingested_at=None, branch_nodes=None, oltp_engine=None):
    if source not in ('uci', 'app', 'api'):
        raise ValueError('Unknown ETL source')
    collected_at = ingested_at or datetime.datetime.now(datetime.timezone.utc)
    manifest_key = lake.raw_prefix(source, batch_id, collected_at) + '/manifest.json'
    checkpoint_key = f'checkpoints/{batch_id}/{source}.json'
    checkpoint = lake.get_optional(checkpoint_key)
    if checkpoint is not None:
        identity = json.loads(checkpoint)
        collected_at = datetime.datetime.fromisoformat(identity['ingested_at'])
        manifest_key = identity['manifest_key']
    else:
        # Persist identity BEFORE collection: clearing a task or crossing midnight
        # cannot change the run's input partition. Writers are serialized by Airflow.
        lake.put(checkpoint_key, json.dumps({'manifest_key': manifest_key,
            'ingested_at': collected_at.isoformat()}).encode('utf-8'), 'application/json')
    if lake.get_optional(manifest_key) is not None:
        lake.read_raw(manifest_key)
        print(f'Reusing verified input: {manifest_key}', flush=True)
        return manifest_key

    # Partition/run time can precede this attempt by hours. Version ordering uses
    # the actual collection start, frozen in the manifest after a successful read.
    observation_time = datetime.datetime.now(datetime.timezone.utc)
    mode = 'operational'
    provenance = 'DEMO'
    metadata = {}
    if source == 'uci':
        configured = load_config().get('etl', {}).get('uci_file_path', 'data_lake/raw/uci/online_retail_II.xlsx')
        path = Path(uci_file) if uci_file else BASE_DIR / configured
        if not path.exists() and demo:
            path = Path(prepare_uci_data())
        if not path.exists():
            raise FileNotFoundError('Provide original UCI CSV/XLSX or run the official downloader')
        payload, filename, count = path.read_bytes(), path.name, None
        sidecar = path.with_suffix(path.suffix + '.provenance.json')
        metadata = json.loads(sidecar.read_text(encoding='utf-8')) if sidecar.exists() else {}
        digest = hashlib.sha256(payload).hexdigest()
        if metadata.get('checksum') and metadata['checksum'] != digest:
            raise ValueError('Source checksum does not match provenance manifest')
        provenance = metadata.get('provenance', 'UNVERIFIED') if metadata.get('checksum') == digest else 'UNVERIFIED'
        mode = 'historical' if provenance == 'OFFICIAL_UCI' else 'unverified'
        count = metadata.get('record_count')
        metadata = dict(metadata, original_filename=filename)
    elif source == 'app':
        frame = extract_app_db_orders(engine=oltp_engine) if oltp_engine is not None else extract_app_db_orders()
        payload, filename, count = frame.to_csv(index=False).encode('utf-8'), 'orders.csv', len(frame)
    else:
        snapshots = extract_api_inventory(branch_nodes) if branch_nodes is not None else extract_api_inventory()
        payload, filename, count = json.dumps(snapshots, ensure_ascii=False).encode('utf-8'), 'inventory.json', sum(len(n.get('items', [])) for n in snapshots)
    return lake.write_raw(source, batch_id, filename, payload, record_count=count,
                          mode=mode, ingested_at=collected_at, collected_at=observation_time,
                          provenance=provenance, currency='GBP' if source == 'uci' else 'VND', metadata=metadata)
