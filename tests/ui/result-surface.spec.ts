import { expect, test } from '@playwright/test';

test('declarative result renders safely, paginates and stays mounted across navigation', async ({
  page,
}, testInfo) => {
  const faults: string[] = [];
  await page.emulateMedia({ reducedMotion: 'reduce' });
  page.on('pageerror', (error) => faults.push(error.message));
  await page.goto('/');
  await page.getByRole('button', { name: /示例 文本报告/ }).click();
  await page.getByRole('button', { name: '分析文本', exact: true }).first().click();
  const dialog = page.getByRole('dialog');
  await dialog
    .getByLabel('文本', { exact: true })
    .fill(Array.from({ length: 75 }, (_, i) => `word${i}`).join(' '));
  await dialog.getByRole('button', { name: '分析文本', exact: true }).click();
  const result = page.getByRole('region', { name: '文本分析', exact: true });
  await expect(result).toBeVisible();
  await expect(result.getByRole('row')).toHaveCount(51);
  await expect(result).toContainText('75 条记录');
  await result.getByRole('button', { name: '下一页结果' }).click();
  await expect(result.getByRole('row')).toHaveCount(26);
  await expect(result).toContainText('word74');
  await page.getByRole('button', { name: '工作台', exact: true }).click();
  await page.getByRole('tab', { name: '文本报告', exact: true }).click();
  await expect(result).toContainText('第 2 / 2 页');
  await result.evaluate((element) => {
    element.scrollTop = 0;
  });
  await expect(result.getByRole('columnheader', { name: '词语', exact: true })).toBeInViewport();
  await page.screenshot({ path: testInfo.outputPath('result-light.png'), animations: 'disabled' });
  await page.getByRole('button', { name: '设置', exact: true }).click();
  await page.getByRole('button', { name: '深色', exact: true }).click();
  await page.getByRole('button', { name: '关闭设置', exact: true }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await page.screenshot({ path: testInfo.outputPath('result-dark.png'), animations: 'disabled' });
  await result.getByRole('button', { name: '再次运行' }).click();
  await dialog.getByLabel('文本', { exact: true }).fill('hello hello cove');
  await dialog.getByRole('button', { name: '分析文本', exact: true }).click();
  await expect(result.getByRole('row')).toHaveCount(3);
  await expect(result).toContainText('第 1 / 1 页');
  await result.getByRole('button', { name: '再次运行' }).click();
  const markup = '<img src=x onerror="window.resultInjected=true">';
  await dialog.getByLabel('文本', { exact: true }).fill(markup);
  await dialog.getByRole('button', { name: '分析文本', exact: true }).click();
  await expect(result).toContainText(markup);
  await expect(result.locator('img')).toHaveCount(0);
  expect(await page.evaluate(() => Object.hasOwn(window, 'resultInjected'))).toBe(false);
  expect(faults).toEqual([]);
});
