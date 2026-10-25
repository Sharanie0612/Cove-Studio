import { expect, test, type Page } from '@playwright/test';

const plugin = 'test.terminal';

async function configureConnection(page: Page, port: number) {
  await page
    .locator('.terminal-toolbar')
    .getByRole('button', { name: '新建连接', exact: true })
    .click();
  const dialog = page.locator('dialog.connection-dialog');
  await dialog.getByLabel('测试地址', { exact: true }).fill('localhost');
  await dialog.getByLabel('测试用户名', { exact: true }).fill('demo');
  await dialog.getByLabel('测试秘密', { exact: true }).fill('test-only');
  await expect(dialog.locator('.advanced-fields')).not.toHaveAttribute('open');
  await dialog.locator('.advanced-fields summary').click();
  await dialog.getByLabel('端口', { exact: true }).fill(String(port));
  return dialog;
}

test.beforeEach(async ({ request }) => {
  await request.post('/api/invoke', { data: [plugin, 'disconnect', {}] });
});

test.afterEach(async ({ request }) => {
  await request.post('/api/invoke', { data: [plugin, 'disconnect', {}] });
});

test('profile editing shares the command gate, omits secrets and confirms deletion', async ({
  page,
  request,
}) => {
  const fixture = await (await request.get('/fixture')).json();
  const faults: string[] = [];
  page.on('pageerror', (error) => faults.push(error.message));
  await page.goto('/');
  await page.getByRole('button', { name: /测试 终端夹具/ }).click();
  const dialog = await configureConnection(page, fixture.port);
  const name = `Workspace profile ${Date.now()}`;
  await dialog.getByRole('textbox', { name: '连接名称' }).fill(name);

  let releaseSave = () => {};
  const pausedSave = new Promise<void>((resolve) => {
    releaseSave = resolve;
  });
  const commands: string[] = [];
  await page.route('**/api/invoke', async (route) => {
    const [id, command] = route.request().postDataJSON();
    if (id === plugin) commands.push(command);
    if (id === plugin && command === 'save_profile') await pausedSave;
    await route.continue();
  });
  try {
    await dialog.getByRole('button', { name: '保存', exact: true }).click();
    await expect(dialog.getByRole('button', { name: '保存', exact: true })).toBeDisabled();
    await page.keyboard.press('Control+Enter');
    expect(commands.filter((command) => command === 'save_profile')).toHaveLength(1);
    expect(commands).not.toContain('connect');
  } finally {
    releaseSave();
  }
  await expect(dialog.getByRole('button', { name: '保存', exact: true })).toBeEnabled();
  await page.unroute('**/api/invoke');
  const profiles = await (
    await request.post('/api/invoke', { data: [plugin, 'list_profiles', {}] })
  ).json();
  const saved = profiles.result.profiles.find((profile: { name: string }) => profile.name === name);
  expect(saved.values.host).toBe('localhost');
  expect(saved.values.password).toBeUndefined();
  const snapshot = await (
    await request.post('/api/invoke', { data: [plugin, 'snapshot', {}] })
  ).json();
  expect(snapshot.result.connected).toBe(false);

  await dialog.getByRole('button', { name: '关闭连接配置' }).click();
  await expect(dialog).toHaveCount(0);
  await page.getByRole('button', { name: '连接配置', exact: true }).click();
  const reopened = page.getByRole('dialog', { name, exact: true });
  await expect(reopened.getByLabel('测试秘密', { exact: true })).toHaveValue('');
  await expect(reopened.locator('.advanced-fields')).not.toHaveAttribute('open');
  await reopened.getByRole('button', { name: '关闭连接配置' }).click();
  await expect(reopened).toHaveCount(0);

  await page.getByRole('button', { name: '管理连接', exact: true }).click();
  const manager = page.getByRole('dialog', { name: '连接管理', exact: true });
  await manager.getByRole('textbox', { name: '搜索连接' }).fill(name);
  const remove = manager.getByRole('button', { name: `删除连接 ${name}`, exact: true });
  await remove.click();
  const confirmation = page.getByRole('dialog', { name: '删除这个连接？', exact: true });
  await confirmation.getByRole('button', { name: '取消', exact: true }).click();
  await expect(confirmation).toHaveCount(0);
  await expect(remove).toBeFocused();
  await remove.click();
  await confirmation.getByRole('button', { name: '删除连接', exact: true }).click();
  await expect(confirmation).toHaveCount(0);
  await expect(remove).toHaveCount(0);
  await expect(manager).toContainText('没有匹配的连接');
  expect(faults).toEqual([]);
});

test('declared confirmation gates connection and the mounted terminal survives workspace navigation', async ({
  page,
  request,
}) => {
  const fixture = await (await request.get('/fixture')).json();
  await page.goto('/');
  await page.getByRole('button', { name: /测试 终端夹具/ }).click();
  const configuration = await configureConnection(page, fixture.port);
  await page.keyboard.press('Control+Enter');
  const confirmation = page.getByRole('dialog', { name: '确认测试会话', exact: true });
  await expect(confirmation).toContainText('测试标记');
  await confirmation.getByRole('button', { name: '取消', exact: true }).click();
  await expect(confirmation).toHaveCount(0);
  await expect(configuration).toBeVisible();
  const before = await (
    await request.post('/api/invoke', { data: [plugin, 'snapshot', {}] })
  ).json();
  expect(before.result.connected).toBe(false);

  await configuration.getByRole('button', { name: '连接测试', exact: true }).click();
  await expect(confirmation).toBeVisible();
  await confirmation.getByRole('button', { name: '确认并连接', exact: true }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(page.getByRole('button', { name: '断开', exact: true })).toBeVisible();
  const saved = await page.evaluate(
    (id) => JSON.parse(localStorage.getItem(`toolbench:${id}:last`) || '{}'),
    plugin,
  );
  expect(saved.password).toBeUndefined();
  const terminal = page.locator('.xterm-mount .xterm');
  const node = await terminal.elementHandle();
  expect(node).not.toBeNull();
  await page.keyboard.press('Control+Shift+f');
  await expect(page.locator('.tool-workspace.is-focused')).toBeVisible();
  await page.keyboard.press('Control+Shift+f');
  await page.getByRole('button', { name: '工作台', exact: true }).click();
  await page.getByRole('tab', { name: '终端夹具', exact: true }).click();
  await expect(terminal).toBeVisible();
  expect(await node!.evaluate((element) => element.isConnected)).toBe(true);
  await page.getByRole('button', { name: '断开', exact: true }).click();
  await expect(page.getByRole('combobox', { name: '选择连接' })).toBeVisible();
  await page.keyboard.press('Control+Enter');
  await expect(page.getByRole('dialog').getByLabel('测试秘密', { exact: true })).toHaveValue('');
});
