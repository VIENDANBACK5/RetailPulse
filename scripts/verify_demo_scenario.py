"""Execute the teaching story using real HTTP, real ETL and actual SQL checks.

Creates one labelled DEMO session, keeps its audit records, and never resets DBs.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time
import uuid

import requests

ROOT = Path(__file__).resolve().parents[1]


def main(base='http://127.0.0.1:8010', key=None):
    key = key or 'verify-demo-' + uuid.uuid4().hex[:16]
    evidence = {'execution': 'REAL_HTTP_REAL_ETL', 'started_at': datetime.now(timezone.utc).isoformat(), 'checks': []}

    def get(path):
        response = requests.get(base + path, timeout=40)
        response.raise_for_status()
        return response.json()

    def post(path, body):
        response = requests.post(base + path, json=body, timeout=40)
        response.raise_for_status()
        return response.json()

    def execute(params):
        result = post('/api/runs', {'kind': 'etl', 'params': params})
        deadline = time.monotonic() + 240
        while time.monotonic() < deadline:
            run = get('/api/runs/' + result['run_id'])
            if run['status'] in ('SUCCESS', 'PARTIAL', 'FAILED'):
                return run
            time.sleep(.5)
        raise TimeoutError('ETL did not reach terminal status within four minutes')

    session = post('/api/demo/sessions', {'idempotency_key': key, 'label': 'Verified live retail story'})
    evidence['session_id'] = session['session_id']
    evidence['expected'] = session['expected']
    repeated = post('/api/demo/sessions', {'idempotency_key': key})
    assert repeated['source_item_ids'] == session['source_item_ids']
    evidence['checks'].append({'name': 'PREPARE_SOURCE_ORDERS_IDEMPOTENT', 'status': 'PASS', 'rows': len(session['source_rows']),
                               'warehouse_before': session['actual'], 'verification_before': session['verification']['status']})
    run = execute({'sources': ['app', 'api']})
    assert run['status'] == 'SUCCESS', run
    verified = get('/api/demo/session/' + session['session_id'])
    assert verified['verification']['status'] == 'MATCHED', verified
    assert verified['actual'] == verified['expected']
    traces = [get('/api/lineage/' + str(fact['sales_key'])) for fact in verified['warehouse_rows']]
    assert all(trace['raw_record'] is not None and
               str(trace['raw_record']['source_record_id']) == str(trace['fact']['source_record_id'])
               for trace in traces)
    evidence['first_run_id'] = run['run_id']
    evidence['first_run'] = run
    evidence['session_verified'] = verified
    evidence['source_traces'] = traces
    evidence['checks'].append({'name': 'ACTUAL_SOURCE_RAW_DWH_KPI', 'status': 'PASS', 'actual': verified['actual']})
    replay = execute({'sources': ['app', 'api'], 'replay_run_id': run['run_id']})
    assert replay['status'] == 'SUCCESS', replay
    result = replay.get('metadata', {}).get('result', replay.get('metadata', {}))
    counts = result['sources']['app']['counts']
    assert counts['inserted'] == counts['updated'] == 0, counts
    assert counts['reconciliation'] == 'MATCHED', counts
    verified_replay = get('/api/demo/session/' + session['session_id'])
    assert verified_replay['verification']['status'] == 'MATCHED'
    own_replay = next(row for row in verified_replay['observed_runs'] if row['run_id'] == replay['run_id'])
    assert own_replay['unchanged'] == 3 and own_replay['inserted'] == own_replay['updated'] == 0, own_replay
    evidence['replay_run_id'] = replay['run_id']
    evidence['replay_run'] = replay
    evidence['checks'].append({'name': 'FROZEN_RAW_REPLAY_IDEMPOTENT', 'status': 'PASS', 'counts': counts, 'session_counts': own_replay})
    evidence.update(status='PASS', finished_at=datetime.now(timezone.utc).isoformat())
    target = ROOT / 'evidence/demo_scenario.json'
    target.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'status': evidence['status'], 'session_id': session['session_id'], 'run_id': run['run_id'], 'actual': verified['actual']}, indent=2))
    return evidence


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', default='http://127.0.0.1:8010')
    parser.add_argument('--key')
    args = parser.parse_args()
    main(args.base, args.key)
