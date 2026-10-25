import { expect, test } from '@playwright/test';
test('title and sizing bridge exclude controls; snapped windows remove padding and radii', async ({
  page,
}) => {
  await page.goto('/');
  await expect(page.locator('.tool-tile').first()).toBeVisible();
  await page.evaluate(() => {
    document.documentElement.dataset.windowFrame = 'alpha';
    document.documentElement.dataset.windowDrag = 'bridge';
    (window as any).chromeActions = [];
    (window as any).pywebview.api.window_action = async (action: string) => {
      (window as any).chromeActions.push(action);
      return { ok: true, result: {} };
    };
    (window as any).pywebview.api.resize_window = async (edge: string) => {
      (window as any).chromeActions.push(edge);
      return { ok: true };
    };
  });
  await page.locator('.wordmark b').click();
  expect(await page.evaluate(() => (window as any).chromeActions)).toEqual(['drag']);
  await page.locator('.sidebar-toggle').click();
  expect(await page.evaluate(() => (window as any).chromeActions)).toEqual(['drag']);
  await page.locator('.resize-e').click();
  expect(await page.evaluate(() => (window as any).chromeActions)).toEqual(['drag', 'e']);
  await page.evaluate(() => (document.documentElement.dataset.windowSnapped = 'true'));
  expect(await page.locator('.app-shell').evaluate((el) => getComputedStyle(el).borderRadius)).toBe(
    '0px',
  );
  expect(await page.locator('#root').evaluate((el) => getComputedStyle(el).padding)).toBe('0px');
  await page.evaluate(() => (document.documentElement.dataset.windowSnapped = 'false'));
  expect(await page.locator('.app-shell').evaluate((el) => getComputedStyle(el).borderRadius)).toBe(
    '16px',
  );
});
