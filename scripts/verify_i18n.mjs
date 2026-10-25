import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import parser from 'prettier/plugins/typescript';
import { getLocale, hostMessage, normalizeLocale, setLocale, subscribeLocale, t } from '../src/core/i18n.ts';

const root = new URL('../', import.meta.url);
const catalog = JSON.parse(fs.readFileSync(new URL('src/locales/en-US.json', root), 'utf8'));
const parameters = (text) => [...text.matchAll(/\{(p\d+)\}/g)].map((match) => match[1]).sort();
for (const [source, translation] of Object.entries(catalog)) {
  assert.ok(typeof translation === 'string' && translation.trim(), `Empty translation: ${source}`);
  assert.deepEqual(parameters(translation), parameters(source), `Interpolation mismatch: ${source}`);
}
const han = (value) => typeof value === 'string' && /\p{Script=Han}/u.test(value);
const staticTables = new Set(['components/PluginManager.tsx', 'core/appearance.ts', 'framework/surfaces/instrument/Measurements.tsx']);
let checked = 0;
for (const relative of fs.readdirSync(new URL('src', root), { recursive: true }).filter((name) => /\.tsx?$/.test(name))) {
  const file = relative.replaceAll('\\', '/');
  if (['core/i18n.ts', 'core/useLocale.ts'].includes(file)) continue;
  const source = fs.readFileSync(new URL('src/' + file, root), 'utf8');
  const ast = parser.parsers.typescript.parse(source, { filepath: file });
  function visit(node, ancestors = []) {
    if (!node || typeof node !== 'object') return;
    const parent = ancestors.at(-1);
    if (file === 'content/developerGuide.ts' && ancestors.some((item) => item.type === 'ObjectExpression' && item.properties.some((property) => property.key?.name === 'kind' && property.value?.value === 'code'))) return;
    if ((node.type === 'Literal' || node.type === 'JSXText') && han(node.value)) {
      const inTranslation = parent?.type === 'CallExpression' && parent.callee.name === 't' && parent.arguments[0] === node;
      const staticTable = staticTables.has(file) && !ancestors.some((item) => /Function/.test(item.type));
      assert.ok(inTranslation || staticTable, `Untranslated host text: ${file}:${node.loc.start.line}`);
      assert.ok(Object.hasOwn(catalog, node.value), `Missing English message: ${file}:${node.loc.start.line}: ${node.value}`);
      checked++;
    }
    if (node.type === 'TemplateLiteral') assert.ok(!node.quasis.some((part) => han(part.value.cooked)), `Untranslated template: ${file}:${node.loc.start.line}`);
    for (const [key, value] of Object.entries(node)) if (!['tokens', 'comments', 'loc', 'range'].includes(key)) {
      if (Array.isArray(value)) value.forEach((item) => visit(item, [...ancestors, node]));
      else if (value?.type) visit(value, [...ancestors, node]);
    }
  }
  visit(ast);
}

assert.equal(normalizeLocale('en-GB'), 'en-US');
assert.equal(normalizeLocale('zh-TW'), 'zh-CN');
assert.equal(normalizeLocale('fr-FR'), 'en-US');
let notifications = 0;
const unsubscribe = subscribeLocale(() => notifications++);
setLocale('en-US');
assert.equal(getLocale(), 'en-US');
assert.equal(t('关闭 {p0}', { p0: '<script>data</script>' }), 'Close <script>data</script>');
assert.equal(hostMessage('此客户端已在 Cove 中断开，请在 MCP 连接页重新连接。'), 'This client was disconnected in Cove. Reconnect it in MCP Connections.');
assert.equal(hostMessage('插件启动失败：ImportError。请查看启动诊断或设置独立 Python 环境。'), 'Plugin startup failed: ImportError. Review startup diagnostics or configure a separate Python environment.');
assert.equal(hostMessage('plugin output: 用户数据'), 'plugin output: 用户数据');
assert.equal(t('unknown {p0}', { p0: 'C:\\private\\data' }), 'unknown C:\\private\\data');
setLocale('zh-CN');
assert.equal(t('工作台'), '工作台');
assert.equal(hostMessage('Plugin startup failed: ImportError. Review startup diagnostics or configure a separate Python environment.'), '插件启动失败：ImportError。请查看启动诊断或设置独立 Python 环境。');
assert.equal(notifications, 2);
unsubscribe();
console.log(`Localization passed: ${Object.keys(catalog).length} English messages; ${checked} source references; interpolation and host-error boundaries verified.`);
