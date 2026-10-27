"""Click Danh's actual pages through seven nodes, including real upload/ETL/ML.

Uses a labelled, constant UCI-schema UNVERIFIED/GBP fixture and resumes the
existing audited DEMO OLTP session. No deletion/reset, mocked metrics or statuses.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import requests
import sys
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'evidence/danh_live_journey'
BASE='http://127.0.0.1:8010'
CSV=b'Invoice,StockCode,Description,Quantity,InvoiceDate,Price,Customer ID,Country\nDJ-UPLOAD-BUY,DJ-UPLOAD-SKU,DEMO file fixture,2,2011-01-01,5,DJ-UPLOAD-CUSTOMER,DEMO\nC-DJ-UPLOAD-RETURN,DJ-UPLOAD-SKU,DEMO file fixture,-1,2011-01-02,2,DJ-UPLOAD-CUSTOMER,DEMO\nDJ-UPLOAD-BAD,DJ-UPLOAD-SKU,DEMO invalid fixture,bad,2011-01-03,5,DJ-UPLOAD-CUSTOMER,DEMO\n'


def get(path):
    response=requests.get(BASE+'/api'+path,timeout=90)
    response.raise_for_status()
    return response.json()


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    prior=json.loads((ROOT/'evidence/live_demo_ui.json').read_text(encoding='utf-8'))
    state={'sessionKey':prior['idempotency_key'],'sessionId':prior['session_id']}
    report={'started_at':datetime.now(timezone.utc).isoformat(),'execution':'REAL_BROWSER_HTTP_SQL_MINIO_ML',
            'source_fixture':{'name':'demo_journey_upload.csv','sha256':hashlib.sha256(CSV).hexdigest(),
                              'provenance':'UNVERIFIED','currency':'GBP','rows':3,'expected_valid':2,'expected_rejected':1},
            'checks':[],'runs':{},'status':'RUNNING'}
    def save(): (OUT/'live_checks.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    def passed(name,**values):
        report['checks'].append({'name':name,'status':'PASS',**values});save();print(name+': PASS',flush=True)
    if '--resume-tail' not in sys.argv:save()
    if '--resume-tail' in sys.argv:
        report=json.loads((OUT/'live_checks.json').read_text(encoding='utf-8'))
        (OUT/'failed_hidden_refresh_test.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        report.update(status='RUNNING',resumed_at=datetime.now(timezone.utc).isoformat(),resume_reason='Test tried a technical control hidden in BI; open Mining before refreshing')
        report.pop('error',None)
        state.update(etlRun=report['runs']['replay'],modelRun=report['runs']['mining-run'])
    errors=[]
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(channel='chrome',headless=True)
            context=browser.new_context(viewport={'width':1440,'height':1000})
            context.add_init_script('if(!localStorage.getItem("retailpulse-danh-journey-v1")) localStorage.setItem("retailpulse-danh-journey-v1",'+json.dumps(json.dumps(state))+');')
            page=context.new_page();page.set_default_timeout(90000)
            page.on('pageerror',lambda error:errors.append(str(error)))
            def ready(): page.wait_for_function('document.querySelector("#dj-context")?.textContent.includes("ETL:")')
            def click(action):
                page.locator('[data-dj-action="'+action+'"]').click()
                report.setdefault('clicked_actions',[]).append(action)
            def node(identifier):
                page.locator('[data-dj-sidebar="'+identifier+'"]').click();ready()
                page.wait_for_selector('[data-dj-node="'+identifier+'"]:not([hidden])')
            def run(action,expected='SUCCESS'):
                with page.expect_response(lambda r:r.url.endswith('/api/runs') and r.request.method=='POST') as trigger:
                    click(action)
                response=trigger.value;assert response.status==202,response.text()
                rid=response.json()['run_id'];report['runs'][action]=rid;save()
                page.wait_for_function('''({id,status})=>document.querySelector('#dj-run-status').textContent.includes(id)
                    &&document.querySelector('#dj-run-status').textContent.includes(status)
                    && !document.querySelector('[data-dj-action="refresh"]').disabled''',arg={'id':rid,'status':expected},timeout=300000)
                record=get('/runs/'+rid);assert record['status']==expected
                return record['metadata'].get('result',record['metadata'])

            if '--resume-tail' in sys.argv:
                page.goto(BASE+'/frontend/dashboard.html#bi');ready()
            else:
                page.goto(BASE+'/frontend/index.html?ui=danh-live-20261025')
                page.wait_for_selector('#page-loader',state='hidden')
                # Actual user entry point: customer link must stay within Danh's own page/shell.
                page.locator('a[href*="customer-segments.html"]').first.click();ready()
                assert page.url.startswith(BASE+'/frontend/customer-segments.html')
                assert page.locator('#portal-shell').count()==0
                assert page.locator('.workspace-sidebar').count()==1
                assert page.locator('link[href*="css/workspace.css"]').count()==1
                passed('CUSTOMER_LINK_SAME_ORIGIN_DANH_SHELL',url=page.url)

                node('source')
                click('official');page.wait_for_selector('#dj-official pre')
                assert 'OFFICIAL_UCI' in page.locator('#dj-official').inner_text()
                click('configured-file')
                assert page.evaluate('JSON.parse(localStorage.getItem("retailpulse-danh-journey-v1")).filePath===undefined')
                click('upload')
                page.wait_for_function('document.querySelector("#dj-message").classList.contains("error")')
                for source in ['uci','app','api']:page.locator('#dj-src-'+source).uncheck()
                click('collect')
                page.wait_for_function('document.querySelector("#dj-message").classList.contains("error")')
                for source in ['app','api']:page.locator('#dj-src-'+source).check()
                passed('INPUT_GUARDS_NO_FILE_AND_NO_SELECTED_SOURCE')
                with page.expect_response(lambda r:'/api/journey/sources/app' in r.url) as db:
                    click('preview-db')
                assert db.value.json()['record_count']>0
                click('preview-api');page.wait_for_selector('#dj-api-preview pre')
                assert len(json.loads(page.locator('#dj-api-preview pre').inner_text())['branches'])==3
                click('prepare');page.wait_for_function('document.querySelector("#dj-session-label").textContent.includes("demo-")')
                passed('SQL_AND_HTTP_SOURCE_PREVIEWS_AND_EXISTING_DEMO_SESSION')

                page.locator('#dj-file').set_input_files({'name':'demo_journey_upload.csv','mimeType':'text/csv','buffer':CSV})
                with page.expect_response(lambda r:'/api/journey/files?' in r.url) as uploaded:
                    click('upload')
                intake=uploaded.value.json();assert uploaded.value.status==201
                assert intake['checksum']==report['source_fixture']['sha256'] and intake['provenance']=='UNVERIFIED'
                page.wait_for_selector('#dj-file-preview tbody tr')
                assert page.locator('#dj-file-preview tbody tr').count()==3
                passed('CSV_UPLOAD_PREVIEW_CHECKSUM_AND_UNVERIFIED_LABEL',file_path=intake['file_path'])
                loaded=run('collect')
                assert set(loaded['sources'])=={'uci','app','api'}
                assert loaded['sources']['uci']['valid_count']==2 and loaded['sources']['uci']['rejected_count']==1
                passed('THREE_SOURCE_REAL_ETL_WITH_VALID_AND_REJECTED',counts=loaded['counts'])
                page.screenshot(path=str(OUT/'01_sources.png'),full_page=True)

                node('raw');page.wait_for_selector('#dj-raw-manifests tbody tr')
                click('raw')
                assert page.locator('#dj-raw-manifests tbody tr').count()==3
                manifests=get('/journey/manifests?run_id='+report['runs']['collect'])
                for manifest in manifests:
                    payload=requests.get(BASE+'/api/journey/download',params={'path':manifest['raw_path']},timeout=30)
                    assert payload.status_code==200
                    assert hashlib.sha256(payload.content).hexdigest()==manifest['checksum']
                    assert manifest['metadata']['lake_uri'].startswith('s3://')
                page.locator('[data-raw-path]').first.click();page.wait_for_selector('#dj-raw-preview pre')
                with page.expect_download() as download:
                    page.locator('#dj-raw-links a').first.click()
                assert download.value.failure() is None
                assert hashlib.sha256(Path(download.value.path()).read_bytes()).hexdigest()==manifests[0]['checksum']
                passed('THREE_RAW_FILES_DOWNLOAD_SHA256_AND_MINIO_MANIFEST')

                node('etl');page.wait_for_selector('#dj-transform tbody tr');page.wait_for_selector('#dj-rejected tbody tr')
                assert page.locator('#dj-rejected tbody tr').count()==1
                assert 'Invalid quantity' in page.locator('#dj-rejected').inner_text()
                assert 'CANCELLATION' in page.locator('#dj-transform').inner_text()
                options=page.locator('#dj-record option').all_text_contents()
                assert any('DJ-UPLOAD-BUY' in text for text in options)
                selected=next(o.get_attribute('value') for o in page.locator('#dj-record option').all() if 'DJ-UPLOAD-BUY' in o.inner_text())
                page.locator('#dj-record').select_option(selected);click('transform')
                page.wait_for_function('document.querySelectorAll("#dj-transform tbody tr").length===1')
                assert 'GBP' in page.locator('#dj-transform').inner_text()
                cells=page.locator('#dj-transform tbody tr').first.locator('td').all_text_contents()
                assert cells[1:3]==['2','5'],cells
                passed('SELECT_RECORD_RAW_TO_FACT_AND_REAL_REJECTION')
                page.screenshot(path=str(OUT/'03_transform.png'),full_page=True)

                node('dwh');page.wait_for_selector('#dj-reconciliation tbody tr')
                click('warehouse')
                assert 'MATCHED' in page.locator('#dj-reconciliation').inner_text()
                page.wait_for_function('document.querySelector("#dj-session-kpis").textContent.includes("325.000")')
                replay=run('replay')
                for src in ['uci','app']:
                    counts=replay['sources'][src]['counts'];assert counts['inserted']==counts['updated']==0
                passed('WAREHOUSE_DIMENSIONS_SQL_RECONCILIATION_AND_FROZEN_REPLAY',counts=replay['counts'])

                node('mining');page.wait_for_selector('#dj-profiles tbody tr')
                click('mining-read')
                assert page.locator('#dj-model-k tbody tr').count()>=2
                click('customer');page.wait_for_selector('#dj-cust-features tbody tr')
                assert page.locator('#dj-cust-transactions tbody tr').count()>0
                customer=get('/journey/mining/'+page.locator('#dj-model').input_value()+'/customer?customer_key='+page.locator('#dj-customer').input_value())
                for feature in ['recency','frequency','monetary']:
                    assert abs(float(customer['rfm'][feature])-float(customer['segment'][feature]))<0.0001
                passed('CUSTOMER_TRANSACTIONS_RFM_STANDARDIZATION_AND_PERSISTED_CLUSTER')
                mined=run('mining-run')
                assert mined['rfm_sql_python_verified'] and mined['segment_readback_verified']
                assert mined['selection_mode']=='PREDECLARED_RULE'
                passed('REAL_MINING_SELECTION_EVALUATION_AND_READBACK',selected_k=mined['selected_k'],customers=mined['persisted_customers'])
                for path in mined['artifact_paths']:
                    response=requests.get(BASE+'/api/artifacts',params={'path':path},timeout=30)
                    assert response.status_code==200 and response.content,path
                    assert hashlib.sha256(response.content).hexdigest()==hashlib.sha256((ROOT/path).read_bytes()).hexdigest(),path
                passed('ALL_MODEL_ARTIFACT_DOWNLOADS_MATCH_LOCAL_BYTES',artifacts=len(mined['artifact_paths']))
                page.screenshot(path=str(OUT/'06_mining.png'),full_page=True)

                node('olap');page.locator('#dj-source').select_option('APP_OPERATIONAL')
                totals=[]
                for grain in ['year','quarter','month','day']:
                    page.locator('#dj-grain').select_option(grain)
                    with page.expect_response(lambda r:'/api/analytics/sales?' in r.url) as rollup:
                        click('olap')
                    payload=rollup.value.json()
                    assert rollup.value.status==200,payload
                    rows=payload['rows']
                    totals.append(sum(float(row['net_sales']) for row in rows))
                assert max(totals)-min(totals)<.01,totals
                passed('ALL_FOUR_TIME_GRAINS_PRESERVE_NET_SALES',totals=totals)
                page.locator('#dj-grain').select_option('day');click('olap');page.wait_for_selector('#dj-olap-output table')
                assert 'VND' in page.locator('#dj-olap-output').inner_text()
                click('pivot');page.wait_for_function('document.querySelector("#dj-sql").textContent.includes("2000")')
                click('details');page.wait_for_selector('[data-lineage]')
                page.locator('[data-lineage]').first.click();page.wait_for_selector('#dj-lineage pre')
                assert 'raw_record' in page.locator('#dj-lineage').inner_text()
                passed('OLAP_FILTER_GRAIN_PIVOT_DRILLTHROUGH_AND_RAW')

                node('bi');page.locator('#dj-bi-evidence > summary').click();page.wait_for_selector('#dj-bi-inventory tbody tr')
                click('bi')
                before={r['stock_code']:r['stock_on_hand'] for r in get('/analytics/inventory') if r['branch_code']=='DN'}
                page.locator('[data-dj-action="outage"]').locator('..').locator('summary').click()
                run('outage','PARTIAL')
                offline=[r for r in get('/analytics/inventory') if r['branch_code']=='DN']
                assert {r['stock_code']:r['stock_on_hand'] for r in offline}==before
                assert all(r['node_status']=='OFFLINE' for r in offline)
                run('recover')
                assert all(r['node_status']=='ONLINE' for r in get('/analytics/inventory') if r['branch_code']=='DN')
                passed('BI_REAL_DATA_SOURCE_OUTAGE_AND_RECOVERY_PRESERVES_STOCK')
            node('mining')
            click('refresh');page.wait_for_function('!document.querySelector("[data-dj-action=refresh]").disabled')
            node('bi');page.locator('#dj-bi-evidence > summary').click()
            page.screenshot(path=str(OUT/'07_bi.png'),full_page=True)

            page.set_viewport_size({'width':390,'height':844})
            for identifier,_,_,_ in [('source',0,0,0),('raw',0,0,0),('etl',0,0,0),('dwh',0,0,0),('olap',0,0,0),('mining',0,0,0),('bi',0,0,0)]:
                page.locator('#sidebar-toggle').click();node(identifier)
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'),identifier
            passed('ALL_SEVEN_NODES_MOBILE_DANH_NAVIGATION_NO_OVERFLOW')
            page.screenshot(path=str(OUT/'08_mobile.png'),full_page=True)
            assert not errors,errors
            passed('NO_BROWSER_JAVASCRIPT_ERRORS_AND_NO_CACHE_HEADER',header=requests.get(BASE+'/frontend/customer-segments.html').headers.get('Cache-Control'))
            expected={'preview-db','preview-api','prepare','upload','configured-file','official','collect','raw','transform','warehouse','olap','pivot','details','replay','mining-read','mining-run','customer','bi','outage','recover','refresh'}
            assert expected<=set(report['clicked_actions']),expected-set(report['clicked_actions'])
            report['action_coverage']={'exercised':len(expected),'total':len(expected),'actions':sorted(expected)}
            report['status']='PASS';browser.close()
    except Exception as exc:
        report['status']='FAIL';report['error']=str(exc);report['javascript_errors']=errors;raise
    finally: report['finished_at']=datetime.now(timezone.utc).isoformat();save()
    print(json.dumps({'status':report['status'],'checks':len(report['checks']),'runs':report['runs']}),flush=True)


if __name__=='__main__':main()
