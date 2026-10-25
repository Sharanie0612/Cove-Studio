import { expect, test } from '@playwright/test';

test.afterEach(async ({ request }) => {
  await request.post('/api/assistant_allow', { data: [[]] });
  await request.post('/api/plugin_action', { data: ['test.approval', 'stop', true] });
});

test('approval exposes complete arguments, identifies redactions and executes only after approval', async ({
  page,
  request,
}) => {
  await request.post('/api/assistant_allow', { data: [['test.approval']] });
  const argumentsToReview = {
    document: 'x'.repeat(17000) + 'review-the-final-operation',
    steps: Array.from({ length: 110 }, (_, index) => `step-${index}`).concat(
      'review-final-array-item',
    ),
    options: { api_token: 'fixture-secret', note: 'ordinary option' },
  };
  await page.goto('/');
  const operation = request.post('/fixture/approval', { data: argumentsToReview });
  const dialog = page.getByRole('dialog', { name: '确认本次工具操作' });
  await expect(dialog).toBeVisible();
  const parameters = dialog.getByRole('region', { name: '工具操作参数' });
  await expect(parameters).toContainText('review-the-final-operation');
  await expect(parameters).toContainText('review-final-array-item');
  await expect(parameters).not.toContainText('fixture-secret');
  await expect(dialog.getByRole('note')).toContainText('已遮盖 1 个敏感字段');
  await expect(dialog.getByRole('note')).toContainText('执行时仍使用原始值');
  const shown = JSON.parse((await parameters.textContent())!);
  expect(shown.document).toBe(argumentsToReview.document);
  expect(shown.steps).toEqual(argumentsToReview.steps);
  expect(shown.options.api_token).toBe('[redacted]');
  // The bounded parameter region remains keyboard-scrollable with reachable decisions.
  await parameters.focus();
  await page.keyboard.press('Control+End');
  await expect.poll(() => parameters.evaluate((element) => element.scrollTop)).toBeGreaterThan(0);
  await expect(dialog.getByRole('button', { name: '允许本次', exact: true })).toBeInViewport();
  const before = await (
    await request.post('/api/invoke', { data: ['test.approval', 'snapshot', {}] })
  ).json();
  expect(before.result).toEqual([]);
  await dialog.getByRole('button', { name: '允许本次', exact: true }).click();
  expect((await (await operation).json()).ok).toBe(true);
  await expect(dialog).toHaveCount(0);
  const after = await (
    await request.post('/api/invoke', { data: ['test.approval', 'snapshot', {}] })
  ).json();
  expect(after.result).toEqual([argumentsToReview]);

  const rejected = request.post('/fixture/approval', { data: argumentsToReview });
  await expect(dialog).toBeVisible();
  await dialog.getByRole('button', { name: '拒绝', exact: true }).click();
  expect((await (await rejected).json()).ok).toBe(false);
  await expect(dialog).toHaveCount(0);
  const unchanged = await (
    await request.post('/api/invoke', { data: ['test.approval', 'snapshot', {}] })
  ).json();
  expect(unchanged.result).toEqual([argumentsToReview]);
});
