"""Render current real BI at desktop/mobile; capture and verify bounds/JS errors."""
from pathlib import Path
from datetime import datetime, timezone
import json
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'evidence/revalidation_20261026/bi'


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    report={'checked_at':datetime.now(timezone.utc).isoformat(),'scope':'Real API, no data interception','checks':[],'status':'RUNNING'}
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(channel='chrome',headless=True)
            for width,height in [(1440,1100),(390,844)]:
                page=browser.new_page(viewport={'width':width,'height':height});page.set_default_timeout(90000)
                errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto('http://127.0.0.1:8010/frontend/dashboard.html?ui=danh-live-20261026#bi')
                page.wait_for_selector('#sales-content:not([hidden])');page.wait_for_function('document.querySelector("#data-journey").dataset.current==="bi"')
                for tab in ['sales','inventory','customers']:
                    page.locator('#tab-'+tab).click();page.wait_for_selector('#'+tab+'-content:not([hidden])')
                    assert not errors,errors
                    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'),(tab,width)
                    page.screenshot(path=str(OUT/f'{width}_{tab}.png'),full_page=True)
                    if width==1440:page.screenshot(path=str(OUT/f'preview_{tab}.png'))
                    report['checks'].append({'width':width,'tab':tab,'status':'PASS','javascript_errors':list(errors)})
                page.close()
            browser.close()
        report['status']='PASS'
    except Exception as exc:
        report['status']='FAIL';report['error']=str(exc);raise
    finally:(OUT/'checks.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'status':report['status'],'screens':len(report['checks'])}))


if __name__=='__main__':main()
