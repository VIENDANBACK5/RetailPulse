"""Read back real execution evidence and exercise the live outage/recovery path.

Run after START_RETAILPULSE.ps1. Never reloads the historical million-row file:
the previously executed full/replay jobs are independently checked against SQL.
"""
from pathlib import Path
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import requests
from sqlalchemy import text
from src.utils.db_helper import get_dwh_engine, get_oltp_engine

BASE = 'http://127.0.0.1:8010'
MINING = 'mining-20261020T170400-eea9afc3a6'


def digest(path):
    h = hashlib.sha256()
    with open(path, 'rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def request(path, **kwargs):
    response = requests.request(kwargs.pop('method', 'GET'), BASE + path, timeout=60, **kwargs)
    response.raise_for_status()
    return response.json()


def run_etl(scenario):
    run_id = request('/api/runs', method='POST', json={'kind': 'etl', 'params': {'sources': ['api'], 'scenario': scenario}})['run_id']
    deadline = time.monotonic() + 240
    while time.monotonic() < deadline:
        result = request('/api/runs/' + run_id)
        if result['status'] in ('SUCCESS', 'PARTIAL', 'FAILED'):
            return result
        time.sleep(1)
    raise TimeoutError(f'Actual backend job {run_id} not terminal after 240 seconds')


def main(browser=True):
    report = {'execution': 'REAL_INTEGRATION', 'checked_at': datetime.now(timezone.utc).isoformat(), 'steps': []}
    engine = get_dwh_engine()
    full = json.loads((ROOT / 'evidence/full_etl_and_replay.json').read_text(encoding='utf-8'))
    model_dir = ROOT / 'models/runs' / MINING

    def sql(query, params=None):
        with engine.connect() as conn:
            conn.execute(text("SET LOCAL statement_timeout='45s'"))
            return [dict(r) for r in conn.execute(text(query), params or {}).mappings()]

    def step(number, name, operation):
        try:
            evidence = operation()
            report['steps'].append({'step': number, 'name': name, 'status': 'PASS', 'evidence': evidence})
        except Exception as exc:
            report['steps'].append({'step': number, 'name': name, 'status': 'FAIL', 'error': str(exc)})
        print(json.dumps(report['steps'][-1], default=str), flush=True)

    def docker():
        records = []
        for container in ('retail-oltp-db', 'retail-dwh-db', 'retail-fastapi-app'):
            item = json.loads(subprocess.check_output(['docker', 'inspect', container], text=True))[0]
            assert item['State']['Running'], container
            health = item['State'].get('Health', {}).get('Status', 'not_configured')
            assert health in ('healthy', 'not_configured'), (container, health)
            records.append({'container': container, 'running': True, 'health': health})
        return records
    step(1, 'Docker services running', docker)

    def health():
        with get_oltp_engine().connect() as conn:
            assert conn.execute(text('SELECT 1')).scalar() == 1
        item = request('/api/health')
        assert item['execution'] == 'REAL' and item['status'] == 'UP'
        response = requests.get('http://127.0.0.1:8001/docs', timeout=20)
        response.raise_for_status()
        return item
    step(2, 'OLTP, DWH and APIs healthy', health)

    def provenance():
        items = sql('SELECT source_code,provenance,record_count,currency,raw_path,checksum FROM source_manifest WHERE run_id=:run', {'run': full['full']['run_id']})
        assert {'UCI_HISTORICAL', 'APP_OPERATIONAL'} <= {r['source_code'] for r in items}
        assert any(r['provenance'] == 'OFFICIAL_UCI' and r['record_count'] == 1067371 for r in items)
        assert any(r['provenance'] == 'DEMO' for r in items)
        return items
    step(3, 'Real historical versus demo source labels', provenance)

    def ingestion():
        item = request('/api/runs/' + full['full']['run_id'])
        assert item['status'] == 'SUCCESS'
        assert set(full['full']['sources']) == {'uci', 'app', 'api'}
        assert len(sql('SELECT 1 FROM source_manifest WHERE run_id=:run', {'run': item['run_id']})) >= 3
        return {'run_id': item['run_id'], 'status': item['status'], 'sources': list(full['full']['sources'])}
    step(4, 'Previously executed three-source ingestion readback', ingestion)

    def raw():
        items = sql('SELECT source_code,raw_path,checksum FROM source_manifest WHERE run_id=:run', {'run': full['full']['run_id']})
        for item in items:
            assert digest(ROOT / item['raw_path']) == item['checksum'], item['raw_path']
        return {'checksum_verified_manifests': len(items), 'run_id': full['full']['run_id']}
    step(5, 'Raw bytes match persisted source manifest checksums', raw)

    def etl():
        # Verify the executed batch's identities, not a frozen global total:
        # new labelled demo orders legitimately increase the live warehouse.
        items = sql('''SELECT s.source_code,count(*) AS rows,sum(f.total_amount) AS signed_amount
            FROM etl_batch_records b JOIN fact_sales f
              ON f.source_key=b.source_key AND f.source_record_id=b.source_record_id
            JOIN dim_source s ON s.source_key=b.source_key
            WHERE b.run_id=:run GROUP BY s.source_code''', {'run': full['full']['run_id']})
        by_source = {r['source_code']: r for r in items}
        assert by_source['UCI_HISTORICAL']['rows'] == 1061164
        assert by_source['APP_OPERATIONAL']['rows'] == 29
        return items
    step(6, 'Executed ETL facts read back from PostgreSQL', etl)

    def reconcile():
        items = sql('SELECT source_code,currency,source_records_count,target_count,source_total_amount,dwh_total_amount,diff_amount,status FROM etl_reconciliation_log WHERE run_id=:run', {'run': full['full']['run_id']})
        assert len(items) == 2 and all(r['status'] == 'MATCHED' and r['diff_amount'] == 0 for r in items)
        return items
    step(7, 'Exact source/batch/currency reconciliation', reconcile)

    def replay():
        run = full['replay']
        assert request('/api/runs/' + run['run_id'])['status'] == 'SUCCESS'
        items = sql('SELECT s.source_code,b.disposition,count(*) AS rows FROM etl_batch_records b JOIN dim_source s USING(source_key) WHERE b.run_id=:run GROUP BY s.source_code,b.disposition', {'run': run['run_id']})
        assert sum(r['rows'] for r in items if r['disposition'].lower() == 'unchanged') == 1061193, items
        assert all(r['disposition'].lower() == 'unchanged' for r in items)
        return {'run_id': run['run_id'], 'replay_of': run['replay_of'], 'sql_dispositions': items, 'inventory_inserted': run['sources']['api']['counts']['inserted']}
    step(8, 'Actual full Raw replay is idempotent (SQL membership readback)', replay)

    def olap():
        daily = sql("SELECT full_date,sum(net_sales_amount) value FROM vw_bi_sales_analytics WHERE currency='GBP' GROUP BY full_date")
        monthly = sql("SELECT year,month,sum(net_sales_amount) value FROM vw_bi_sales_analytics WHERE currency='GBP' GROUP BY year,month")
        assert sum(r['value'] for r in daily) == sum(r['value'] for r in monthly)
        slice_rows = sql("SELECT customer_country,source_code,count(*) rows FROM vw_bi_sales_analytics WHERE currency='GBP' AND year=2011 AND month BETWEEN 1 AND 3 GROUP BY customer_country,source_code")
        assert slice_rows
        assert request('/api/analytics/sales?currency=GBP&grain=month')
        return {'daily_groups': len(daily), 'monthly_groups': len(monthly), 'rollup_sum': sum(r['value'] for r in daily), 'dice_country_groups': len(slice_rows)}
    step(9, 'SQL OLAP roll-up and multi-dimensional dice with live API', olap)

    def mining():
        result = json.loads((model_dir / 'result.json').read_text())
        dataset = result['dataset']
        assert result['status'] == 'SUCCESS' and dataset['provenance'] == 'OFFICIAL_UCI'
        assert digest(model_dir / 'rfm.csv') == dataset['rfm_sha256']
        with open(model_dir / 'rfm_sql_python_check.csv', newline='', encoding='utf-8') as stream:
            checks = list(csv.DictReader(stream))
        assert len(checks) == dataset['customer_count']
        assert all(row[key] == 'True' for row in checks for key in ('recency_match', 'frequency_match', 'monetary_match'))
        evaluation = json.loads((model_dir / 'evaluation.json').read_text())
        assert len(evaluation['summary_table']) == 5
        assert all(r['seed_count'] == 10 and r['pair_count'] == 45 for r in evaluation['summary_table'])
        repeated = json.loads((ROOT / 'evidence/mining_repeat_run.json').read_text())
        assert request('/api/runs/' + repeated['run_id'])['status'] == 'SUCCESS'
        repeat_dir = ROOT / 'models/runs' / repeated['run_id']
        repeat_result = json.loads((repeat_dir / 'result.json').read_text())
        assert repeat_result['dataset']['rfm_sha256'] == dataset['rfm_sha256']
        assert repeat_result['selected_k'] == result['selected_k']
        assert repeat_result['profiles'] == result['profiles']
        repeat_evaluation = json.loads((repeat_dir / 'evaluation.json').read_text())
        assert repeat_evaluation['summary_table'] == evaluation['summary_table']
        repeat_count = sql('SELECT count(*) rows FROM customer_segment_snapshot WHERE run_id=:run', {'run': repeated['run_id']})[0]['rows']
        assert repeat_count == dataset['customer_count']
        return {'run_id': MINING, 'customers': dataset['customer_count'], 'selected_k': result['selected_k'], 'window': [dataset['window_start'], dataset['window_end']], 'seed_fits_per_run': 50, 'pairwise_ari_per_run': 225, 'rfm_checksum': dataset['rfm_sha256'], 'actual_repeat_run': repeated['run_id'], 'repeat_profiles_and_metric_tables_exact': True, 'repeat_persisted_customers': repeat_count}
    step(10, 'Executed official RFM and fifty-fit clustering experiment', mining)

    def snapshots():
        expected = list(csv.DictReader((model_dir / 'customer_segments.csv').open(encoding='utf-8')))
        actual = sql('SELECT customer_key,cluster_id,recency,frequency,monetary FROM customer_segment_snapshot WHERE run_id=:run ORDER BY customer_key', {'run': MINING})
        assert len(actual) == len(expected) == 4317
        by_customer = {int(r['customer_key']): r for r in expected}
        from decimal import Decimal
        for row in actual:
            match = by_customer[row['customer_key']]
            assert all(int(row[k]) == int(float(match[k])) for k in ('cluster_id', 'recency', 'frequency'))
            assert Decimal(str(row['monetary'])) == Decimal(match['monetary'])
        return {'run_id': MINING, 'exact_csv_to_database_customers': len(actual)}
    step(11, 'Persisted segment RFM/labels exactly match exported model results', snapshots)

    def bi():
        views = {name: sql('SELECT count(*) rows FROM ' + name)[0]['rows'] for name in ('vw_bi_sales_analytics', 'vw_bi_inventory_status', 'vw_bi_customer_segments')}
        assert all(views.values())
        for page in ('dashboard.html', 'customer-segments.html'):
            response = requests.get(BASE + '/frontend/' + page, timeout=20)
            response.raise_for_status()
        assert request('/api/analytics/segments?run_id=' + MINING)
        return {'web_dashboard': 'VERIFIED', 'views': views, 'native_power_bi': 'BLOCKED: Power BI Desktop unavailable; semantic model and DAX supplied, not executed'}
    step(12, 'Live SQL-backed BI dashboard (native Power BI remains blocked)', bi)

    def outage():
        before = sql("SELECT branch_code,stock_code,stock_on_hand,snapshot_time FROM vw_bi_inventory_status WHERE branch_code='DN' ORDER BY stock_code")
        failed = run_etl('dn_outage')
        assert failed['status'] == 'PARTIAL', failed
        during = sql("SELECT branch_code,stock_code,stock_on_hand,snapshot_time,node_status FROM vw_bi_inventory_status WHERE branch_code='DN' ORDER BY stock_code")
        assert during and all(r['node_status'] == 'OFFLINE' for r in during)
        assert before == [{k: r[k] for k in before[0]} for r in during]
        restored = run_etl('normal')
        assert restored['status'] == 'SUCCESS', restored
        after = sql("SELECT branch_code,stock_code,stock_on_hand,snapshot_time,node_status FROM vw_bi_inventory_status WHERE branch_code='DN' ORDER BY stock_code")
        assert all(r['node_status'] == 'ONLINE' for r in after)
        assert before == [{k: r[k] for k in before[0]} for r in after]
        return {'outage_run': failed['run_id'], 'outage_status': failed['status'], 'recovery_run': restored['run_id'], 'recovery_status': restored['status'], 'unchanged_dn_snapshots': len(before), 'mechanism': 'real refused HTTP connection for DN; three endpoints share one demo API server'}
    step(13, 'Actual API outage/recovery preserves last known inventory', outage)

    def portal():
        run_id = full['full']['run_id']
        item = request('/api/runs/' + run_id)
        logs = request('/api/runs/' + run_id + '/logs')
        reconciled = request('/api/runs/' + run_id + '/reconciliation')
        assert item['status'] == 'SUCCESS' and logs and len(reconciled) == 2
        return {'run_id': run_id, 'status': item['status'], 'backend_events': len(logs), 'reconciliation_rows': len(reconciled)}
    step(14, 'Portal reads real persisted run status, logs and reconciliation', portal)

    def screenshots():
        if browser:
            subprocess.run([sys.executable, str(ROOT / 'scripts/browser_verify.py')], cwd=ROOT, check=True, timeout=240)
        item = json.loads((ROOT / 'evidence/browser_verification.json').read_text())
        assert item['status'] == 'PASS' and not item['javascript_errors']
        assert len(item['screenshots']) >= 4
        return item
    step(15, 'Actual Chrome interaction and captured screenshots', screenshots)

    report['summary'] = {status: sum(r['status'] == status for r in report['steps']) for status in ('PASS', 'FAIL', 'BLOCKED')}
    report['native_power_bi'] = {'status': 'BLOCKED', 'reason': 'Power BI Desktop not installed/available; actual web BI fallback verified in steps 12 and 15. No PBIX execution claimed.'}
    report['status'] = 'PASS_WITH_NATIVE_POWER_BI_BLOCKED' if not report['summary']['FAIL'] else 'FAIL'
    (ROOT / 'evidence/end_to_end.json').write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding='utf-8')
    return int(bool(report['summary']['FAIL']))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--skip-browser', action='store_true')
    args = parser.parse_args()
    sys.exit(main(not args.skip_browser))
