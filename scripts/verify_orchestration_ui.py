"""Capture authenticated Airflow screens, without triggering or altering DAGs."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'evidence/danh_integration'


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    result = {'execution': 'REAL_BROWSER_REAL_AIRFLOW',
              'checked_at': datetime.now(timezone.utc).isoformat(), 'checks': []}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=r'C:\Program Files\Google\Chrome\Application\chrome.exe', headless=True)
        page = browser.new_page(viewport={'width': 1600, 'height': 1080})
        page.set_default_timeout(30000)
        page.goto('http://127.0.0.1:18082')
        page.locator('[name=username]').fill('admin')
        page.locator('[name=password]').fill(os.getenv('AIRFLOW_ADMIN_PASSWORD', 'retail-airflow-local-only'))
        page.get_by_role('button', name='Sign in').click()
        page.wait_for_url('http://127.0.0.1:18082/')
        page.get_by_role('link', name='Dags', exact=True).click()
        for name in ('retailpulse_operations', 'retailpulse_historical', 'retailpulse_mining', 'retailpulse_replay'):
            page.get_by_role('link', name=name, exact=True).wait_for()
        page.screenshot(path=str(OUT / 'airflow_dags.png'), full_page=True)
        result['checks'].append({'name': 'AUTHENTICATED_FOUR_DAGS', 'status': 'PASS'})
        page.get_by_role('link', name='retailpulse_historical', exact=True).click()
        page.get_by_role('link', name='mine_customers', exact=True).wait_for()
        page.screenshot(path=str(OUT / 'airflow_historical.png'), full_page=True)
        result['checks'].append({'name': 'HISTORICAL_TASK_OVERVIEW', 'status': 'PASS'})
        evidence = json.loads((ROOT / 'evidence/airflow_historical.json').read_text())
        run_id = evidence['run_id']
        assert evidence['state'] == 'success'
        page.get_by_role('link', name='Runs', exact=True).click()
        page.get_by_role('link', name=run_id, exact=True).wait_for()
        page.get_by_role('link', name=run_id, exact=True).click()
        page.wait_for_url('**/runs/' + run_id)
        page.get_by_role('link', name='mine_customers', exact=True).wait_for()
        page.screenshot(path=str(OUT / 'airflow_successful_run.png'), full_page=True)
        result['checks'].append({'name': 'ACTUAL_SUCCESSFUL_RUN', 'status': 'PASS', 'run_id': run_id})
        page.get_by_role('button', name='Show Graph (Press g)', exact=True).click()
        page.get_by_role('button', name='Collapse Details Panel', exact=True).click()
        page.mouse.move(1400, 30)
        page.wait_for_timeout(500)
        page.screenshot(path=str(OUT / 'airflow_graph.png'), full_page=True)
        result['checks'].append({'name': 'ACTUAL_HISTORICAL_GRAPH', 'status': 'PASS'})
        browser.close()
    (OUT / 'orchestration_browser.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
