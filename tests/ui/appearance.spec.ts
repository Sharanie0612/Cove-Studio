import { expect, test } from '@playwright/test';

for (const mode of ['light', 'dark']) {
  test(`shared pages remain usable at minimum size in ${mode} with reduced motion`, async ({
    page,
  }, testInfo) => {
    await page.setViewportSize({ width: 960, height: 660 });
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.addInitScript((mode) => {
      localStorage.setItem('toolbench:appearance-v1', JSON.stringify({ mode, scheme: 'cove' }));
    }, mode);
    await page.goto('/');
    await expect(page.locator('.tool-tile').first()).toBeVisible();
    const fonts = await page.evaluate(async () => {
      await document.fonts.ready;
      return Array.from(document.fonts)
        .filter((font) => font.family.includes('Cove Sans'))
        .map((font) => ({ family: font.family.replaceAll('"', ''), status: font.status }));
    });
    expect(fonts).toEqual([
      { family: 'Cove Sans Latin', status: 'loaded' },
      { family: 'Cove Sans CJK', status: 'loaded' },
    ]);
    const pages = [
      ['工作台', '工作台'],
      ['智能体工具', '智能体工具'],
      ['插件', '插件'],
      ['开发指南', '插件开发'],
    ];
    for (const [label, heading] of pages) {
      await page.locator('.app-sidebar').getByRole('button', { name: label, exact: true }).click();
      await expect(page.getByRole('heading', { name: heading, exact: true })).toBeVisible();
      const metrics = await page.locator('.content-main').evaluate((element) => ({
        visible: element.clientWidth,
        content: element.scrollWidth,
        body: document.body.scrollWidth,
        viewport: innerWidth,
      }));
      expect(
        metrics.content,
        `${label} must not require horizontal page scrolling`,
      ).toBeLessThanOrEqual(metrics.visible + 1);
      expect(metrics.body).toBeLessThanOrEqual(metrics.viewport);
      await page.screenshot({ path: testInfo.outputPath(`${heading}-${mode}.png`) });
    }
    await page.getByRole('button', { name: '设置', exact: true }).click();
    await page.getByRole('button', { name: '完成', exact: true }).focus();
    await expect(page.getByRole('button', { name: '完成', exact: true })).toBeInViewport();
    await page.keyboard.press('Enter');
    await expect(page.getByRole('dialog')).toHaveCount(0);
    await page.getByRole('button', { name: '工作台', exact: true }).click();
    await page.getByRole('button', { name: '列表视图' }).click();
    await expect(page.locator('.tool-collection')).toHaveClass(/is-list/);
    await page.getByRole('button', { name: /连接 MCP 连接/ }).click();
    await expect(page.getByRole('heading', { name: 'MCP 连接', exact: true })).toBeVisible();
    await page.screenshot({ path: testInfo.outputPath(`mcp-${mode}.png`) });
  });
}
