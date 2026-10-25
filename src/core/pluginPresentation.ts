import { t, getLocale } from './i18n.ts';
import type { Manifest } from './types';

export type SurfaceKind = 'terminal' | 'instrument' | 'job' | 'form';
const originals = new WeakMap<Manifest, Manifest>();
export function categoryKey(tool: Manifest): string {
  return (originals.get(tool) || tool).category;
}
export function localizeTool(tool: Manifest): Manifest {
  tool = originals.get(tool) || tool;
  const messages = tool.localization?.messages[getLocale()];
  if (!messages) return tool;
  const text = (value: string) => (Object.hasOwn(messages, value) ? messages[value] : value);
  // Only presentation keys are translated. IDs, commands, defaults, option values,
  // result data keys, units and confirmation payloads retain their exact bytes.
  const keys = new Set([
    'label',
    'placeholder',
    'title',
    'description',
    'confirmLabel',
    'emptyText',
    'idle',
    'connected',
  ]);
  const presentation = (value: unknown): unknown => {
    if (Array.isArray(value)) return value.map(presentation);
    if (!value || typeof value !== 'object') return value;
    return Object.fromEntries(
      Object.entries(value).map(([key, item]) => [
        key,
        keys.has(key) && typeof item === 'string' ? text(item) : presentation(item),
      ]),
    );
  };
  const localized = {
    ...tool,
    name: text(tool.name),
    subtitle: tool.subtitle && text(tool.subtitle),
    description: text(tool.description),
    category: text(tool.category),
    ai: tool.ai && (presentation(tool.ai) as Manifest['ai']),
    ui: presentation(tool.ui) as Manifest['ui'],
  };
  originals.set(localized, tool);
  return localized;
}
export function surfaceKind(tool: Manifest): SurfaceKind {
  if (tool.ui.surface === 'terminal') return 'terminal';
  if (tool.ui.instrument) return 'instrument';
  if (tool.ui.job) return 'job';
  return 'form';
}
export function toolStatus(tool: Manifest): string {
  if (tool.compatibilityStatus?.supported === false) return t('需要兼容版本');
  if (tool.enabled === false) return t('已停用');
  if (tool.runtime?.connected) return t('已连接');
  if (tool.ui.surface === 'mcp') return t('服务已启用');
  return tool.runtime?.running ? t('运行中') : t('准备就绪');
}
export function filterTools(
  tools: Manifest[],
  query: string,
  category: string,
  favorites: string[],
  onlyFavorites: boolean,
): Manifest[] {
  const search = query.trim().toLocaleLowerCase();
  return tools
    .filter(
      (tool) =>
        (!onlyFavorites || favorites.includes(tool.id)) &&
        (!category || categoryKey(tool) === category) &&
        `${tool.name} ${tool.id} ${tool.description} ${tool.category} ${(originals.get(tool) || tool).name}`
          .toLocaleLowerCase()
          .includes(search),
    )
    .sort(
      (a, b) =>
        Number(favorites.includes(b.id)) - Number(favorites.includes(a.id)) ||
        a.name.localeCompare(b.name, getLocale()),
    );
}
