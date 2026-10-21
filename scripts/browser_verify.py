"""Actual Chromium UI integration, SQL-backed OLAP and backend run evidence.

Requires playwright Python package and an installed Chromium-family browser.
Runs app/API ETL only, never reloads the million-row historical source.
"""
import argparse
import json
from pathlib import Path
import time
import requests
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
BASE='http://127.0.0.1:8010'
EVIDENCE=ROOT/'evidence'/'screenshots'


def main(no_etl=False):
    EVIDENCE.mkdir(parents=True,exist_ok=True)
    result={'execution':'REAL_BROWSER','checks':[],'screenshots':[]}
    errors=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path=r'C:\Program Files\Google\Chrome\Application\chrome.exe',headless=True)
        page=browser.new_page(viewport={'width':1440,'height':1050},device_scale_factor=1)
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.set_default_timeout(120000)
        page.goto(BASE+'/frontend/index.html')
        page.wait_for_function("document.getElementById('connection').textContent.includes('connected')")
        page.screenshot(path=str(EVIDENCE/'01_overview.png'),full_page=True)
        result['screenshots'].append('evidence/screenshots/01_overview.png')
        page.goto(BASE+'/frontend/etl-monitor.html')
        page.wait_for_selector('#runs table')
        if not no_etl:
            page.locator('[name=source][value=uci]').uncheck()
            with page.expect_response(lambda r:r.url.endswith('/api/runs') and r.request.method=='POST') as response:
                page.locator('#run-etl').click()
            payload=response.value.json()
            assert response.value.status==202,payload
            run_id=payload['run_id']
            deadline=time.monotonic()+180
            while time.monotonic()<deadline:
                run=requests.get(BASE+'/api/runs/'+run_id,timeout=20).json()
                if run['status'] in ['SUCCESS','PARTIAL','FAILED','BLOCKED']:break
                time.sleep(1)
            assert run['status']=='SUCCESS',run
            page.locator('[data-run="'+run_id+'"]').click()
            page.wait_for_function("document.querySelector('#selected-status').textContent.includes('SUCCESS')")
            page.wait_for_selector('#reconciliation table')
            assert 'MATCHED' in page.locator('#reconciliation').inner_text()
            result['checks'].append({'name':'UI_ETL_REAL_RUN','status':'PASS','run_id':run_id,'batch_id':run['metadata'].get('batch_id')})
            page.locator('[data-records=rejected]').click()
            page.locator('[data-records=sales]').click()
            page.wait_for_selector('#run-records table')
        page.screenshot(path=str(EVIDENCE/'02_etl_real_run.png'),full_page=True)
        result['screenshots'].append('evidence/screenshots/02_etl_real_run.png')
        page.goto(BASE+'/frontend/dashboard.html')
        page.wait_for_selector('#sales-table table')
        page.locator('#currency').select_option('GBP')
        page.locator('#grain').select_option('month')
        with page.expect_response(lambda r:'/api/analytics/sales?' in r.url) as gbp_response:
            page.locator('#apply-filters').click()
        gbp_payload=gbp_response.value.json()
        assert gbp_payload['rows'] and all(row['currency']=='GBP' for row in gbp_payload['rows']),gbp_payload
        result['checks'].append({'name':'OLAP_GBP_MONTH_CURRENCY_SELECTION','status':'PASS'})
        page.locator('#currency').select_option('VND')
        page.locator('#grain').select_option('day')
        with page.expect_response(lambda r:'/api/analytics/sales?' in r.url):page.locator('#apply-filters').click()
        page.wait_for_selector('#sales-chart .bar-row')
        result['checks'].append({'name':'OLAP_DAY_SLICE_CURRENCY','status':'PASS'})
        page.locator('#pivot').select_option('product')
        with page.expect_response(lambda r:'/api/analytics/sales?' in r.url):page.locator('#apply-filters').click()
        page.wait_for_selector('#sales-table table')
        with page.expect_response(lambda r:'/api/analytics/pivot?' in r.url):page.locator('#pivot-table').click()
        page.wait_for_selector('#cross-tab table')
        with page.expect_response(lambda r:'/api/analytics/sales/details?' in r.url):page.locator('#drill-through').click()
        page.wait_for_selector('#sales-details table')
        page.locator('#sales-details [data-trace]').first.click()
        page.wait_for_selector('#sales-details-lineage pre')
        assert 'source_record_id' in page.locator('#sales-details-lineage').inner_text()
        result['checks'].append({'name':'OLAP_PIVOT_DRILLTHROUGH_LINEAGE','status':'PASS'})
        page.screenshot(path=str(EVIDENCE/'03_olap_real_warehouse.png'),full_page=True)
        result['screenshots'].append('evidence/screenshots/03_olap_real_warehouse.png')
        page.goto(BASE+'/frontend/customer-segments.html')
        page.wait_for_function("!document.getElementById('models').innerText.includes('Đang tải')")
        page.wait_for_timeout(1500)
        page.screenshot(path=str(EVIDENCE/'04_mining_registry.png'),full_page=True)
        result['screenshots'].append('evidence/screenshots/04_mining_registry.png')
        browser.close()
    assert not errors,errors
    result['javascript_errors']=errors
    result['status']='PASS'
    (ROOT/'evidence'/'browser_verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--no-etl',action='store_true')
    main(parser.parse_args().no_etl)
