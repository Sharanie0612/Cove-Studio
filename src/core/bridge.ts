import { t, hostMessage } from './i18n.ts';
import { version } from '../../package.json';
import type { Catalog, HostApi, Reply, ToolEvent } from './types';

export const fallbackCatalog: Catalog = {
  tools: [],
  issues: [],
  hostVersion: version,
  sdkVersion: 1,
};
type Listener = (event: ToolEvent) => void;
const listeners = new Set<Listener>();
export function subscribe(listener: Listener) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}
export class CommandError extends Error {
  code: string;
  details: Record<string, string>;
  constructor(message: string, code = '', details = {}) {
    super(message);
    this.code = code;
    this.details = details;
  }
}
export async function hostCall<T = unknown>(
  method: Exclude<keyof HostApi, 'catalog' | 'drain_events'>,
  ...args: unknown[]
): Promise<T> {
  const operation = window.pywebview?.api[method];
  if (typeof operation !== 'function') throw new CommandError(t('请在桌面版中使用此功能。'));
  const reply = await (operation as (...params: unknown[]) => Promise<Reply>)(...args);
  if (!reply.ok)
    throw new CommandError(hostMessage(reply.error || t('操作失败')), reply.code, reply.details);
  return reply.result as T;
}
export async function invoke<T = unknown>(
  id: string,
  command: string,
  payload: Record<string, unknown> = {},
): Promise<T> {
  if (!window.pywebview?.api)
    throw new CommandError(t('请启动桌面版以使用本地连接功能。浏览器中可以预览界面。'));
  const reply = await window.pywebview.api.invoke(id, command, payload);
  if (!reply.ok)
    throw new CommandError(hostMessage(reply.error || t('操作失败')), reply.code, reply.details);
  return reply.result as T;
}
export function startEvents() {
  let pending = false;
  const timer = window.setInterval(async () => {
    if (pending || !window.pywebview?.api) return;
    pending = true;
    try {
      const events = await window.pywebview.api.drain_events();
      events.forEach((event) => listeners.forEach((listener) => listener(event)));
    } catch {
      /* The desktop window may be shutting down. */
    } finally {
      pending = false;
    }
  }, 100);
  return () => clearInterval(timer);
}
