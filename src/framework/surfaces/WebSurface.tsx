import { useEffect, useRef, useState } from 'react';
import { t, getLocale, subscribeLocale } from '../../core/i18n.ts';
import { hostCall, subscribe } from '../../core/bridge';
import type { PluginSurfaceProps } from '../contracts';
import type { Reply } from '../../core/types';
import { VIEW_PROTOCOL, webDocument } from './webDocument';
import './web.css';

export default function WebSurface({ manifest, active, connected, runtime }: PluginSurfaceProps) {
  const frame = useRef<HTMLIFrameElement>(null);
  const [view, setView] = useState<{ ticket: string; document: string }>();
  const [error, setError] = useState('');
  const context = useRef({
    active,
    connected,
    running: Boolean(runtime?.running),
    name: manifest.name,
  });
  context.current = { active, connected, running: Boolean(runtime?.running), name: manifest.name };
  const update = useRef<() => void>(() => {});
  const navigation = useRef<() => void>(() => {});
  const lastPid = useRef(runtime?.pid);
  const [generation, setGeneration] = useState(0);
  useEffect(() => {
    if (runtime?.pid) {
      if (lastPid.current && lastPid.current !== runtime.pid) setGeneration((value) => value + 1);
      lastPid.current = runtime.pid;
    }
  }, [runtime?.pid]);
  useEffect(() => update.current(), [active, connected, runtime?.running, manifest.name]);

  useEffect(() => {
    let disposed = false;
    let ticket = '';
    let ready = false;
    let loads = 0;
    const pending = new Set<string>();
    const post = (value: Record<string, unknown>) => {
      if (!disposed && ready)
        frame.current?.contentWindow?.postMessage(
          { protocol: VIEW_PROTOCOL, session: ticket, ...value },
          '*',
        );
    };
    const sync = () => {
      const root = document.documentElement;
      const tokens = Object.fromEntries(
        Array.from(root.style)
          .filter((key) => key.startsWith('--'))
          .map((key) => [key, root.style.getPropertyValue(key)]),
      );
      post({
        type: 'context',
        value: {
          pluginId: manifest.id,
          locale: getLocale(),
          mode: root.dataset.theme || 'light',
          reducedMotion: matchMedia('(prefers-reduced-motion: reduce)').matches,
          tokens,
          ...context.current,
        },
      });
    };
    update.current = sync;
    const receive = async (event: MessageEvent) => {
      const message = event.data;
      if (
        disposed ||
        !ticket ||
        event.source !== frame.current?.contentWindow ||
        !message ||
        message.protocol !== VIEW_PROTOCOL ||
        message.session !== ticket
      )
        return;
      if (message.type === 'ready') {
        ready = true;
        sync();
        return;
      }
      if (
        message.type !== 'call' ||
        typeof message.id !== 'string' ||
        !/^[0-9]{1,12}$/.test(message.id) ||
        typeof message.name !== 'string' ||
        pending.has(message.id)
      )
        return;
      const id = message.id;
      const sendReply = (reply: Reply) => post({ type: 'reply', id, reply });
      if (pending.size >= 8) {
        sendReply({ ok: false, error: 'Too many pending UI requests' });
        return;
      }
      pending.add(id);
      try {
        const result = await hostCall('plugin_view_call', ticket, message.name, message.arguments);
        sendReply({ ok: true, result });
      } catch (failure) {
        const value = failure as Error & { code?: string; details?: Record<string, string> };
        sendReply({ ok: false, error: value.message, code: value.code, details: value.details });
      } finally {
        pending.delete(id);
      }
    };
    navigation.current = () => {
      if (++loads <= 1 || disposed) return;
      ready = false;
      void hostCall('plugin_view_close', ticket).catch(() => {});
      setView(undefined);
      setError(t('插件界面发生导航，已关闭命令连接。请重新打开工具。'));
    };
    window.addEventListener('message', receive);
    window.addEventListener('cove-appearance-change', sync);
    const media = matchMedia('(prefers-reduced-motion: reduce)');
    media.addEventListener('change', sync);
    const stopLocale = subscribeLocale(sync);
    const stopEvents = subscribe((event) => {
      if (event.pluginId === manifest.id) post({ type: 'event', value: event });
    });
    setError('');
    void hostCall<{ ticket: string; html: string }>('plugin_view_open', manifest.id)
      .then((value) => {
        if (disposed) {
          void hostCall('plugin_view_close', value.ticket).catch(() => {});
          return;
        }
        ticket = value.ticket;
        setView({ ticket, document: webDocument(value.html, ticket) });
      })
      .catch((failure) => {
        if (!disposed) setError(failure.message);
      });
    return () => {
      disposed = true;
      window.removeEventListener('message', receive);
      window.removeEventListener('cove-appearance-change', sync);
      media.removeEventListener('change', sync);
      stopLocale();
      stopEvents();
      if (ticket) void hostCall('plugin_view_close', ticket).catch(() => {});
    };
  }, [manifest.id, manifest.ui.web?.entry, generation]);

  return (
    <section className="plugin-web-surface">
      {error ? (
        <p className="error-note" role="alert">
          {error}
        </p>
      ) : view ? (
        <iframe
          key={view.ticket}
          ref={frame}
          title={t('{p0} 的插件界面', { p0: manifest.name })}
          sandbox="allow-scripts allow-downloads"
          referrerPolicy="no-referrer"
          onLoad={() => navigation.current()}
          srcDoc={view.document}
        />
      ) : (
        <p className="list-empty">{t('正在加载插件自带界面…')}</p>
      )}
    </section>
  );
}
