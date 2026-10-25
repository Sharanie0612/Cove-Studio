import { t } from '../../core/i18n.ts';
import { useEffect, useRef, useState } from 'react';
import { Terminal } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import { ArrowRight, TerminalSquare } from 'lucide-react';
import { invoke, subscribe } from '../../core/bridge';
import type { Manifest } from '../../core/types';
import '@xterm/xterm/css/xterm.css';

function terminalColors() {
  const style = getComputedStyle(document.documentElement);
  const color = (name: string) => style.getPropertyValue('--terminal-' + name).trim();
  return {
    background: color('bg'),
    foreground: color('fg'),
    cursor: color('cursor'),
    cursorAccent: color('bg'),
    selectionBackground: color('selection'),
    black: color('black'),
    red: color('red'),
    green: color('green'),
    yellow: color('yellow'),
    blue: color('blue'),
    magenta: color('magenta'),
    cyan: color('cyan'),
    white: color('fg'),
    brightBlack: color('muted'),
    brightRed: color('red'),
    brightGreen: color('green'),
    brightYellow: color('yellow'),
    brightBlue: color('blue'),
    brightMagenta: color('magenta'),
    brightCyan: color('cyan'),
    brightWhite: color('fg'),
  };
}
export default function TerminalSurface({
  manifest,
  connected,
  active,
  onError,
  clearToken,
  fontSize,
  onConfigure,
}: {
  manifest: Manifest;
  connected: boolean;
  active: boolean;
  onError: (error: string) => void;
  clearToken: number;
  fontSize: number;
  onConfigure: () => void;
}) {
  const [hasOutput, setHasOutput] = useState(false);
  const element = useRef<HTMLDivElement>(null);
  const terminal = useRef<Terminal | null>(null);
  const fit = useRef<FitAddon | null>(null);
  const connectedRef = useRef(connected);
  const errorRef = useRef(onError);
  errorRef.current = onError;
  connectedRef.current = connected;
  const bindings = manifest.ui.terminal;
  useEffect(() => {
    if (!element.current || !manifest.ui.terminal) return;
    const surface = manifest.ui.terminal;
    const term = new Terminal({
      cursorBlink: true,
      cursorStyle: 'bar',
      fontSize,
      fontFamily: '"Cascadia Code", "SF Mono", Consolas, monospace',
      lineHeight: 1.35,
      scrollback: 5000,
      allowProposedApi: false,
      theme: terminalColors(),
    });
    const sizing = new FitAddon();
    term.loadAddon(sizing);
    term.open(element.current);
    terminal.current = term;
    fit.current = sizing;
    const appearanceChanged = () => {
      term.options.theme = terminalColors();
    };
    window.addEventListener('cove-appearance-change', appearanceChanged);
    let queue = Promise.resolve();
    const input = term.onData((data) => {
      if (!connectedRef.current) return;
      queue = queue
        .then(() => invoke(manifest.id, surface.write, { data }))
        .then(() => undefined)
        .catch((error) => errorRef.current(String(error.message || error)));
    });
    let resizeTimer = 0;
    const resized = term.onResize(({ cols, rows }) => {
      clearTimeout(resizeTimer);
      resizeTimer = window.setTimeout(() => {
        if (connectedRef.current)
          void invoke(manifest.id, surface.resize, { cols, rows }).catch(() => undefined);
      }, 150);
    });
    const observer = new ResizeObserver(() => {
      if (element.current?.clientWidth) sizing.fit();
    });
    observer.observe(element.current);
    const off = subscribe((event) => {
      if (event.pluginId === manifest.id && event.event === surface.dataEvent) {
        term.write(String(event.data.text || ''));
        setHasOutput(true);
      }
    });
    return () => {
      window.removeEventListener('cove-appearance-change', appearanceChanged);
      clearTimeout(resizeTimer);
      off();
      input.dispose();
      resized.dispose();
      observer.disconnect();
      term.dispose();
      terminal.current = null;
    };
    // Presentation messages change with language; only wire bindings own the terminal lifetime.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [manifest.id, bindings?.write, bindings?.resize, bindings?.dataEvent]);
  useEffect(() => {
    if (terminal.current) terminal.current.options.fontSize = fontSize;
    fit.current?.fit();
  }, [fontSize]);
  useEffect(() => {
    if (clearToken) {
      terminal.current?.clear();
      setHasOutput(false);
    }
  }, [clearToken]);
  useEffect(() => {
    if (!active) return;
    const timer = setTimeout(() => {
      fit.current?.fit();
      if (connected) {
        terminal.current?.focus();
        const term = terminal.current;
        if (term && manifest.ui.terminal)
          void invoke(manifest.id, manifest.ui.terminal.resize, {
            cols: term.cols,
            rows: term.rows,
          }).catch(() => undefined);
      }
    }, 60);
    return () => clearTimeout(timer);
  }, [active, connected, manifest.id, bindings?.resize]);
  return (
    <div className="terminal-stage">
      <div className="xterm-mount" ref={element} />
      {!connected && !hasOutput && (
        <div className="terminal-empty">
          <TerminalSquare size={34} strokeWidth={1.2} className="empty-terminal-icon" />
          <h3>{t('未连接')}</h3>

          <button className="terminal-connect" onClick={onConfigure}>
            {t('新建连接')}
            <ArrowRight size={14} />
          </button>
        </div>
      )}
    </div>
  );
}
