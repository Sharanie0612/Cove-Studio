# Interface languages

Cove supports Simplified Chinese (`zh-CN`) and English (`en-US`). Choose **Settings → Interface language**. On first launch, the browser/system language selects Chinese for `zh-*` and English otherwise. A saved choice takes precedence later.

The choice is stored locally under `toolbench:locale-v1`. If storage is unavailable, switching works for the current session. Switching updates `html.lang`, labels, accessible names, help and locale-sensitive formatting without remounting workspaces or restarting connections. Windows-owned file-picker controls follow Windows display language; Cove-owned picker labels follow the interface language.

## Messages

Use `t()` from `src/core/i18n.ts` for host-owned text, including tooltips, confirmations, empty states and tutorials. Chinese source text is the message key; provide its English value in `src/locales/en-US.json` in the same change. Resolve translations at render/call time, not module initialization.

```tsx
t('关闭 {p0}', { p0: tool.name })
```

Translate complete sentences and preserve interpolation names so languages can reorder values. Interpolation handles text only: no HTML parsing or template evaluation. React escapes the resulting content.

Known core errors are translated at the desktop presentation boundary. Paths, protocol names, identifiers, third-party output, raw diagnostics and executable examples stay intact. Plugins own their business translations. Cove resolves declared presentation messages at render time; switching language never rewrites installed manifests, defaults, user values or existing results. SDK and command-line diagnostics retain their original contracts and source language.

Use `getLocale()` with `Intl` formatting and sorting. Selector language names stay in their native language so users can recover from an accidental choice.

## Plugin catalogs (Cove 0.12.11+)

A plugin can opt into `ui.i18n` with `compatibility.minHostVersion: "0.12.11"`. Declare its own source-text messages in `manifest.json`:

```json
"localization": {
  "defaultLocale": "zh-CN",
  "messages": {
    "en-US": {
      "姓名": "Name",
      "打个招呼": "Say hello",
      "你好，{name}！": "Hello, {name}!"
    }
  }
}
```

The host resolves names, subtitles, categories, descriptions, field/option labels, placeholders, action labels, empty/status text, result-layout headings and confirmation copy. It does not translate identifiers, commands, defaults, option values, result keys/values, units, paths, user text or executable examples. Missing catalogs/messages fall back to the original text. Old plugins remain compatible but cannot acquire an absent translation automatically. Translation is local and does not call a translation service.

Use `self.context.locale` to read the current host language and `self.context.t("你好，{name}！", name=name)` for new plugin-generated messages. Locale reads use the existing SDK bridge and need no `host.tools` permission. They do not authorize tool calls. Read/translate at call time; cached strings and old results retain their original content. Language changes do not restart workers or connections. Standalone portable MCP has no desktop preference and uses the plugin's declared default locale. The starter example includes a catalog and demonstrates both calls.

## Installer

Setup and uninstall include Chinese/English in `packaging/languages.nsh`. The shared setup frontend starts with a language page, followed by installation location, license, progress and completion. Silent setup accepts `/LANGUAGE=2052` for Chinese or `/LANGUAGE=1033` for English and does not open the selector. Installer language and the app's saved language are independent. Never write language preferences into existing client configurations.

## Verification

Run `npm run test:i18n`, `npm run test:frontend`, `npm run build` and `npm run test:ui`. Catalog checks verify source keys, nonempty English values and matching interpolation names. UI checks cover first-run selection, persistence, live switching, preserved terminal instances and Chinese/English layouts in light/dark mode at 960 × 660 with reduced motion.

Add another language only with a complete catalog, native selector label, fallback behavior, installer strings where supported and equivalent accessibility/layout checks.

## 简体中文说明

首批支持简体中文和英语。在“设置 → 界面语言”切换并自动保存，不重建工作区或断开连接。新增文案须同步补齐英语，使用完整句子和插值参数。路径、协议、用户数据、插件结果与可执行示例保留原样；插件通过 localization 声明业务译文，由主程序实时解析；旧插件缺少译文时回退原文，不自动翻译用户数据或旧结果。安装器语言与应用语言独立，Windows 自有控件遵循系统显示语言。
