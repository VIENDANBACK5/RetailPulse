"""Verify the exact branch frontend and render it; do not claim simulated controls execute ETL."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import subprocess
import requests
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'evidence/exact_danh_frontend'
BASE = 'http://127.0.0.1:8010'
REF = 'origin/danh'


def main():
    if (ROOT/'frontend/js/journey.js').exists():
        raise SystemExit('The original Danh baseline is now intentionally extended. Run scripts/verify_danh_live_journey.py; old byte-identical evidence remains under evidence/exact_danh_frontend/.')
    OUT.mkdir(parents=True, exist_ok=True)
    commit = subprocess.check_output(['git', 'rev-parse', REF], cwd=ROOT, text=True).strip()
    paths = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', REF, 'frontend'], cwd=ROOT, text=True).splitlines()
    actual = sorted(p.relative_to(ROOT).as_posix() for p in (ROOT/'frontend').rglob('*') if p.is_file())
    assert actual == sorted(paths), 'Frontend contains missing or additional files'
    report = {'checked_at': datetime.now(timezone.utc).isoformat(), 'ref': REF, 'commit': commit,
              'scope': 'Exact branch bytes, HTTP serving and visual render; NOT ETL/ML execution', 'files': [], 'pages': [], 'status': 'RUNNING'}
    try:
        for name in paths:
            expected = subprocess.check_output(['git', 'show', f'{REF}:{name}'], cwd=ROOT)
            assert (ROOT/name).read_bytes() == expected, name
            response = requests.get(BASE+'/'+name, timeout=20)
            assert response.status_code == 200 and response.content == expected, name
            report['files'].append({'path': name, 'sha256': hashlib.sha256(expected).hexdigest(), 'status': 'PASS'})
        with sync_playwright() as p:
            browser = p.chromium.launch(channel='chrome', headless=True)
            for name in ['index', 'dashboard', 'etl-monitor', 'customer-segments', 'operations']:
                page = browser.new_page(viewport={'width': 1440, 'height': 1000})
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto(BASE+f'/frontend/{name}.html?source=danh-{commit[:7]}')
                if name == 'index':
                    page.wait_for_selector('#page-loader', state='hidden', timeout=30000)
                if name == 'dashboard':
                    page.wait_for_selector('#sales-content:not([hidden])', timeout=45000)
                page.screenshot(path=str(OUT/f'{name}.png'), full_page=True)
                report['pages'].append({'path': name, 'title': page.title(), 'javascript_errors': errors,
                                        'status': 'PASS' if not errors else 'FAIL'})
                assert not errors, (name, errors)
                page.close()
            browser.close()
        report['status'] = 'PASS'
    except Exception as exc:
        report['status'] = 'FAIL'
        report['error'] = str(exc)
        raise
    finally:
        (OUT/'checks.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'status': report['status'], 'commit': commit, 'exact_files_served': len(paths), 'rendered_pages': len(report['pages'])}))


if __name__ == '__main__':
    main()
