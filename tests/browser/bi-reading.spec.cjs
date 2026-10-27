/** Live BI semantics plus one explicitly simulated UI failure, not fabricated pipeline proof. */
const {test,expect}=require('@playwright/test');
const number=value=>new Intl.NumberFormat('vi-VN',{maximumFractionDigits:2}).format(value);
test.beforeEach(async({page})=>{
 await page.goto('/frontend/dashboard.html?ui=danh-live-20261026#bi');
 await expect(page.locator('#sales-content')).toBeVisible();
});
test('default BI isolates official provenance and explains net/return/cancel with actual values',async({page,request})=>{
 await expect(page.locator('#sales-provenance')).toHaveValue('OFFICIAL_UCI');
 const data=await(await request.get('/api/reports/sales?currency=GBP&source=UCI_HISTORICAL&provenance=OFFICIAL_UCI')).json();
 await expect(page.locator('#sales-kpis')).toContainText(number(data.summary.net));
 await expect(page.locator('#sales-scope')).toContainText('UCI chính thức');
 await expect(page.locator('#sales-equation')).toContainText('Đơn hủy');
 expect(data.summary.gross-data.summary.refunds).toBeCloseTo(data.summary.net,2);
 await page.locator('#sales-kpis .metric-help summary').first().click();
 await expect(page.locator('#sales-kpis .metric-help[open]')).toContainText('Giá trị mua trừ giá trị hoàn trả');
 await expect(page.locator('#bi-notes')).toHaveCount(0);
 await expect(page.locator('#sales-kpis')).not.toContainText('Thầy hỏi');
 await expect(page.locator('#dj-bi-evidence')).not.toHaveAttribute('open','');
});
test('App DEMO keeps cancellation separate and invalid dates do not leave stale visible KPIs',async({page,request})=>{
 await page.locator('#sales-source').selectOption('APP_OPERATIONAL');
 await expect(page.locator('#sales-provenance')).toHaveValue('DEMO');
 await expect(page.locator('#sales-currency')).toHaveValue('VND');
 await page.locator('#sales-filters button[type=submit]').click();
 const data=await(await request.get('/api/reports/sales?currency=VND&source=APP_OPERATIONAL&provenance=DEMO')).json();
 await expect(page.locator('#sales-equation')).toContainText(number(data.summary.cancelled));
 await expect(page.locator('#sales-kpis')).toContainText(number(data.summary.net));
 await page.locator('#sales-start').fill('2026-10-26');await page.locator('#sales-end').fill('2020-01-01');
 await page.locator('#sales-filters button[type=submit]').click();
 await expect(page.locator('#sales-content')).toBeHidden();
 await expect(page.locator('#report-message')).toContainText('Ngày bắt đầu');
});
test('inventory warns on old snapshots while distinguishing connection from freshness',async({page,request})=>{
 const data=await(await request.get('/api/reports/inventory')).json();
 await page.locator('#tab-inventory').click();await expect(page.locator('#inventory-content')).toBeVisible();
 await expect(page.locator('#inventory-kpis')).toContainText('Chi nhánh có dữ liệu cũ');
 if(data.summary.stale_branches>0)await expect(page.locator('#inventory-warning')).toContainText('24 giờ');
 await expect(page.locator('#inventory-branches')).toContainText('Nguồn chụp dữ liệu');
 await expect(page.locator('#inventory-branches')).toContainText('Hệ thống thu thập');
});
test('customer model, cohort chart and filtered KPI remain explicitly distinguished on mobile',async({page,request})=>{
 await page.locator('#tab-customers').click();await expect(page.locator('#customers-content')).toBeVisible();
 const run=await page.locator('#customers-model').inputValue();
 const data=await(await request.get('/api/reports/customers?run_id='+encodeURIComponent(run))).json();
 await expect(page.locator('#segment-donut')).toContainText(number(data.summary.customers));
 const cluster=String(data.profiles[0].cluster_id);
 await page.locator('#customers-cluster').selectOption(cluster);await page.locator('#customers-filters button[type=submit]').click();
 const filtered=await(await request.get('/api/reports/customers?run_id='+encodeURIComponent(run)+'&cluster='+cluster)).json();
 await expect(page.locator('#customers-kpis')).toContainText(number(filtered.summary.customers));
 await expect(page.locator('#segment-donut')).toContainText(number(data.summary.customers));
 await page.setViewportSize({width:390,height:844});
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
 await expect(page.locator('#segment-scatter')).toContainText('Bao lâu chưa mua');
});
test('UI error contract only: a 503 hides old values and real retry recovers',async({page})=>{
 await page.route('**/api/reports/sales?**',r=>r.fulfill({status:503,json:{detail:'Audit simulated UI failure'}}));
 await page.locator('#refresh-report').click();
 await expect(page.locator('#sales-content')).toBeHidden();await expect(page.locator('#report-message')).toContainText('Audit simulated');
 await page.unroute('**/api/reports/sales?**');await page.locator('#retry-report').click();
 await expect(page.locator('#sales-content')).toBeVisible();
});

test('UI state contract only: failed mining does not replace the last successful model',async({page})=>{
 await page.goto('/frontend/customer-segments.html?ui=danh-live-20261026#mining');
 await expect(page.locator('#dj-profiles tbody tr')).not.toHaveCount(0);
 const previous=await page.locator('#dj-model').inputValue();
 const fake='ui-contract-failed-mining';
 await page.route('**/api/runs',r=>r.request().method()==='POST'?r.fulfill({status:202,json:{run_id:fake,status:'PENDING'}}):r.continue());
 await page.route('**/api/runs/'+fake,r=>r.fulfill({status:200,json:{run_id:fake,kind:'mining',status:'FAILED',error:'UI failure contract only',metadata:{},events:[]}}));
 await page.locator('[data-dj-action="mining-run"]').click();
 await expect(page.locator('#dj-message')).toContainText('FAILED');
 await expect(page.locator('#dj-message')).toContainText('không phải kết quả của run lỗi');
 await expect(page.locator('#dj-model')).toHaveValue(previous);
 await expect(page.locator('#dj-model-meta')).toContainText(previous);
 await expect(page.locator('#dj-model-meta')).not.toContainText(fake);
});
