export const VIEW_PROTOCOL = 'cove.ui.v1';

/** Runs only inside the opaque-origin iframe. Never receives a native API. */
export function bootstrapView(protocol: string, session: string) {
  let context: Record<string, unknown> = {};
  let sequence = 0;
  const pending = new Map<
    string,
    { resolve: (value: unknown) => void; reject: (error: Error) => void; timer: number }
  >();
  const listeners = new Map<string, Set<(value: unknown) => void>>();
  const send = (message: Record<string, unknown>) =>
    parent.postMessage({ protocol, session, ...message }, '*');
  const emit = (name: string, value: unknown) =>
    listeners.get(name)?.forEach((callback) => callback(value));
  const on = (name: string, callback: (value: unknown) => void) => {
    if (!listeners.has(name)) listeners.set(name, new Set());
    listeners.get(name)!.add(callback);
    return () => listeners.get(name)?.delete(callback);
  };
  const ready = new Promise((resolve) => {
    const stop = on('context', (value) => {
      stop();
      resolve(value);
    });
  });
  Object.defineProperty(window, 'Cove', {
    value: Object.freeze({
      version: 1,
      ready,
      get context() {
        return context;
      },
      on,
      call(name: string, args: Record<string, unknown> = {}) {
        if (pending.size >= 8) return Promise.reject(new Error('Too many pending UI requests'));
        const id = String(++sequence);
        return new Promise((resolve, reject) => {
          const timer = window.setTimeout(() => {
            pending.delete(id);
            reject(new Error('Plugin UI request timed out'));
          }, 250000);
          pending.set(id, { resolve, reject, timer });
          send({ type: 'call', id, name, arguments: args });
        });
      },
    }),
  });
  addEventListener('message', (event) => {
    const message = event.data;
    if (
      event.source !== parent ||
      !message ||
      message.protocol !== protocol ||
      message.session !== session
    )
      return;
    if (message.type === 'context') {
      context = message.value;
      const value = context as {
        locale: string;
        mode: string;
        reducedMotion: boolean;
        tokens: Record<string, string>;
      };
      document.documentElement.lang = value.locale;
      document.documentElement.dataset.theme = value.mode;
      document.documentElement.dataset.reducedMotion = String(value.reducedMotion);
      document.documentElement.style.colorScheme = value.mode;
      Object.entries(value.tokens).forEach(([key, token]) =>
        document.documentElement.style.setProperty(key, token),
      );
      emit('context', context);
    } else if (message.type === 'event') emit('event', message.value);
    else if (message.type === 'reply') {
      const waiting = pending.get(message.id);
      if (!waiting) return;
      clearTimeout(waiting.timer);
      pending.delete(message.id);
      if (message.reply.ok) waiting.resolve(message.reply.result);
      else
        waiting.reject(
          Object.assign(new Error(message.reply.error || 'Plugin command failed'), {
            code: message.reply.code,
            details: message.reply.details,
          }),
        );
    }
  });
  send({ type: 'ready' });
}

export function webDocument(html: string, session: string) {
  const policy =
    "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data: blob:; font-src data:; connect-src 'none'; frame-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'";
  const bootstrap = `(${bootstrapView.toString()})(${JSON.stringify(VIEW_PROTOCOL)},${JSON.stringify(session)})`;
  return `<!doctype html><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="${policy}"><script>${bootstrap}<\/script>${html}`;
}
