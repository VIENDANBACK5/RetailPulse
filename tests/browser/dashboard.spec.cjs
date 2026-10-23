/** Live read-only acceptance for the unified portal and same-origin reports.
 * Only the explicitly named UI-error-contract case intercepts an HTTP error.
 * It does not manufacture data, cluster metrics, or service integration proof.
 */
const { test, expect } = require('@playwright/test');
const fs = require('node:fs');

const formatted = (value, decimals = 2) => new Intl.NumberFormat('vi-VN', {maximumFractionDigits: decimals}).format(value);
const salesResponse = (currency) => response => response.url().includes('/api/reports/sales?') && new URL(response.url()).searchParams.get('currency') === currency;

test.beforeEach(async ({ page }) => {
  await page.goto('/frontend/reports.html');
  await expect(page.locator('#sales-content')).toBeVisible();
  await expect(page.locator('#sales-month-table table')).toBeAttached();
});

test('live sales matches warehouse and supports source/currency, month drill-down and reset', async ({ page, request }) => {
  const response = await request.get('/api/reports/sales?currency=GBP');
  expect(response.ok()).toBeTruthy();
  const data = await response.json();
  await expect(page.locator('#sales-kpis')).toContainText(formatted(data.summary.net));
  await expect(page.locator('#sales-unit')).toHaveText('GBP');
  await page.locator('#sales-source').selectOption('APP_OPERATIONAL');
  await expect(page.locator('#sales-currency')).toHaveValue('VND');
  await Promise.all([page.waitForResponse(salesResponse('VND')), page.locator('#sales-filters button[type=submit]').click()]);
  await expect(page.locator('#sales-content')).toBeVisible();
  const app = await (await request.get('/api/reports/sales?currency=VND&source=APP_OPERATIONAL')).json();
  await expect(page.locator('#sales-kpis')).toContainText(formatted(app.summary.net, 0));
  await Promise.all([page.waitForResponse(salesResponse('VND')), page.locator('#sales-chart [data-month]').first().click()]);
  await expect(page.locator('#sales-start')).not.toHaveValue('');
  await expect(page.locator('#sales-end')).not.toHaveValue('');
  await expect(page.locator('#sales-content')).toBeVisible();
  await Promise.all([page.waitForResponse(salesResponse('GBP')), page.locator('#sales-filters button[type=reset]').click()]);
  await expect(page.locator('#sales-unit')).toHaveText('GBP');
  await expect(page.locator('#sales-content')).toBeVisible();
});

test('live CSV export contains the actual monthly warehouse rows', async ({ page, request }) => {
  const data = await (await request.get('/api/reports/sales?currency=GBP')).json();
  const download = await Promise.all([page.waitForEvent('download'), page.locator('[data-export=sales]').click()]).then(results => results[0]);
  expect(download.suggestedFilename()).toMatch(/^RetailPulse-sales-.*\.csv$/);
  const contents = fs.readFileSync(await download.path(), 'utf8').replace(/^\uFEFF/, '').trim();
  const lines = contents.split(/\r?\n/);
  expect(lines.length).toBe(data.monthly.length + 1);
  expect(contents).toContain('GBP');
  expect(contents).toContain(data.monthly[0].year_month);
});

test('live inventory searches and paginates actual SKU snapshots without fabricated products', async ({ page, request }) => {
  const data = await (await request.get('/api/reports/inventory')).json();
  expect(data.items.length).toBeGreaterThan(0);
  expect(data.items.some(row => row.stock_code === 'ALL_PRODUCTS')).toBe(false);
  await page.locator('#tab-inventory').click();
  await expect(page.locator('#inventory-content')).toBeVisible();
  await expect(page.locator('#inventory-branches .inventory-branch')).toHaveCount(data.branches.length);
  if (data.total > data.page_size) {
    await page.locator('[data-page-kind="inventory"][data-page="2"]').click();
    await expect(page.locator('#inventory-pagination')).toContainText('Trang 2');
    await expect(page.locator('#inventory-content')).toBeVisible();
  }
  const sku = data.items[0].stock_code;
  const expected = await (await request.get('/api/reports/inventory?search=' + encodeURIComponent(sku))).json();
  await page.locator('#inventory-search').fill(sku);
  await expect(page.locator('#inventory-table tbody tr')).toHaveCount(expected.items.length);
  await expect(page.locator('#inventory-pagination')).toContainText(String(expected.total));
  await expect(page.locator('#inventory-search')).toBeFocused();
  await expect(page.locator('#inventory-table')).toContainText(sku);
});

