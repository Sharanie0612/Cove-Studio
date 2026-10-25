import { expect, test } from '@playwright/test';

test.beforeEach(async ({ request }) => {
  await request.post('/api/plugin_action', { data: ['test.background', 'stop', true] });
});

test('background work protects tab, stop, restart, disable and exit; Cancel restores focus', async ({
  page,
  request,
}) => {
  const faults: string[] = [];
  page.on('pageerror', (error) => faults.push(error.message));
  await page.goto('/');
  await page.getByRole('button', { name: /测试 后台任务测试/ }).click();
  await page.getByRole('button', { name: '启动测试任务', exact: true }).click();
  const configuration = page.getByRole('dialog');
  await configuration.getByRole('button', { name: '启动测试任务', exact: true }).click();
  await expect(configuration).toHaveCount(0);
  await expect(page.getByRole('heading', { name: '正在运行' })).toBeVisible();
  const close = page.getByRole('button', { name: '关闭 后台任务测试', exact: true });
  await close.click();
  await expect(page.getByRole('dialog')).toContainText('1 个后台任务');
  await page.getByRole('button', { name: '取消', exact: true }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(close).toBeFocused();
  await expect(page.getByRole('heading', { name: '正在运行' })).toBeVisible();
  for (const operation of ['stop', 'restart', 'disable']) {
    const reply = await (
      await request.post('/api/plugin_action', { data: ['test.background', operation] })
    ).json();
    expect(reply.result.needsConfirmation).toBe(true);
    expect(reply.result.backgroundTasks).toBe(1);
  }
  await page.getByRole('button', { name: '关闭窗口', exact: true }).click();
  await expect(page.getByRole('dialog')).toContainText('1 个后台任务');
  await page.getByRole('button', { name: '取消', exact: true }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await close.click();
  await page.getByRole('button', { name: '确认', exact: true }).click();
  await expect(page.getByRole('tab', { name: '后台任务测试', exact: true })).toHaveCount(0);
  const catalog = await (await request.post('/api/catalog', { data: [] })).json();
  expect(
    catalog.tools.find((tool: { id: string }) => tool.id === 'test.background').runtime.running,
  ).toBe(false);
  expect(faults).toEqual([]);
});

test('live terminal survives navigation, lazy mounting, appearance and sidebar changes', async ({
  page,
  request,
}) => {
  const fixture = await (await request.get('/fixture')).json();
  const values = {
    host: '127.0.0.1',
    port: fixture.port,
    username: 'demo',
    auth: 'password',
    password: 'test-only',
  };
  const challenge = await (
    await request.post('/api/invoke', { data: ['test.terminal', 'connect', values] })
  ).json();
  const connected = await (
    await request.post('/api/invoke', {
      data: [
        'test.terminal',
        'connect',
        { ...values, trust_fingerprint: challenge.details?.fingerprint },
      ],
    })
  ).json();
  expect(connected.ok).toBe(true);
  await page.goto('/');
  await page.getByRole('button', { name: /测试 终端夹具/ }).click();
  const terminal = page.locator('.xterm-mount .xterm');
  await expect(terminal).toBeVisible();
  const handle = await terminal.elementHandle();
  await page.getByRole('button', { name: '工作台', exact: true }).click();
  await page.getByRole('button', { name: '设置', exact: true }).click();
  await page.getByRole('button', { name: '深色', exact: true }).click();
  await page.getByRole('button', { name: '完成', exact: true }).click();
  await page.getByRole('button', { name: '收起侧栏', exact: true }).click();
  await page.getByRole('tab', { name: '终端夹具', exact: true }).click();
  await expect(terminal).toBeVisible();
  expect(await handle!.evaluate((node) => node.isConnected)).toBe(true);
  const catalog = await (await request.post('/api/catalog', { data: [] })).json();
  expect(
    catalog.tools.find((tool: { id: string }) => tool.id === 'test.terminal').runtime.connected,
  ).toBe(true);
  await page.getByRole('button', { name: '关闭 终端夹具', exact: true }).click();
  await expect(page.getByRole('dialog')).toContainText('1 个连接');
  await page.getByRole('button', { name: '取消', exact: true }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  expect(await handle!.evaluate((node) => node.isConnected)).toBe(true);
});

test('startup failure opens safe diagnostic and leaves the rest of the UI usable', async ({
  page,
}) => {
  const faults: string[] = [];
  page.on('pageerror', (error) => faults.push(error.message));
  await page.goto('/');
  await page.getByRole('button', { name: /测试 启动失败测试/ }).click();
  await expect(page.getByRole('dialog')).toContainText('missing_e2e_dependency');
  await expect(page.getByRole('dialog')).toContainText('ModuleNotFoundError');
  await page.getByRole('button', { name: '完成', exact: true }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await page.getByRole('button', { name: '智能体工具', exact: true }).click();
  await expect(page.getByRole('heading', { name: '智能体工具', exact: true })).toBeVisible();
  expect(faults).toEqual([]);
});

test('tool collections, layout and recents remain useful after a reload', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: '列表视图', exact: true }).click();
  await expect(page.locator('.tool-collection')).toHaveClass(/is-list/);
  await page.getByRole('button', { name: '收藏 后台任务测试', exact: true }).click();
  await page.getByRole('button', { name: /^收藏\s*1$/ }).click();
  await expect(page.locator('.tool-tile')).toHaveCount(1);
  await page.getByRole('textbox', { name: '搜索工作台工具' }).fill('no-such-tool');
  await expect(page.locator('.tool-tile')).toHaveCount(0);
  await page.getByRole('button', { name: '清除筛选', exact: true }).click();
  await page.getByRole('button', { name: /测试 后台任务测试/ }).click();
  await page.getByRole('button', { name: '工作台', exact: true }).click();
  await expect(page.getByRole('region', { name: '最近使用' })).toContainText('后台任务测试');
  await page.reload();
  await expect(page.locator('.tool-collection')).toHaveClass(/is-list/);
  await expect(page.getByRole('region', { name: '最近使用' })).toContainText('后台任务测试');
  await expect(
    page.getByRole('button', { name: '取消收藏 后台任务测试', exact: true }),
  ).toHaveAttribute('aria-pressed', 'true');
  await page.getByRole('button', { name: '卡片视图', exact: true }).click();
  await expect(page.locator('.tool-collection')).toHaveClass(/is-grid/);
});

test('authorization drafts survive navigation and the direct client shortcut does not save them', async ({
  page,
  request,
}) => {
  await request.post('/api/assistant_allow', { data: [[]] });
  await page.goto('/');
  await page.getByRole('button', { name: '智能体工具', exact: true }).click();
  const checkbox = page.getByRole('checkbox', { name: /终端夹具/ });
  await checkbox.check();
  const save = page.getByRole('button', { name: '保存授权', exact: true });
  await expect(save).toBeEnabled();
  await page.waitForResponse((response) => response.url().endsWith('/api/assistant_state'));
  await expect(checkbox).toBeChecked();
  await expect(save).toBeEnabled();
  await page.getByRole('button', { name: '插件', exact: true }).click();
  await page.getByRole('button', { name: '智能体工具', exact: true }).click();
  await expect(checkbox).toBeChecked();
  await expect(save).toBeEnabled();
  await page.getByRole('button', { name: '连接客户端', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'MCP 连接', exact: true })).toBeVisible();
  await expect(page.getByLabel('连接状态')).toContainText('客户端配置');
  await expect(page.getByLabel('连接状态')).toContainText('适配器');
  await expect(page.getByLabel('连接状态')).toContainText('工具调用');
  await page.getByRole('button', { name: 'Codex 连接详情', exact: true }).click();
  await expect(page.getByRole('dialog')).toContainText('在 Codex 中使用');
  await expect(page.getByRole('dialog')).toContainText('验证第一次工具调用');
  await page.getByRole('button', { name: '关闭使用指南', exact: true }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  const before = await (await request.post('/api/assistant_state', { data: [] })).json();
  expect(before.result.selected).toEqual([]);
  await page.getByRole('button', { name: '智能体工具', exact: true }).click();
  await expect(checkbox).toBeChecked();
  await save.click();
  await expect(save).toBeDisabled();
  const after = await (await request.post('/api/assistant_state', { data: [] })).json();
  expect(after.result.selected).toEqual(['test.terminal']);
});
