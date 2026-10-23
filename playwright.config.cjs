const {defineConfig} = require('@playwright/test');

// Exercise the actual running app. Start with START_RETAILPULSE.ps1 first.
// The portal and its API share 8010; a static dev server cannot execute APIs.
module.exports = defineConfig({
  testDir: './tests/browser',
  workers: 1,
  timeout: 90000,
  expect: {timeout: 45000},
  reporter: [['list'], ['json', {outputFile: 'evidence/portal_browser_tests.json'}]],
  use: {
    baseURL: process.env.PORTAL_URL || 'http://127.0.0.1:8010',
    channel: 'chrome',
    headless: true,
    viewport: {width: 1440, height: 1000},
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },
});
