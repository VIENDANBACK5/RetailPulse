const { test, expect } = require('@playwright/test');

test.beforeEach(async ({ page }) => {
  await page.route('https://fonts.googleapis.com/**', route => route.abort());
  await page.goto('/frontend/dashboard.html');
  await expect(page.locator('#sales-content')).toBeVisible();
});

test('sales reads warehouse, switches currency, drills into a month and resets', async ({ page, request }) => {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  const data = await (await request.get('/api/v1/analytics/sales?currency=GBP')).json();
  const expected = new Intl.NumberFormat('vi-VN', { maximumFractionDigits: 2 }).format(data.summary.net);
  await expect(page.locator('#sales-kpis')).toContainText(expected);
  await expect(page.locator('#sales-unit')).toHaveText('GBP');
  await page.screenshot({ path: 'test-results/sales-desktop.png', fullPage: true });
  await page.locator('#sales-source').selectOption('APP_OPERATIONAL');
  await expect(page.locator('#sales-currency')).toHaveValue('VND');
  await page.locator('#sales-filters button[type=submit]').click();
  await expect(page.locator('#sales-unit')).toHaveText('VND');
  await expect(page.locator('#sales-content')).toBeVisible();
  await page.locator('#sales-chart [data-month]').first().click();
  await expect(page.locator('#sales-start')).not.toHaveValue('');
  await expect(page.locator('#sales-content')).toBeVisible();
  await page.locator('#sales-filters button[type=reset]').click();
  await expect(page.locator('#sales-unit')).toHaveText('GBP');
  expect(errors).toEqual([]);
});

test('inventory searches, paginates, and represents offline inventory as unknown', async ({ page }) => {
  await page.getByRole('tab', { name: 'Tồn kho chi nhánh' }).click();
  await expect(page.locator('#inventory-content')).toBeVisible();
  await expect(page.locator('#inventory-branches .inventory-branch')).toHaveCount(3);
  await page.locator('#inventory-pagination').getByRole('button', { name: 'Sau' }).click();
  await expect(page.locator('#inventory-pagination')).toContainText('Trang 2');
  await page.locator('#inventory-search').fill('PROD-CERAMIC');
  await expect(page.locator('#inventory-pagination')).toContainText('1–3 / 3');
  await expect(page.locator('#inventory-search')).toBeFocused();
  await page.screenshot({ path: 'test-results/inventory-desktop.png', fullPage: true });
  await page.route('**/analytics/inventory?**', async route => {
    const response = await route.fetch();
    const data = await response.json();
    data.summary.stock = null;
    data.summary.offline_branches = 1;
    data.branches = [{ branch_code: 'HN', node_status: 'OFFLINE', stock: null, sku_count: 0, low_locations: 0, snapshot_time: null }];
    data.items = [{ branch_code: 'HN', stock_code: 'ALL_PRODUCTS', product_name: 'Node mất kết nối', stock_on_hand: null, node_status: 'OFFLINE', snapshot_time: null }];
    data.total = 1;
    await route.fulfill({ json: data });
  });
  await page.locator('#refresh-report').click();
  await expect(page.locator('#inventory-branches')).toContainText('Chưa biết tồn');
  await expect(page.locator('#inventory-table')).toContainText('—');
  await expect(page.locator('#inventory-warning')).toBeVisible();
});

test('customer groups drill into real records and preserve latest model context', async ({ page }) => {
  await page.getByRole('tab', { name: 'Phân khúc khách hàng' }).click();
  await expect(page.locator('#customers-content')).toBeVisible();
  await expect(page.locator('#customers-run')).toContainText('kmeans-k4');
  const group = page.locator('.segment-legend button').first();
  const id = await group.getAttribute('data-cluster');
  await group.click();
  await expect(page.locator('#customers-cluster')).toHaveValue(id);
  await expect(page.locator('#customers-content')).toBeVisible();
  await expect(page.locator('#customers-table tbody tr')).toHaveCount(20);
  await page.screenshot({ path: 'test-results/customers-desktop.png', fullPage: true });
  await page.locator('#customers-search').fill('customer-does-not-exist');
  await page.locator('#customers-filters button[type=submit]').click();
  await expect(page.locator('#customers-table')).toContainText('Không có dữ liệu phù hợp');
});

test('valid empty inventory stays online and audit exposes skipped older versions', async ({ page }) => {
  await expect(page.locator('#audit-table')).toContainText('Bản cũ bỏ qua');
  await page.route('**/analytics/inventory?**', async route => {
    const response = await route.fetch();
    const data = await response.json();
    const snapshot = new Date().toISOString();
    data.summary = { stock: 0, offline_branches: 0, branch_count: 1,
      sku_locations: 0, low_locations: 0, zero_locations: 0, snapshot_time: snapshot };
    data.branches = [{ branch_code: 'SG', node_status: 'ONLINE', stock: 0,
      sku_count: 0, low_locations: 0, snapshot_time: snapshot }];
    data.items = [{ branch_code: 'SG', stock_code: 'ALL_PRODUCTS',
      product_name: 'Chi nhánh chưa có sản phẩm', stock_on_hand: null,
      node_status: 'ONLINE', snapshot_time: snapshot }];
    data.total = 1;
    await route.fulfill({ json: data });
  });
  await page.getByRole('tab', { name: 'Tồn kho chi nhánh' }).click();
  await expect(page.locator('#inventory-content')).toBeVisible();
  await expect(page.locator('#inventory-branches')).toContainText('Chưa có sản phẩm');
  await expect(page.locator('#inventory-context')).toContainText('0 điểm tồn ONLINE');
  await expect(page.locator('#inventory-table')).toContainText('Chưa có sản phẩm');
  await expect(page.locator('#inventory-table')).not.toContainText('Mất kết nối');
  await expect(page.locator('#inventory-warning')).toBeHidden();
});

test('connection failure hides old numbers and retry recovers', async ({ page }) => {
  await page.route('**/analytics/sales?**', route => route.fulfill({ status: 503, json: { detail: 'Warehouse tạm ngừng' } }));
  await page.locator('#refresh-report').click();
  await expect(page.locator('#report-message')).toContainText('Warehouse tạm ngừng');
  await expect(page.locator('#sales-content')).toBeHidden();
  await page.unroute('**/analytics/sales?**');
  await page.locator('#retry-report').click();
  await expect(page.locator('#sales-content')).toBeVisible();
});

test('mobile keeps the page within viewport and supports keyboard tabs and sidebar', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.locator('#tab-sales').focus();
  await page.keyboard.press('ArrowRight');
  await expect(page.locator('#tab-inventory')).toBeFocused();
  await expect(page.locator('#inventory-content')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.locator('#sidebar-toggle').click();
  await expect(page.locator('#sidebar-toggle')).toHaveAttribute('aria-expanded', 'true');
  await page.keyboard.press('Escape');
  await expect(page.locator('#sidebar-toggle')).toHaveAttribute('aria-expanded', 'false');
  await page.screenshot({ path: 'test-results/inventory-mobile.png', fullPage: true });
});

test('static frontend dev server can read the API across origins', async ({ page }) => {
  await page.goto('http://127.0.0.1:5174/frontend/dashboard.html');
  await expect(page.locator('#sales-content')).toBeVisible();
  await expect(page.locator('#connection-label')).toHaveText('Dữ liệu từ warehouse');
});
