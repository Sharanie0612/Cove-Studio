import { expect, test } from '@playwright/test';

test('plugin catalogs switch labels and calls while preserving drafts, results and worker', async ({
  page,
  request,
}) => {
  await page.goto('/');
  await page.getByRole('combobox', { name: '工具分类', exact: true }).selectOption('示例');
  await page.getByRole('button', { name: '设置', exact: true }).click();
  await page.getByRole('combobox', { name: '界面语言', exact: true }).selectOption('en-US');
  await page.getByRole('button', { name: 'Done', exact: true }).click();
  await expect(page.getByRole('combobox', { name: 'Tool category', exact: true })).toHaveValue(
    '示例',
  );
  await expect(page.getByRole('button', { name: /Examples Hello tool/ })).toBeVisible();
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  await page
    .getByRole('combobox', { name: 'Interface language', exact: true })
    .selectOption('zh-CN');
  await page.getByRole('button', { name: '完成', exact: true }).click();
  await page.getByRole('button', { name: /示例 Hello 工具/ }).click();
  await page.getByRole('button', { name: '打个招呼', exact: true }).first().click();
  await page.getByRole('dialog').getByLabel('姓名', { exact: true }).fill('draft / 保留');
  await page.getByRole('button', { name: '关闭工具配置' }).click();
  await page.getByRole('button', { name: '设置', exact: true }).click();
  await page.getByRole('combobox', { name: '界面语言', exact: true }).selectOption('en-US');
  await page.getByRole('button', { name: 'Done', exact: true }).click();
  await expect(page.getByRole('tab', { name: 'Hello tool', exact: true })).toBeVisible();

  await page.getByRole('button', { name: 'Say hello', exact: true }).first().click();
  await expect(page.getByRole('dialog').getByLabel('Name', { exact: true })).toHaveValue(
    'draft / 保留',
  );
  await page.getByRole('dialog').getByRole('button', { name: 'Say hello', exact: true }).click();
  await expect(page.locator('.generic-output')).toContainText('Hello, draft / 保留!');
  const before = await (await request.post('/api/catalog', { data: [] })).json();
  const pid = before.tools.find((tool: { id: string }) => tool.id === 'community.hello').runtime
    .pid;
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  await page
    .getByRole('combobox', { name: 'Interface language', exact: true })
    .selectOption('zh-CN');
  await page.getByRole('button', { name: '完成', exact: true }).click();
  await expect(page.getByRole('tab', { name: 'Hello 工具', exact: true })).toBeVisible();
  await expect(page.locator('.generic-output')).toContainText('Hello, draft / 保留!');
  const after = await (await request.post('/api/catalog', { data: [] })).json();
  expect(
    after.tools.find((tool: { id: string }) => tool.id === 'community.hello').runtime.pid,
  ).toBe(pid);
});

