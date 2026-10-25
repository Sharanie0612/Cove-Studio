import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests/ui',
  fullyParallel: false,
  workers: 1,
  timeout: 30000,
  reporter: [['list'], ['html', { open: 'never', outputFolder: 'artifacts/playwright-report' }]],
  outputDir: 'artifacts/playwright-results',
  use: {
    locale: 'zh-CN',
    baseURL: 'http://127.0.0.1:18320',
    viewport: { width: 1380, height: 900 },
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    launchOptions: process.env.COVE_BROWSER_CHANNEL
      ? { channel: process.env.COVE_BROWSER_CHANNEL }
      : {},
  },
  webServer: {
    command: '.venv\\Scripts\\python.exe scripts/serve_e2e.py',
    url: 'http://127.0.0.1:18320',
    reuseExistingServer: false,
    timeout: 30000,
  },
});
