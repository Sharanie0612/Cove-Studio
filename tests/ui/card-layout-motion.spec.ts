import { expect, test } from '@playwright/test';

for (const locale of ['zh-CN', 'en-US'])
  for (const mode of ['light', 'dark']) {
    test(`${locale} ${mode}: MCP cards keep equal dimensions across states and window sizes`, async ({
      page,
    }, testInfo) => {
      await page.emulateMedia({ reducedMotion: 'reduce' });
      await page.addInitScript(
        ({ locale, mode }) => {
          localStorage.setItem('toolbench:locale-v1', JSON.stringify(locale));
          localStorage.setItem('toolbench:appearance-v1', JSON.stringify({ mode, scheme: 'cove' }));
        },
        { locale, mode },
      );
      await page.route('**/api/mcp_clients', async (route) => {
        const response = await route.fetch();
        const body = await response.json();
        body.result = body.result.map((client: { id: string }, index: number) => ({
          ...client,
          configured: index !== 1,
          connected: index === 0,
          paused: index === 2,
          needsUpdate: index === 0,
          needsRepair: index === 3,
          adapterVersions:
            index === 0 ? ['0.12.11'] : index === 2 ? ['0.12.4', '0.12.6', '0.12.10'] : [],
          issue: index === 3 ? 'Diagnostic / 诊断 '.repeat(18) : '',
        }));
        await route.fulfill({ response, json: body });
      });
      await page.goto('/');
      await page.locator('.tool-tile').filter({ hasText: 'MCP' }).locator('.tool-launch').click();
      await expect(page.locator('.provider-version').first()).toContainText('0.12.11');
      for (const width of [960, 1168, 1380]) {
        await page.setViewportSize({ width, height: 660 });
        const metrics = await page.locator('.provider-card').evaluateAll((cards) =>
          cards.map((card) => {
            const button = card.querySelector('.provider-card-footer > button')!;
            const bounds = card.getBoundingClientRect();
            const action = button.getBoundingClientRect();
            const version = card.querySelector('.provider-version');
            const range = document.createRange();
            if (version) range.selectNodeContents(version);
            return {
              width: bounds.width,
              height: bounds.height,
              overflow: card.scrollWidth > card.clientWidth,
              buttonHeight: action.height,
              buttonBottom: bounds.bottom - action.bottom,
              buttonInside: action.right <= bounds.right && action.left >= bounds.left,
              versionTextHeight: version ? range.getBoundingClientRect().height : 0,
              versionLineHeight: version ? parseFloat(getComputedStyle(version).lineHeight) : 0,
            };
          }),
        );
        expect(metrics.length).toBe(7);
        expect(new Set(metrics.map((card) => card.height)).size).toBe(1);
        expect(
          Math.max(...metrics.map((card) => card.width)) -
            Math.min(...metrics.map((card) => card.width)),
        ).toBeLessThan(1);
        expect(new Set(metrics.map((card) => card.buttonHeight)).size).toBe(1);
        expect(new Set(metrics.map((card) => card.buttonBottom)).size).toBe(1);
        for (const card of metrics) {
          expect(card.overflow).toBe(false);
          expect(card.buttonInside).toBe(true);
          expect(card.versionTextHeight).toBeLessThanOrEqual(card.versionLineHeight + 2);
          expect(card.buttonHeight).toBeLessThan(40);
        }
        expect(
          await page.locator('.mcp-slot').evaluate((e) => e.scrollWidth <= e.clientWidth),
        ).toBe(true);
        if (width === 1168)
          await page.screenshot({ path: testInfo.outputPath(`mcp-cards-${locale}-${mode}.png`) });
      }
      const description = page.locator('.provider-description').nth(3);
      await expect(description).toContainText('Diagnostic / 诊断');
      await description.evaluate((element) => {
        element.scrollTop = element.scrollHeight;
      });
      expect(await description.evaluate((element) => element.scrollTop)).toBeGreaterThan(0);
    });
  }

test('motion renders intermediate frames, preserves card geometry and respects reduced motion', async ({
  page,
}, testInfo) => {
  await page.emulateMedia({ reducedMotion: 'no-preference' });
  await page.goto('/');
  const tile = page.locator('.tool-tile').first();
  await expect(tile).toBeVisible();
  await tile.evaluate(async (element) => {
    await Promise.all(element.getAnimations().map((animation) => animation.finished));
  });
  const before = await tile.boundingBox();
  await tile.hover();
  await expect.poll(async () => (await tile.boundingBox())!.y).toBeLessThan(before!.y - 1);
  const after = await tile.boundingBox();
  expect(after!.width).toBeCloseTo(before!.width, 3);
  expect(after!.height).toBeCloseTo(before!.height, 3);
  const toggle = page.locator('.sidebar-toggle');
  await toggle.click();
  const sidebarFrames = await page.locator('.app-sidebar').evaluate(async (element) => {
    await new Promise(requestAnimationFrame);
    const animations = element.getAnimations();
    animations.forEach((animation) => animation.pause());
    const duration = Math.max(
      ...animations.map((animation) => Number(animation.effect!.getTiming().duration)),
    );
    return [0, duration / 2, duration].map((time) => {
      animations.forEach((animation) => {
        animation.currentTime = time;
      });
      const width = element.getBoundingClientRect().width;
      if (time === duration) animations.forEach((animation) => animation.finish());
      return width;
    });
  });
  expect(sidebarFrames[0]).toBeGreaterThan(sidebarFrames[1]);
  expect(sidebarFrames[1]).toBeGreaterThan(sidebarFrames[2]);
  await page.getByRole('button', { name: '设置', exact: true }).click();
  const dialog = page.getByRole('dialog');
  await expect(dialog).toBeVisible();
  const dialogFrames = await dialog.evaluate((element) => {
    const animation = element
      .getAnimations()
      .find((animation) => animation instanceof CSSAnimation)!;
    animation.pause();
    const duration = Number(animation.effect!.getTiming().duration);
    const frames = [0, duration / 2, duration].map((time) => {
      animation.currentTime = time;
      const style = getComputedStyle(element);
      return { opacity: Number(style.opacity), transform: style.transform };
    });
    animation.finish();
    return frames;
  });
  expect(dialogFrames[0].opacity).toBe(0);
  expect(dialogFrames[1].opacity).toBeGreaterThan(0.5);
  expect(dialogFrames[0].transform).not.toBe(dialogFrames[1].transform);
  expect(dialogFrames[2].opacity).toBe(1);
  await page.emulateMedia({ reducedMotion: 'reduce' });
  expect(await dialog.evaluate((element) => element.getAnimations().length)).toBe(0);
  const done = page.getByRole('button', { name: '完成', exact: true });
  await done.hover();
  await page.mouse.down();
  expect(await done.evaluate((element) => getComputedStyle(element).transform)).toBe('none');
  await page.mouse.up();
  await expect(dialog).toHaveCount(0);
  await testInfo.attach('motion-frames.json', {
    body: JSON.stringify({ sidebarFrames, dialogFrames }),
    contentType: 'application/json',
  });
});
