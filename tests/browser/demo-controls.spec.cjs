/** Exercise real report controls and validate their returned populations/downloads. */
const {test,expect}=require('@playwright/test');
const fs=require('node:fs');
const number=x=>new Intl.NumberFormat('vi-VN',{maximumFractionDigits:2}).format(x);
async function responseTo(page,kind,action){
 const pending=page.waitForResponse(r=>r.url().includes('/api/reports/'+kind+'?')&&r.request().method()==='GET');
 await action();const r=await pending;expect(r.ok()).toBeTruthy();
 const d=await r.json();await expect(page.locator('#'+kind+'-content')).toBeVisible();return d;
}
async function csv(page,kind){
 const pending=page.waitForEvent('download');await page.locator('[data-export="'+kind+'"]').click();
 const d=await pending;expect(await d.failure()).toBeNull();
 expect(d.suggestedFilename()).toContain('RetailPulse-'+kind+'-');
 return fs.readFileSync(await d.path(),'utf8');
}
test.beforeEach(async({page})=>{
 await page.goto('/frontend/dashboard.html#bi');await expect(page.locator('#sales-content')).toBeVisible();
});
test('sales refresh, chart month, branch drill, reset, CSV and audit controls',async({page})=>{
 const d=await responseTo(page,'sales',()=>page.locator('#refresh-report').click());
 expect(d.summary.gross-d.summary.refunds).toBeCloseTo(d.summary.net,2);
 const output=await csv(page,'sales');expect(output).toContain('Giá trị sau hoàn');
 expect(output).toContain(String(d.monthly[0].year_month));
 const month=await page.locator('[data-month]').first().getAttribute('data-month');
 const monthly=await responseTo(page,'sales',()=>page.locator('[data-month]').first().click());
 expect(monthly.monthly.every(r=>r.year_month===month)).toBeTruthy();
 await expect(page.locator('#sales-start')).toHaveValue(month+'-01');
 const branch=await page.locator('[data-branch]').first().getAttribute('data-branch');
 const byBranch=await responseTo(page,'sales',()=>page.locator('[data-branch]').first().click());
 expect(byBranch.branches.every(r=>r.branch_code===branch)).toBeTruthy();
 await responseTo(page,'sales',()=>page.locator('#sales-filters [type=reset]').click());
 await expect(page.locator('#sales-start')).toHaveValue('');
 await expect(page.locator('#sales-provenance')).toHaveValue('OFFICIAL_UCI');
 await page.locator('#system-status > summary').click();await expect(page.locator('#audit-table table')).toBeVisible();
});
test('inventory health, branch, search, pagination, reset and exported page',async({page})=>{
 await responseTo(page,'inventory',()=>page.locator('#tab-inventory').click());
 const next=page.locator('#inventory-pagination [data-page="2"]');
 await responseTo(page,'inventory',()=>next.click());
 const output=await csv(page,'inventory');expect(output).toContain('Snapshot');
 await page.locator('#inventory-health').selectOption('low');
 const low=await responseTo(page,'inventory',()=>page.locator('#inventory-filters [type=submit]').click());
 expect(low.items.every(r=>r.node_status==='ONLINE'&&r.stock_on_hand<=10)).toBeTruthy();
 await page.locator('#inventory-branch').selectOption('HN');
 const hn=await responseTo(page,'inventory',()=>page.locator('#inventory-filters [type=submit]').click());
 expect(hn.items.every(r=>r.branch_code==='HN')).toBeTruthy();
 const empty=await responseTo(page,'inventory',()=>page.locator('#inventory-search').fill('NO_SUCH_SKU_DEMO_AUDIT'));
 expect(empty.total).toBe(0);await expect(page.locator('#inventory-table')).toContainText('Không có dữ liệu');
 const reset=await responseTo(page,'inventory',()=>page.locator('#inventory-filters [type=reset]').click());
 expect(reset.total).toBeGreaterThan(0);await expect(page.locator('#inventory-search')).toHaveValue('');
});
test('customer chart, profile bars, search, pagination, reset, model and CSV',async({page})=>{
 const all=await responseTo(page,'customers',()=>page.locator('#tab-customers').click());
 expect(all.summary.customers).toBe(all.profiles.reduce((s,p)=>s+p.customers,0));
 await responseTo(page,'customers',()=>page.locator('#customers-pagination [data-page="2"]').click());
 const output=await csv(page,'customers');expect(output).toContain('R trung vị');
 const cluster=await page.locator('#segment-donut [data-cluster]').first().getAttribute('data-cluster');
 const group=await responseTo(page,'customers',()=>page.locator('#segment-donut [data-cluster]').first().click());
 expect(group.items.every(r=>String(r.cluster_id)===cluster)).toBeTruthy();
 await expect(page.locator('#customers-kpis')).toContainText(number(group.summary.customers));
 await responseTo(page,'customers',()=>page.locator('#segment-scatter [data-cluster]').first().click());
 await page.locator('#customers-search').fill('NO_SUCH_CUSTOMER_DEMO_AUDIT');
 const empty=await responseTo(page,'customers',()=>page.locator('#customers-filters [type=submit]').click());
 expect(empty.summary.customers).toBe(0);
 const reset=await responseTo(page,'customers',()=>page.locator('#customers-filters [type=reset]').click());
 expect(reset.summary.customers).toBe(all.summary.customers);
 const options=await page.locator('#customers-model option').count();
 if(options>1){
  await page.locator('#customers-model').selectOption({index:1});
  const model=await responseTo(page,'customers',()=>page.locator('#customers-filters [type=submit]').click());
  expect(model.runs).toHaveLength(1);
 }
});
