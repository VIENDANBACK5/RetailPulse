"""Real-browser checks for the shared live portal shell, without synthetic data."""
raise SystemExit('RETIRED: old portal removed. Run python scripts/verify_danh_frontend.py instead.')
from pathlib import Path
import json
from datetime import datetime, timezone
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'evidence/unified_portal'
PAGES = ['index.html', 'etl-monitor.html', 'dashboard.html', 'customer-segments.html', 'reports.html', 'operations.html']


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    result = {'execution': 'REAL_BROWSER_REAL_API', 'checked_at': datetime.now(timezone.utc).isoformat(), 'checks': []}
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='chrome', headless=True)
        for width, height in [(1440, 1000), (390, 844)]:
            page = browser.new_page(viewport={'width': width, 'height': height})
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            for filename in PAGES:
                page.goto('http://127.0.0.1:8010/frontend/' + filename)
                page.wait_for_selector('.portal-header')
                page.wait_for_function("!document.querySelector('#connection').innerText.includes('Đang kiểm tra')")
                assert page.locator('#portal-navigation [data-flow-step]').count() == 7
                assert page.locator('link[href="css/portal.css"]').count() == 1
                assert page.locator('#portal-footer footer').count() == 1
                if width < 1024:
                    menu = page.locator('.portal-menu')
                    menu.click()
                    assert menu.get_attribute('aria-expanded') == 'true'
                    assert page.locator('#portal-navigation').is_visible()
                    page.keyboard.press('Escape')
                    assert menu.get_attribute('aria-expanded') == 'false'
                if filename == 'reports.html':
                    page.wait_for_selector('#sales-month-table table', state='attached', timeout=60000)
                    page.locator('#tab-inventory').click()
                    page.wait_for_selector('#inventory-table table', timeout=60000)
                    page.locator('#tab-customers').click()
                    page.wait_for_selector('#segment-profiles table', timeout=60000)
                    page.locator('#tab-sales').click()
                    page.wait_for_selector('#sales-content:not([hidden])', timeout=60000)
                if filename == 'etl-monitor.html':
                    page.wait_for_selector('#sources table', timeout=60000)
                    page.wait_for_selector('#runs table', timeout=60000)
                if filename == 'dashboard.html':
                    page.wait_for_selector('#sales-table table', timeout=60000)
                    page.wait_for_selector('#inventory table', timeout=60000)
                if filename == 'customer-segments.html':
                    page.wait_for_selector('#profiles table', timeout=60000)
                    page.wait_for_selector('#models details', timeout=60000)
                page.screenshot(path=str(OUT / f'{width}_{filename[:-5]}.png'), full_page=True)
                bounds = page.evaluate('''()=>({viewport:innerWidth,document:document.documentElement.scrollWidth,
                    font:getComputedStyle(document.body).fontFamily,header:getComputedStyle(document.querySelector('.portal-header')).backgroundColor})''')
                assert bounds['document'] <= bounds['viewport'] + 1, (filename, bounds)
                assert not errors, (filename, errors)
                result['checks'].append({'page': filename, 'width': width, 'status': 'PASS', **bounds})
            page.close()
        browser.close()
    result['status'] = 'PASS'
    (OUT / 'browser_checks.json').write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f"Shared portal: {len(result['checks'])} desktop/mobile checks PASS")


if __name__ == '__main__':
    main()