for (const locale of ['zh-CN', 'en-US'])
  for (const mode of ['light', 'dark']) {
    test(`${locale} ${mode}: shared pages fit the minimum window`, async ({ page }, testInfo) => {
      await page.setViewportSize({ width: 960, height: 660 });
      await page.emulateMedia({ reducedMotion: 'reduce' });
      await page.addInitScript(
        ({ locale, mode }) => {
          localStorage.setItem('toolbench:locale-v1', JSON.stringify(locale));
          localStorage.setItem('toolbench:appearance-v1', JSON.stringify({ mode, scheme: 'cove' }));
        },
        { locale, mode },
      );
      await page.goto('/');
      await expect(page.locator('html')).toHaveAttribute('lang', locale);
      const english = locale === 'en-US';
      for (const [navigation, heading] of english
        ? [
            ['Workbench', 'Workbench'],
            ['Agent Tools', 'Agent Tools'],
            ['Plugins', 'Plugins'],
            ['Developer Guide', 'Plugin development'],
          ]
        : [
            ['工作台', '工作台'],
            ['智能体工具', '智能体工具'],
            ['插件', '插件'],
            ['开发指南', '插件开发'],
          ]) {
        await page
          .locator('.app-sidebar')
          .getByRole('button', { name: navigation, exact: true })
          .click();
        await expect(page.getByRole('heading', { name: heading, exact: true })).toBeVisible();
        const geometry = await page
          .locator('.content-main')
          .evaluate((element) => ({ width: element.clientWidth, scroll: element.scrollWidth }));
        expect(geometry.scroll, navigation).toBeLessThanOrEqual(geometry.width + 1);
        if (navigation === 'Plugins' || navigation === '插件') {
          const rows = await page.locator('.plugin-overview').evaluateAll((elements) =>
            elements.map((row) => {
              const icon = row.querySelector('.tool-icon')!.getBoundingClientRect();
              const svg = row.querySelector('.tool-icon svg')!.getBoundingClientRect();
              const description = row.querySelector('.plugin-description')!.getBoundingClientRect();
              const card = row.closest('.plugin-entry')!.getBoundingClientRect();
              const bounds = row.getBoundingClientRect();
              return {
                inset: icon.left - card.left,
                textGap: description.left - icon.right,
                centerOffset: Math.abs(icon.y + icon.height / 2 - bounds.y - bounds.height / 2),
                svgOffset: Math.abs(svg.x - icon.x) + Math.abs(svg.y - icon.y),
              };
            }),
          );
          for (const row of rows) {
            expect(row.inset).toBeGreaterThanOrEqual(16);
            expect(row.textGap).toBeGreaterThanOrEqual(12);
            expect(row.centerOffset).toBeLessThan(1);
            expect(row.svgOffset).toBeLessThan(1);
          }
          await page.screenshot({ path: testInfo.outputPath(`plugins-${locale}-${mode}.png`) });
        }
      }
      await page
        .locator('.app-sidebar')
        .getByRole('button', { name: english ? 'Workbench' : '工作台', exact: true })
        .click();
      await page
        .locator('.tool-launch')
        .filter({ hasText: english ? 'MCP Connections' : 'MCP 连接' })
        .click();
      await expect(
        page.getByRole('heading', { name: english ? 'MCP Connections' : 'MCP 连接', exact: true }),
      ).toBeVisible();
      await expect(page.locator('.provider-card')).toHaveCount(7);
      if (english)
        for (const text of await page
          .locator('.mcp-summary, .provider-state, .provider-caption')
          .allTextContents())
          expect(text).not.toMatch(/\p{Script=Han}/u);
      if (english) {
        await page.getByRole('button', { name: 'Codex connection details', exact: true }).click();
        await expect(
          page.getByRole('heading', { name: 'Use Cove in Codex', exact: true }),
        ).toBeVisible();
        expect(await page.locator('.connection-steps').innerText()).not.toMatch(/\p{Script=Han}/u);
        await page.getByRole('button', { name: 'Close setup guide', exact: true }).click();
      }
      await page.screenshot({ path: testInfo.outputPath(`mcp-${locale}-${mode}.png`) });
      await page
        .locator('.app-sidebar')
        .getByRole('button', { name: english ? 'Settings' : '设置', exact: true })
        .click();
      const done = page.getByRole('button', { name: english ? 'Done' : '完成', exact: true });
      await done.focus();
      await expect(done).toBeInViewport();
    });
  }

test('language selection persists and updates mounted terminal and workspaces in place', async ({
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
  await request.post('/api/invoke', {
    data: [
      'test.terminal',
      'connect',
      { ...values, trust_fingerprint: challenge.details.fingerprint },
    ],
  });
  try {
    await page.goto('/');
    await page.getByRole('button', { name: /测试 终端夹具/ }).click();
    const terminal = page.locator('.xterm-mount .xterm');
    await expect(terminal).toBeVisible();
    const node = await terminal.elementHandle();
    await page.getByRole('button', { name: '设置', exact: true }).click();
    await page.getByRole('combobox', { name: '界面语言', exact: true }).selectOption('en-US');
    await expect(page.getByRole('heading', { name: 'Settings', exact: true })).toBeVisible();
    await expect(
      page.getByRole('combobox', { name: 'Interface language', exact: true }),
    ).toHaveValue('en-US');
    await page.getByRole('button', { name: 'Done', exact: true }).click();
    await expect(terminal).toBeVisible();
    expect(await node!.evaluate((element) => element.isConnected)).toBe(true);
    await expect(page.getByRole('tab', { name: 'Terminal fixture', exact: true })).toBeVisible();
    const catalog = await (await request.post('/api/catalog', { data: [] })).json();
    expect(
      catalog.tools.find((tool: { id: string }) => tool.id === 'test.terminal').runtime.connected,
    ).toBe(true);
    await page.getByRole('button', { name: 'Workbench', exact: true }).click();
    await page.reload();
    await expect(page.getByRole('heading', { name: 'Workbench', exact: true })).toBeVisible();
    await page.getByRole('button', { name: 'Settings', exact: true }).click();
    await page
      .getByRole('combobox', { name: 'Interface language', exact: true })
      .selectOption('zh-CN');
    await expect(page.getByRole('heading', { name: '设置', exact: true })).toBeVisible();
  } finally {
    await request.post('/api/invoke', { data: ['test.terminal', 'disconnect', {}] });
  }
});

test('first launch uses the system language and a saved choice overrides it', async ({
  browser,
}) => {
  const context = await browser.newContext({ locale: 'en-US' });
  try {
    const page = await context.newPage();
    await page.goto('http://127.0.0.1:18320');
    await expect(page.getByRole('heading', { name: 'Workbench', exact: true })).toBeVisible();
    await page.getByRole('button', { name: 'Settings', exact: true }).click();
    await page
      .getByRole('combobox', { name: 'Interface language', exact: true })
      .selectOption('zh-CN');
    await page.reload();
    await expect(page.getByRole('heading', { name: '工作台', exact: true })).toBeVisible();
  } finally {
    await context.close();
  }
});
