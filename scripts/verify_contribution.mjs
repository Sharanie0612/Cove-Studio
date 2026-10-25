import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('../', import.meta.url));
export function validTitle(title) {
  return typeof title === 'string' && !/[\r\n\x00-\x1f]/.test(title) &&
    Array.from(title).length <= 96 &&
    /^(feat|fix|refactor|perf|docs|test|build|ci|chore|revert)(\([a-z0-9][a-z0-9-]*\))?!?: \S.{2,}$/.test(title) &&
    title === title.trim();
}

for (const title of ['feat(i18n): add English interface', 'docs: 完善贡献说明', 'feat(sdk)!: replace a public contract']) assert.ok(validTitle(title));
for (const title of ['', 'Update README', 'feat: ', 'fix: ok\nextra', 'unknown: add a thing', 'feat(Upper): add a thing', 'docs: ' + 'x'.repeat(100)]) assert.equal(validTitle(title), false);

const titleIndex = process.argv.indexOf('--title');
const title = titleIndex >= 0 ? process.argv[titleIndex + 1] : process.env.PR_TITLE;
if (title !== undefined || titleIndex >= 0) assert.ok(validTitle(title), 'PR title must use type(scope): summary, one line, at most 96 characters; see CONTRIBUTING.md.');

const documents = ['README.md', 'README.zh-CN.md', 'AGENTS.md', 'CONTRIBUTING.md', 'docs/localization.md', '.github/pull_request_template.md'];
for (const name of documents) {
  const file = path.join(root, name), text = fs.readFileSync(file, 'utf8');
  assert.equal((text.match(/^```/gm) || []).length % 2, 0, `Unclosed code fence: ${name}`);
  const targets = [...text.matchAll(/\[[^\]]*\]\(([^)]+)\)|(?:src|srcset)="([^"]+)"/g)].map((match) => (match[1] || match[2]).replace(/^<|>$/g, ''));
  for (const target of targets) {
    if (/^(?:https?:|mailto:|#)/.test(target)) continue;
    assert.ok(fs.existsSync(path.resolve(path.dirname(file), target.split('#')[0])), `Broken local link in ${name}: ${target}`);
  }
}
assert.ok(fs.readFileSync(path.join(root, 'README.md'), 'utf8').includes('README.zh-CN.md'));
assert.ok(fs.readFileSync(path.join(root, 'README.zh-CN.md'), 'utf8').includes('README.md'));
console.log('Contribution rules, PR title policy and documentation links passed.');
