import { expect, test } from '@playwright/test';

test('compatible older sessions show their version while disconnect remains available', async ({
  page,
}) => {
  await page.route('**/api/mcp_clients', async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    body.result = body.result.map((client: { id: string }) =>
      client.id === 'codex'
        ? {
            ...client,
            configured: true,
            connected: true,
            needsReload: false,
            needsUpdate: true,
            adapterVersions: ['0.12.4', '0.12.6'],
          }
        : client,
    );
    await route.fulfill({ response, json: body });
  });
  await page.goto('/');
  await page.getByRole('button', { name: /连接 MCP 连接/ }).click();
  const card = page
    .locator('.provider-card')
    .filter({ has: page.getByRole('heading', { name: 'Codex', exact: true }) });
  await expect(card).toContainText('会话版本：0.12.4 / 0.12.6');
  await expect(card).toContainText('旧版本会话仍在运行');
  await card.getByRole('button', { name: '断开', exact: true }).click();
  await expect(page.getByRole('dialog', { name: '断开 Codex？' })).toBeVisible();
  await page.getByRole('button', { name: '取消', exact: true }).click();
});

test('legacy adapters show a reload step before disconnect is available', async ({ page }) => {
  await page.route('**/api/mcp_clients', async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    body.result = body.result.map((client: { id: string }) =>
      client.id === 'codex'
        ? { ...client, configured: true, connected: true, needsReload: true }
        : client,
    );
    await route.fulfill({ response, json: body });
  });
  await page.goto('/');
  await page.getByRole('button', { name: /连接 MCP 连接/ }).click();
  const card = page
    .locator('.provider-card')
    .filter({ has: page.getByRole('heading', { name: 'Codex', exact: true }) });
  await card.getByRole('button', { name: '更新会话', exact: true }).click();
  const dialog = page.getByRole('dialog');
  await expect(dialog.getByRole('status').first()).toContainText('升级前的适配器');
  await expect(dialog.getByRole('button', { name: '断开客户端', exact: true })).toBeDisabled();
  await dialog.getByRole('button', { name: '关闭使用指南', exact: true }).click();
});

test('MCP setup, disconnect cancellation, persistent errors and reconnect preserve configuration', async ({
  page,
  request,
}) => {
  await page.goto('/');
  await page.getByRole('button', { name: /连接 MCP 连接/ }).click();
  const card = page
    .locator('.provider-card')
    .filter({ has: page.getByRole('heading', { name: 'Cursor', exact: true }) });
  await card.getByRole('button', { name: '一键接入', exact: true }).click();
  await expect(card).toContainText('等待客户端');
  await expect(card).not.toContainText('适配器在线');
  const installed = await (await request.post('/api/mcp_clients', { data: [] })).json();
  const cursor = installed.result.find((client: { id: string }) => client.id === 'cursor');
  expect(cursor.configured).toBe(true);
  await card.getByRole('button', { name: '继续连接', exact: true }).click();
  await page.getByRole('button', { name: '断开客户端', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: '断开 Cursor？' });
  await expect(dialog.getByRole('button', { name: '取消', exact: true })).toBeFocused();
  await dialog.getByRole('button', { name: '取消', exact: true }).click();
  await expect(dialog).toHaveCount(0);
  await expect(card).toContainText('等待客户端');
  await card.getByRole('button', { name: '继续连接', exact: true }).click();
  await page.getByRole('button', { name: '断开客户端', exact: true }).click();
  await page.route('**/api/mcp_connection', (route) =>
    route.fulfill({ json: { ok: false, error: '测试：连接设置暂时无法保存' } }),
  );
  await dialog.getByRole('button', { name: '断开连接', exact: true }).click();
  await expect(dialog.getByRole('alert')).toContainText('暂时无法保存');
  await page.waitForResponse((response) => response.url().endsWith('/api/mcp_clients'));
  await expect(dialog.getByRole('alert')).toContainText('暂时无法保存');
  await page.unroute('**/api/mcp_connection');
  await dialog.getByRole('button', { name: '断开连接', exact: true }).click();
  await expect(dialog).toHaveCount(0);
  await expect(card).toContainText('已断开');
  await page.reload();
  await page.getByRole('button', { name: /连接 MCP 连接/ }).click();
  await expect(card).toContainText('已断开');
  await card.getByRole('button', { name: '重新连接', exact: true }).click();
  await expect(card).toContainText('等待客户端');
  const resumed = await (await request.post('/api/mcp_clients', { data: [] })).json();
  const current = resumed.result.find((client: { id: string }) => client.id === 'cursor');
  expect(current.configured).toBe(true);
  expect(current.paused).toBe(false);
  expect(current.path).toBe(cursor.path);
});
