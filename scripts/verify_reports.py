"""Real-browser acceptance for the integrated Danh reporting portal."""
from pathlib import Path
import json
from datetime import datetime, timezone
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'evidence' / 'danh_integration'

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    result = {'execution': 'REAL_BROWSER_REAL_DWH', 'checked_at': datetime.now(timezone.utc).isoformat(), 'checks': []}
    errors = []
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=r'C:\Program Files\Google\Chrome\Application\chrome.exe', headless=True)
        page = browser.new_page(viewport={'width': 1440, 'height': 1000})
        page.set_default_timeout(60000)
        page.on('pageerror', lambda exc: errors.append(str(exc)))
        page.goto('http://127.0.0.1:8001/frontend/reports.html')
        page.wait_for_url('http://127.0.0.1:8010/frontend/reports.html')
        page.wait_for_selector('#sales-content:not([hidden])')
        assert page.locator('#sales-month-table tbody tr').count() > 0
        assert page.locator('#sales-kpis').inner_text()
        result['checks'].append({'name': 'SALES_REAL_CROSS_ORIGIN_AND_REDIRECT', 'status': 'PASS'})
        page.screenshot(path=str(OUT / 'reports_sales.png'), full_page=True)
        page.locator('#sales-currency').select_option('VND')
        with page.expect_response(lambda r: '/analytics/sales?' in r.url and 'currency=VND' in r.url) as response:
            page.locator('#sales-filters button[type=submit]').click()
        payload = response.value.json()
        assert response.value.status == 200
        assert payload['currency'] == 'VND'
        assert payload['summary']['row_count'] > 0
        page.wait_for_selector('#sales-content:not([hidden])')
        result['checks'].append({'name': 'CURRENCY_FILTER', 'status': 'PASS', 'rows': payload['summary']['row_count']})
        with page.expect_download() as download:
            page.locator('[data-export=sales]').click()
        download.value.save_as(str(OUT / 'sales_export.csv'))
        result['checks'].append({'name': 'ACTUAL_CSV_EXPORT', 'status': 'PASS'})
        page.locator('#tab-inventory').click()
        page.wait_for_selector('#inventory-content:not([hidden])')
        assert page.locator('#inventory-table tbody tr').count() > 0
        page.screenshot(path=str(OUT / 'reports_inventory.png'), full_page=True)
        result['checks'].append({'name': 'INVENTORY_CURRENT_AND_LAST_KNOWN', 'status': 'PASS'})
        page.locator('#tab-customers').click()
        page.wait_for_selector('#customers-content:not([hidden])')
        assert page.locator('#customers-run').inner_text()
        page.screenshot(path=str(OUT / 'reports_customers.png'), full_page=True)
        result['checks'].append({'name': 'SUCCESSFUL_CUSTOMER_RUN', 'status': 'PASS'})
        assert not errors, errors
        result['checks'].append({'name': 'NO_JAVASCRIPT_RUNTIME_ERRORS', 'status': 'PASS'})
        browser.close()
    (OUT / 'reports_browser.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))

if __name__ == '__main__':
    main()
