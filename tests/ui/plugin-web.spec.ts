import { expect, test } from '@playwright/test';

test.afterEach(async ({ request }) => {
  await request.post('/api/plugin_action', { data: ['community.web-starter', 'stop', true] });
});

for (const mode of ['light', 'dark']) {
  test(`plugin-owned UI is isolated and keeps drafts across language/theme changes in ${mode}`, async ({
    page,
    request,
  }, testInfo) => {
    await page.setViewportSize({ width: 960, height: 660 });
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.addInitScript((mode) => {
      localStorage.setItem('toolbench:appearance-v1', JSON.stringify({ mode, scheme: 'cove' }));
    }, mode);
    await page.goto('/');
    await page.getByRole('button', { name: /示例 独立界面示例/ }).click();
    const frame = page.frameLocator('.plugin-web-surface iframe');
    await expect(frame.getByRole('heading', { name: '插件自带界面' })).toBeVisible();
    await expect(frame.locator('output')).toHaveText('0');
    const child = page.frames().find((frame) => frame.parentFrame());
    expect(
      await child!.evaluate(() => {
        let parentBlocked = false;
        try {
          void parent.document.body;
        } catch {
          parentBlocked = true;
        }
        return { parentBlocked, nativeApi: typeof window.pywebview };
      }),
    ).toEqual({ parentBlocked: true, nativeApi: 'undefined' });
    expect(
      await child!.evaluate(async () => {
        try {
          await fetch('http://127.0.0.1:18320/api/catalog');
          return false;
        } catch {
          return true;
        }
      }),
    ).toBe(true);
    await frame.getByLabel('草稿', { exact: true }).fill('keep draft');
    await page.getByRole('button', { name: '设置', exact: true }).click();
    await page.getByRole('combobox', { name: '界面语言', exact: true }).selectOption('en-US');
    await page
      .getByRole('button', { name: mode === 'light' ? 'Dark' : 'Light', exact: true })
      .click();
    await page.getByRole('button', { name: 'Done', exact: true }).click();
    await expect(page.getByRole('dialog')).toHaveCount(0);
    await expect(frame.getByRole('heading', { name: 'Plugin-owned interface' })).toBeVisible();
    await expect(frame.getByLabel('Draft', { exact: true })).toHaveValue('keep draft');
    await expect
      .poll(() => child!.evaluate(() => document.documentElement.dataset.theme))
      .toBe(mode === 'light' ? 'dark' : 'light');
    await frame.getByRole('button', { name: 'Increment', exact: true }).click();
    await expect
      .poll(async () => {
        const state = await (await request.post('/api/assistant_state', { data: [] })).json();
        return state.result.pending.length;
      })
      .toBeGreaterThan(0);
    const approval = page.getByRole('dialog');
    await expect(
      approval.getByRole('heading', { name: 'Approve this tool operation' }),
    ).toBeVisible();
    await expect(frame.locator('output')).toHaveText('0');
    await approval.getByRole('button', { name: 'Allow once', exact: true }).click();
    await expect(frame.locator('output')).toHaveText('1');
    await expect(page.getByRole('dialog')).toHaveCount(0);
    await page.getByRole('button', { name: 'Workbench', exact: true }).click();
    await page.getByRole('tab', { name: 'Plugin UI example', exact: true }).click();
    await expect(frame.getByLabel('Draft', { exact: true })).toHaveValue('keep draft');
    await page.screenshot({ path: testInfo.outputPath(`plugin-ui-${mode}.png`) });
  });
}

test('closing an iframe invalidates its pending write', async ({ page, request }) => {
  await page.goto('/');
  await page.getByRole('button', { name: /示例 独立界面示例/ }).click();
  const frame = page.frameLocator('.plugin-web-surface iframe');
  await expect(frame.locator('output')).toHaveText('0');
  await frame.getByRole('button', { name: '增加计数', exact: true }).click();
  await expect(
    page.getByRole('dialog').getByRole('heading', { name: '确认本次工具操作' }),
  ).toBeVisible();
  await request.post('/api/plugin_action', { data: ['community.web-starter', 'stop', true] });
  await expect(page.getByRole('dialog')).toHaveCount(0);
  const state = await (await request.post('/api/assistant_state', { data: [] })).json();
  expect(state.result.pending).toEqual([]);
});
