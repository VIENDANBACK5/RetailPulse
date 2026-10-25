"""Exercise the actual teaching demo with one owned, idempotent OLTP session.

Actions are browser clicks; HTTP is used only to independently read persisted
run/session results. Re-running resumes the same saved key unless --key is set.
"""
from pathlib import Path
raise SystemExit('RETIRED: seven-step frontend removed at user request. Run python scripts/verify_danh_frontend.py for original Danh UI checks; this does not verify ETL/ML controls.')
from datetime import datetime, timezone
import argparse
import json
import uuid

import requests
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'evidence/live_demo_ui.json'
SHOTS = ROOT / 'evidence/live_demo_ui'
BASE = 'http://127.0.0.1:8010'
STORAGE = 'retailpulse-live-story-v1'


def read(path):
    response = requests.get(BASE + '/api' + path, timeout=30)
    response.raise_for_status()
    return response.json()


def main(key=None):
    prior = json.loads(OUT.read_text(encoding='utf-8')) if OUT.exists() else {}
    key = key or prior.get('idempotency_key') or 'ui-demo-' + uuid.uuid4().hex
    result = {'execution': 'REAL_CHROME_REAL_OLTP_ETL_MINING',
              'started_at': datetime.now(timezone.utc).isoformat(),
              'idempotency_key': key, 'checks': [], 'status': 'RUNNING'}
    SHOTS.mkdir(parents=True, exist_ok=True)

    def save():
        OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')

    save()
    errors = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(channel='chrome', headless=True)
            context = browser.new_context(viewport={'width': 1440, 'height': 1000})
            context.add_init_script(f"if (!localStorage.getItem({json.dumps(STORAGE)})) localStorage.setItem({json.dumps(STORAGE)}, JSON.stringify({{key:{json.dumps(key)},runs:{{}},step:0}}));")
            page = context.new_page()
            page.set_default_timeout(90000)
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(BASE + '/frontend/index.html')
            page.wait_for_selector('.portal-header')
            assert page.locator('#portal-navigation [aria-current=step]').get_attribute('href') == 'index.html#step=1'
            page.locator('#session-label').fill('Actual browser teaching-demo verification')
            with page.expect_response(lambda r: r.url.endswith('/api/demo/sessions') and r.request.method == 'POST') as prepared:
                page.locator('#prepare-session').click()
            session = prepared.value.json()
            assert prepared.value.status == 200
            sid = session['session_id']
            result['session_id'] = sid
            result['source_item_ids'] = session['source_item_ids']
            result['source_order_codes'] = session['source_order_codes']
            assert len(session['source_rows']) == 3
            assert session['verification']['status'] in ('PENDING', 'MATCHED')
            if not prior.get('session_id'):
                assert session['verification']['status'] == 'PENDING'
                assert session['actual']['rows'] == 0
            result['checks'].append({'name': 'PREPARE_OWNED_THREE_OLTP_ROWS', 'status': 'PASS', 'warehouse_before': session['actual']['rows']})
            save()
            print(json.dumps({'idempotency_key': key, 'session_id': sid, 'source_item_ids': result['source_item_ids']}), flush=True)

            def step(number):
                page.locator(f'[data-step="{number}"]').click()
                assert page.locator(f'[data-demo-step="{number}"]').is_visible()

            def run(button_id, expected):
                with page.expect_response(lambda r: r.url.endswith('/api/runs') and r.request.method == 'POST') as triggered:
                    page.locator('#' + button_id).click()
                assert triggered.value.status == 202, triggered.value.text()
                identifier = triggered.value.json()['run_id']
                page.wait_for_function("""({id,expected,button}) => document.querySelector('#demo-run-id').textContent===id
                    && document.querySelector('#demo-run-status').textContent===expected
                    && !document.getElementById(button).disabled""",
                    arg={'id': identifier, 'expected': expected, 'button': button_id}, timeout=240000)
                persisted = read('/runs/' + identifier)
                assert persisted['status'] == expected
                result.setdefault('runs', {})[button_id] = identifier
                save()
                return persisted

            # File evidence is also read from actual persisted official Raw.
            page.locator('#preview-file').locator('..').locator('summary').click()
            page.locator('#preview-file').click()
            page.wait_for_selector('#file-preview pre')
            file_preview = json.loads(page.locator('#file-preview pre').inner_text())
            assert len(file_preview.get('rows', [])) == 5
            result['checks'].append({'name': 'OFFICIAL_FILE_RAW_PREVIEW', 'status': 'PASS'})
            step(1)
            loaded = run('run-demo-etl', 'SUCCESS')
            session = read('/demo/session/' + sid)
            assert session['verification']['status'] == 'MATCHED'
            assert session['actual']['rows'] == 3
            assert session['actual']['gross_purchase_value'] == session['actual']['net_sales'] == 325000
            assert session['actual']['cancellation_value'] == 50000
            assert session['actual']['order_count'] == 1
            result['checks'].append({'name': 'ACTUAL_ETL_AND_SESSION_SQL_KPI', 'status': 'PASS', 'actual': session['actual']})
            page.get_by_role('button', name='Xem Raw APP', exact=True).click()
            page.wait_for_selector('#demo-raw-preview pre')
            raw = json.loads(page.locator('#demo-raw-preview pre').inner_text())
            assert len(raw['session_raw_rows']) == 3
            assert {str(r['source_record_id']) for r in raw['session_raw_rows']} == set(map(str, session['source_item_ids']))
            result['checks'].append({'name': 'THREE_FACT_LINES_TRACE_TO_RAW', 'status': 'PASS'})
            step(2)
            page.locator('#inspect-transform').click()
            page.wait_for_selector('#transform-proof tbody tr')
            assert page.locator('#transform-proof tbody tr').count() == 3
            result['checks'].append({'name': 'RAW_TO_FACT_TRANSFORM_COMPARISON', 'status': 'PASS'})
            step(3)
            assert page.locator('#warehouse-orders tbody tr').count() == 3
            page.screenshot(path=str(SHOTS / '01_session_warehouse.png'), full_page=True)
            page.locator('#replay-demo').locator('..').locator('summary').first.click()
            replay = run('replay-demo', 'SUCCESS')
            replay_result = replay['metadata'].get('result', replay['metadata'])
            counts = replay_result['sources']['app']['counts']
            assert counts['inserted'] == counts['updated'] == 0
            session = read('/demo/session/' + sid)
            observation = next(r for r in session['observed_runs'] if r['run_id'] == replay['run_id'])
            assert observation['unchanged'] == observation['rows'] == 3
            result['checks'].append({'name': 'FROZEN_RAW_REPLAY_IDEMPOTENT', 'status': 'PASS', 'session_observation': observation, 'source_counts': counts})
            step(6)
            page.locator('#outage-demo').locator('..').locator('summary').first.click()
            before = {r['stock_code']: r['stock_on_hand'] for r in read('/analytics/inventory') if r['branch_code'] == 'DN'}
            assert len(before) == 20
            run('outage-demo', 'PARTIAL')
            offline = [r for r in read('/analytics/inventory') if r['branch_code'] == 'DN']
            assert {r['stock_code']: r['stock_on_hand'] for r in offline} == before
            assert all(r['node_status'] == 'OFFLINE' for r in offline)
            page.screenshot(path=str(SHOTS / '02_dn_outage.png'), full_page=True)
            run('recover-demo', 'SUCCESS')
            recovered = [r for r in read('/analytics/inventory') if r['branch_code'] == 'DN']
            assert {r['stock_code']: r['stock_on_hand'] for r in recovered} == before
            assert all(r['node_status'] == 'ONLINE' for r in recovered)
            result['checks'].append({'name': 'DN_OFFLINE_AND_RECOVERY_PRESERVE_STOCK', 'status': 'PASS', 'sku_count': 20})
            step(4)
            page.locator('#open-olap').click()
            page.wait_for_selector('#sales-table table')
            assert page.locator('#currency').input_value() == 'VND'
            assert page.locator('#source').input_value() == 'APP_OPERATIONAL'
            page.locator('#portal-navigation a[data-flow-step="0"]').click()
            page.wait_for_function("(sid)=>document.querySelector('#session-id').textContent.includes(sid)", arg=sid)
            assert json.loads(page.evaluate(f'localStorage.getItem({json.dumps(STORAGE)})'))['session_id'] == sid
            result['checks'].append({'name': 'OLAP_DEEPLINK_AND_PERSISTED_SESSION_RETURN', 'status': 'PASS'})
            step(5)
            mined = run('run-demo-mining', 'SUCCESS')
            model = mined['metadata'].get('result', mined['metadata'])
            assert model['selected_k'] == 2
            assert model['persisted_customers'] == 4317
            assert model['selection_mode'] == 'PREDECLARED_RULE'
            assert page.locator('#mining-profile-table tbody tr').count() == 2
            result['checks'].append({'name': 'ACTUAL_FIFTY_FIT_MINING_AND_SNAPSHOT', 'status': 'PASS', 'run_id': mined['run_id'], 'selected_k': model['selected_k'], 'persisted_customers': model['persisted_customers']})
            page.screenshot(path=str(SHOTS / '03_actual_mining.png'), full_page=True)
            page.set_viewport_size({'width': 390, 'height': 844})
            for number in range(7):
                step(number)
                bounds = page.evaluate('({w:innerWidth,sw:document.documentElement.scrollWidth})')
                assert bounds['sw'] <= bounds['w'] + 1, (number, bounds)
            step(3)
            page.screenshot(path=str(SHOTS / '04_mobile_session.png'), full_page=True)
            assert not errors, errors
            result['checks'].append({'name': 'SEVEN_CHAPTERS_MOBILE_FIT_AND_NO_JS_ERRORS', 'status': 'PASS'})
            result['javascript_errors'] = errors
            result['status'] = 'PASS'
            browser.close()
    except Exception as error:
        result['status'] = 'FAIL'
        result['error'] = f'{type(error).__name__}: {error}'
        result['javascript_errors'] = errors
        save()
        raise
    result['finished_at'] = datetime.now(timezone.utc).isoformat()
    save()
    print(json.dumps({'status': result['status'], 'checks': len(result['checks']), 'session_id': result['session_id'], 'idempotency_key': key}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--key')
    main(parser.parse_args().key)
