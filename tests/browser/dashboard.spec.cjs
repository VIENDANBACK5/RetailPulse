/** Acceptance for the original origin/danh frontend, not the retired seven-stage UI. */
const {test, expect} = require('@playwright/test');

test('Danh warehouse dashboard reads actual analytics data', async ({page, request}) => {
  await page.goto('/frontend/dashboard.html');
  await expect(page.locator('#sales-content')).toBeVisible();
  const response = await request.get('http://127.0.0.1:8001/api/v1/analytics/sales?currency=GBP');
  expect(response.ok()).toBeTruthy();
  const data = await response.json();
  await expect(page.locator('#sales-kpis')).toContainText(new Intl.NumberFormat('vi-VN', {maximumFractionDigits: 2}).format(data.summary.net));
});

test('Danh pages retain their original shells while extending the data journey', async ({page}) => {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  for (const name of ['index', 'dashboard', 'operations', 'etl-monitor', 'customer-segments']) {
    const response = await page.goto('/frontend/' + name + '.html');
    expect(response.status()).toBe(200);
    await expect(page.locator('#portal-shell')).toHaveCount(0);
    await expect(page.locator('link[href*="portal.css"]')).toHaveCount(0);
    if (name === 'index') await expect(page.locator('#page-loader')).toBeHidden();
    else await expect(page.locator('.workspace-sidebar')).toHaveCount(1);
  }
  expect(errors).toEqual([]);
});

test('secondary customer segmentation link stays on Danh Mining with four evidence blocks and no cache', async ({page}) => {
  const response=await page.goto('/frontend/dashboard.html?ui=danh-live-20261025');
  expect(response.headers()['cache-control']).toContain('no-store');
  const link=page.locator('.sidebar-secondary').getByRole('link',{name:'Phân khúc khách hàng',exact:true});
  await expect(link).toHaveAttribute('href','customer-segments.html?ui=danh-live-20261025#mining');
  await link.click();
  await expect(page).toHaveURL(/\/frontend\/customer-segments\.html\?ui=danh-live-20261025#mining$/);
  await expect(page.locator('[data-dj-node="mining"] .dj-box')).toHaveCount(4);
  await expect(page.locator('link[href*="css/workspace.css"]')).toHaveCount(1);
  await expect(page.locator('#portal-shell')).toHaveCount(0);
});

test('Danh mobile sidebar opens and closes with Escape', async ({page}) => {
  await page.setViewportSize({width: 390, height: 844});
  await page.goto('/frontend/dashboard.html');
  await expect(page.locator('#sales-content')).toBeVisible();
  await page.locator('#sidebar-toggle').click();
  await expect(page.locator('#sidebar-toggle')).toHaveAttribute('aria-expanded', 'true');
  await page.keyboard.press('Escape');
  await expect(page.locator('#sidebar-toggle')).toHaveAttribute('aria-expanded', 'false');
  await expect(page.locator('#sidebar-toggle')).toBeFocused();
});
