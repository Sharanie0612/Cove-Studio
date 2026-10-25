import { expect, test } from '@playwright/test';

test.afterEach(async ({ request }) => {
  for (const id of ['community.background-job', 'test.background'])
    await request.post('/api/plugin_action', { data: [id, 'stop', true] });
});

test('SDK job progress, cancellation and worker restart use the shared task surface', async ({
  page,
  request,
}) => {
  const faults: string[] = [];
  page.on('pageerror', (error) => faults.push(error.message));
  await page.goto('/');
  await page.getByRole('button', { name: /示例 后台任务示例/ }).click();
  await page.getByRole('button', { name: '开始处理', exact: true }).first().click();
  const dialog = page.getByRole('dialog');
  await dialog.getByLabel('批次数', { exact: true }).fill('500');
  await dialog.getByRole('button', { name: '开始处理', exact: true }).click();
  await expect(page.getByRole('heading', { name: '正在运行', exact: true })).toBeVisible();
  await expect(page.getByRole('progressbar', { name: '任务进度' })).toHaveAttribute('max', '500');
  await expect
    .poll(async () => Number(await page.getByRole('progressbar').getAttribute('value')))
    .toBeGreaterThan(1);
  await page.getByRole('button', { name: '停止', exact: true }).click();
  await expect(page.getByRole('heading', { name: '已停止', exact: true })).toBeVisible();
  // Restart outside App's epoch mechanism to exercise runtime identity changes.
  const reply = await (
    await request.post('/api/plugin_action', {
      data: ['community.background-job', 'restart', true],
    })
  ).json();
  expect(reply.ok).toBe(true);
  await expect(page.getByRole('heading', { name: '准备运行', exact: true })).toBeVisible();
  await page.getByRole('button', { name: '开始处理', exact: true }).first().click();
  await dialog.getByLabel('批次数', { exact: true }).fill('3');
  await dialog.getByRole('button', { name: '开始处理', exact: true }).click();
  await expect(page.getByRole('heading', { name: '运行完成', exact: true })).toBeVisible();
  await expect(page.locator('.job-surface')).toContainText('已完成 3 批');
  expect(faults).toEqual([]);
});

test('unknown task size displays indeterminate progress', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: /测试 后台任务测试/ }).click();
  await page.getByRole('button', { name: '启动测试任务', exact: true }).first().click();
  await page.getByRole('dialog').getByRole('button', { name: '启动测试任务', exact: true }).click();
  const progress = page.getByRole('progressbar', { name: '任务进度' });
  await expect(progress).toBeVisible();
  await expect(progress).not.toHaveAttribute('value');
  await expect(page.locator('.job-progress')).toContainText('正在处理…');
});
