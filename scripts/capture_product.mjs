import { chromium } from '@playwright/test';
const browser = await chromium.launch({ channel: process.env.COVE_BROWSER_CHANNEL || 'msedge' });
try {
  for (const locale of ['zh-CN', 'en-US']) {
    const context = await browser.newContext({ locale, viewport: { width: 1380, height: 860 }, reducedMotion: 'reduce' });
    try {
      const page = await context.newPage();
      await page.goto(process.env.COVE_PREVIEW_URL || 'http://127.0.0.1:18329');
      await page.locator('.tool-tile').first().waitFor();
      await page.evaluate(() => document.fonts.ready);
      if (await page.locator('.tool-tile').count() !== 1 || !(await page.locator('.tool-tile').innerText()).includes('MCP')) throw new Error('Documentation capture requires the MCP-only catalog');
      const prefix = locale === 'en-US' ? 'workbench-en' : 'workbench';
      await page.screenshot({ path: `docs/media/${prefix}-light.png` });
      await page.getByRole('button', { name: locale === 'en-US' ? 'Settings' : '设置', exact: true }).click();
      await page.getByRole('button', { name: locale === 'en-US' ? 'Dark' : '深色', exact: true }).click();
      await page.getByRole('button', { name: locale === 'en-US' ? 'Done' : '完成', exact: true }).click();
      await page.getByRole('dialog').waitFor({ state: 'hidden' });
      await page.screenshot({ path: `docs/media/${prefix}-dark.png` });
    } finally { await context.close(); }
  }
} finally { await browser.close(); }
