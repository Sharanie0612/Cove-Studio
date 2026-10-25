import english from '../locales/en-US.json' with { type: 'json' };

export type Locale = 'zh-CN' | 'en-US';
export const languages = [
  { id: 'zh-CN', name: '简体中文' },
  { id: 'en-US', name: 'English' },
] as const;
const catalog: Record<string, string> = english;
const listeners = new Set<() => void>();
let current: Locale = 'zh-CN';

export function normalizeLocale(value: unknown): Locale {
  return typeof value === 'string' && /^zh(?:-|$)/i.test(value) ? 'zh-CN' : 'en-US';
}
export function getLocale(): Locale {
  return current;
}
export function subscribeLocale(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}
export function setLocale(locale: Locale) {
  current = normalizeLocale(locale);
  if (typeof document !== 'undefined') {
    document.documentElement.lang = current;
    document.documentElement.dir = 'ltr';
  }
  try {
    localStorage.setItem('toolbench:locale-v1', JSON.stringify(current));
  } catch {
    /* Live switching works without storage. */
  }
  listeners.forEach((listener) => listener());
}
export function initializeLocale() {
  let saved: unknown;
  try {
    saved = JSON.parse(localStorage.getItem('toolbench:locale-v1') || 'null');
  } catch {
    /* Use the system language. */
  }
  setLocale(normalizeLocale(saved || navigator.languages?.[0] || navigator.language));
}

/** Source-text keys keep Chinese readable; parameters are interpolated as text, never HTML. */
export function t(message: string, values: Record<string, string | number> = {}): string {
  const translated = current === 'en-US' ? catalog[message] || message : message;
  return translated.replace(/\{(\w+)\}/g, (token, key: string) =>
    Object.hasOwn(values, key) ? String(values[key]) : token,
  );
}

/** Translate recognized host errors; preserve paths, plugin output and unknown diagnostics verbatim. */
export function hostMessage(message: string): string {
  const englishMode = current === 'en-US';
  if (englishMode && catalog[message]) return t(message);
  for (const [source, translated] of Object.entries(catalog)) {
    const from = englishMode ? source : translated;
    const to = englishMode ? translated : source;
    if (message === from) return to;
    if (/[：:]$/.test(from) && message.startsWith(from)) return to + message.slice(from.length);
    if (!from.includes('{p')) continue;
    const names: string[] = [];
    const parts = from.split(/(\{p\d+\})/g).map((part) => {
      if (/^\{p\d+\}$/.test(part)) {
        names.push(part.slice(1, -1));
        return '(.+?)';
      }
      return part.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    });
    const match = new RegExp('^' + parts.join('') + '$', 's').exec(message);
    if (match)
      return to.replace(/\{(p\d+)\}/g, (token, key: string) => {
        const index = names.indexOf(key);
        return index < 0 ? token : match[index + 1];
      });
  }
  return message;
}
