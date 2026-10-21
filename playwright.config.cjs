const { defineConfig } = require('@playwright/test');
module.exports = defineConfig({
  testDir: './tests/browser',
  workers: 1,
  timeout: 60000,
  expect: { timeout: 30000 },
  webServer: {
    command: 'python scripts/serve_frontend.py --port 5174',
    url: 'http://127.0.0.1:5174/frontend/dashboard.html',
    reuseExistingServer: !process.env.CI,
  },
  use: {
    baseURL: process.env.PORTAL_URL || 'http://127.0.0.1:8001',
    channel: 'chrome',
    headless: true,
    viewport: { width: 1440, height: 1000 },
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },
});
