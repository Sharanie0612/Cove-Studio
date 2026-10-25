import { expect, test } from '@playwright/test';
for (const locale of ['zh-CN', 'en-US']) {
  test(`installer steps, real progress presentation and finish options in ${locale}`, async ({
    page,
  }, testInfo) => {
    await page.setViewportSize({ width: 640, height: 520 });
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.addInitScript((locale) => {
      document.addEventListener('DOMContentLoaded', () => {
        document.documentElement.dataset.windowFrame = 'alpha';
      });
      let calls = 0;
      (window as any).pywebview = {
        api: {
          state: async () => ({
            version: '0.12.12',
            directory: 'C:\\Users\\Example\\Programs\\Cove',
            locale,
            license: 'MIT License\nPermission is hereby granted, free of charge.',
            previewPage: '',
          }),
          set_locale: async () => ({ ok: true }),
          window_action: async () => ({ ok: true }),
          install: async (_directory: string, accepted: boolean, close: boolean) => {
            (window as any).setupCalls = ++calls;
            if (!accepted || !close) return { ok: false, code: 'DESKTOP_RUNNING' };
            return new Promise((resolve) => {
              (window as any).completeSetup = () => resolve({ ok: true });
            });
          },
          progress: async () => ({
            phase: 'copying',
            percent: 45,
            completedFiles: 10,
            totalFiles: 20,
          }),
          finish: async (launch: boolean, desktop: boolean) => {
            (window as any).finishOptions = { launch, desktop };
            return { ok: true };
          },
        },
      };
    }, locale);
    await page.goto('/setup.html');
    const en = locale === 'en-US';
    const primary = page.locator('.setup-footer .primary');
    await expect(
      page.getByRole('heading', {
        name: en ? 'Choose setup language' : '选择安装语言',
        exact: true,
      }),
    ).toBeVisible();
    await expect(page.getByRole('combobox')).toHaveValue(locale);
    await expect(primary).toBeEnabled();
    const material = await primary.evaluate((el) => ({
      radius: getComputedStyle(el).borderRadius,
      color: getComputedStyle(el).backgroundColor,
      font: getComputedStyle(el).fontFamily,
    }));
    expect(material.radius).toBe('8px');
    expect(material.color).toBe('rgb(83, 111, 148)');
    expect(material.font).toContain('Cove Sans');
    await page.screenshot({ path: testInfo.outputPath(`language-${locale}.png`) });
    await primary.click();
    await expect(
      page.getByLabel(en ? 'Installation folder' : '安装位置', { exact: true }),
    ).toHaveValue('C:\\Users\\Example\\Programs\\Cove');
    await page.getByRole('button', { name: en ? 'Back' : '上一步', exact: true }).click();
    await expect(page.getByRole('combobox')).toHaveValue(locale);
    await primary.click();
    await page.screenshot({ path: testInfo.outputPath(`location-${locale}.png`) });
    await primary.click();
    await expect(
      page.getByRole('heading', { name: en ? 'Review the license' : '阅读开源许可', exact: true }),
    ).toBeVisible();
    await expect(primary).toBeDisabled();
    await page.getByRole('checkbox').check();
    await page.screenshot({ path: testInfo.outputPath(`license-${locale}.png`) });
    await primary.click();
    const consent = page.getByRole('alertdialog');
    await expect(consent).toBeVisible();
    await expect(
      consent.getByRole('button', { name: en ? 'Cancel' : '取消', exact: true }),
    ).toBeFocused();
    await consent.getByRole('button', { name: en ? 'Cancel' : '取消', exact: true }).click();
    expect(await page.evaluate(() => (window as any).setupCalls)).toBe(1);
    await primary.click();
    await consent
      .getByRole('button', { name: en ? 'Close and continue' : '退出并继续', exact: true })
      .click();
    await expect(page.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '45');
    expect(
      await page
        .locator('.setup-progress-track')
        .evaluate(
          (el) =>
            el.firstElementChild!.getBoundingClientRect().width / el.getBoundingClientRect().width,
        ),
    ).toBeCloseTo(0.45, 2);
    await expect(primary).toBeDisabled();
    await expect(
      page.getByRole('button', { name: en ? 'Close setup' : '关闭安装器', exact: true }),
    ).toBeDisabled();
    await page.screenshot({ path: testInfo.outputPath(`progress-${locale}.png`) });
    await page.evaluate(() => (window as any).completeSetup());
    await expect(
      page.getByRole('heading', { name: en ? 'Setup complete' : '安装完成', exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole('checkbox', {
        name: en ? 'Open Cove Studio' : '打开 Cove Studio',
        exact: true,
      }),
    ).toBeChecked();
    await page
      .getByRole('checkbox', { name: en ? 'Open Cove Studio' : '打开 Cove Studio', exact: true })
      .uncheck();
    await page
      .getByRole('checkbox', {
        name: en ? 'Create a desktop shortcut' : '创建桌面快捷方式',
        exact: true,
      })
      .uncheck();
    expect(
      await page
        .locator('.setup-content')
        .evaluate((el) => el.scrollWidth <= el.clientWidth && el.scrollHeight <= el.clientHeight),
    ).toBe(true);
    await page.screenshot({ path: testInfo.outputPath(`finish-${locale}.png`) });
    await primary.click();
    expect(await page.evaluate(() => (window as any).finishOptions)).toEqual({
      launch: false,
      desktop: false,
    });
  });
}