test('live customer view uses the latest successful model and filters actual records', async ({ page, request }) => {
  const data = await (await request.get('/api/reports/customers')).json();
  expect(data.runs.length).toBeGreaterThan(0);
  expect(data.profiles.length).toBeGreaterThan(0);
  const current = data.runs[0];
  const registered = await (await request.get('/api/runs/' + current.run_id)).json();
  expect(registered.status).toBe('SUCCESS');
  await page.locator('#tab-customers').click();
  await expect(page.locator('#customers-content')).toBeVisible();
  await expect(page.locator('#customers-run')).toContainText(current.model_version);
  await expect(page.locator('.segment-legend button')).toHaveCount(data.profiles.length);
  const group = page.locator('.segment-legend button').first();
  const id = await group.getAttribute('data-cluster');
  await group.click();
  await expect(page.locator('#customers-cluster')).toHaveValue(id);
  await expect(page.locator('#customers-content')).toBeVisible();
  const selected = await (await request.get('/api/reports/customers?cluster=' + id)).json();
  await expect(page.locator('#customers-table tbody tr')).toHaveCount(selected.items.length);
  await page.locator('#customers-search').fill('rp-no-such-customer-browser-contract');
  await page.locator('#customers-filters button[type=submit]').click();
  await expect(page.locator('#customers-table .report-empty')).toBeVisible();
});

test('shared shell stays consistent across the real portal pages', async ({ page }) => {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  const expected = await page.locator('.portal-header').evaluate(el => ({background: getComputedStyle(el).backgroundColor, font: getComputedStyle(el).fontFamily}));
  for (const path of ['index.html', 'etl-monitor.html', 'dashboard.html', 'customer-segments.html', 'reports.html', 'demo-guide.html']) {
    await page.goto('/frontend/' + path);
    await expect(page.locator('#portal-navigation a[aria-current="page"]')).toHaveAttribute('href', path);
    await expect(page.locator('#portal-footer footer')).toHaveCount(1);
    expect(await page.locator('.portal-header').evaluate(el => ({background: getComputedStyle(el).backgroundColor, font: getComputedStyle(el).fontFamily}))).toEqual(expected);
  }
  expect(errors).toEqual([]);
});

test('UI error contract only: a simulated HTTP503 hides stale sales and real retry recovers', async ({ page }) => {
  const pattern = /\/api\/reports\/sales\?/;
  await page.route(pattern, route => route.fulfill({status: 503, json: {detail: 'Warehouse temporarily unavailable (UI contract test)'}}));
  await page.locator('#refresh-report').click();
  await expect(page.locator('#report-message')).toContainText('Warehouse temporarily unavailable');
  await expect(page.locator('#sales-content')).toBeHidden();
  await page.unroute(pattern);
  await page.locator('#retry-report').click();
  await expect(page.locator('#sales-content')).toBeVisible();
  await expect(page.locator('#sales-kpis')).not.toBeEmpty();
});

test('mobile supports report-tab keyboard navigation and the shared menu within the viewport', async ({ page }) => {
  await page.setViewportSize({width: 390, height: 844});
  await page.locator('#tab-sales').focus();
  await page.keyboard.press('ArrowRight');
  await expect(page.locator('#tab-inventory')).toBeFocused();
  await expect(page.locator('#inventory-content')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
  await page.locator('.portal-menu').click();
  await expect(page.locator('.portal-menu')).toHaveAttribute('aria-expanded', 'true');
  await expect(page.locator('#portal-navigation')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.locator('.portal-menu')).toHaveAttribute('aria-expanded', 'false');
  await expect(page.locator('.portal-menu')).toBeFocused();
});

test('report requests use the single portal gateway rather than a second browser API origin', async ({ page, baseURL }) => {
  const calls = [];
  page.on('request', request => { if (request.resourceType() === 'fetch') calls.push(request.url()); });
  await Promise.all([page.waitForResponse(salesResponse('GBP')), page.locator('#refresh-report').click()]);
  await expect(page.locator('#sales-content')).toBeVisible();
  const reportCalls = calls.filter(url => new URL(url).pathname.startsWith('/api/reports/'));
  expect(reportCalls.length).toBeGreaterThan(0);
  expect(reportCalls.every(url => new URL(url).origin === new URL(baseURL).origin)).toBe(true);
  expect(calls.some(url => new URL(url).port === '8001')).toBe(false);
});
