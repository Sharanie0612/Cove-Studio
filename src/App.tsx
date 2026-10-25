import { t, hostMessage } from './core/i18n.ts';
import { useLocale } from './core/useLocale';
import { localizeTool } from './core/pluginPresentation';
import { useCallback, useEffect, useRef, useState, useReducer } from 'react';
import { ArrowRight, CircleHelp, LoaderCircle, Copy, Minus, Search, Square, X } from 'lucide-react';
import { fallbackCatalog, hostCall, startEvents, subscribe } from './core/bridge';
import type { Catalog, Manifest, WorkProtection, RuntimeDiagnostic } from './core/types';
import { useLocal } from './core/storage';
import ToolWorkspace from './framework/ToolWorkspace';
import AiTools from './components/AiTools';
import WorkbenchHome from './components/WorkbenchHome';
import WorkbenchStatus from './components/WorkbenchStatus';
import PluginManager from './components/PluginManager';
import { ToolIcon } from './components/ToolIcon';
import NavigationIcon from './components/NavigationIcon';
import Dialog, { DialogPresence } from './components/Dialog';
import DeveloperGuide from './components/DeveloperGuide';
import StatusToast from './components/StatusToast';
import McpWorkspace from './components/McpWorkspace';
import ToolApprovals from './components/ToolApprovals';
import { initialWorkbench, workbenchReducer, type View } from './core/workbench';
import { changeView } from './core/motion';
import WorkspaceTabs from './components/WorkspaceTabs';
import { useAppearance } from './core/useAppearance';
import SettingsDialog from './components/SettingsDialog';
import { protectionDescription } from './framework/lifecycle';
import RuntimeDiagnostics from './components/RuntimeDiagnostics';
import coveIcon from '../assets/cove-mark.svg';
import { productName } from './core/identity';

type Pending = {
  title: string;
  description: string;
  action: () => Promise<void>;
};
export function CoveMark() {
  return <img src={coveIcon} alt="" />;
}

export default function App() {
  const [sourceCatalog, setCatalog] = useState<Catalog>(fallbackCatalog);
  const locale = useLocale();
  const catalog = {
    ...sourceCatalog,
    tools: sourceCatalog.tools.map(localizeTool),
    available: sourceCatalog.available?.map(localizeTool),
  };
  const [native, setNative] = useState(Boolean(window.pywebview?.api));
  const [workbench, dispatch] = useReducer(workbenchReducer, initialWorkbench);
  const { view, tabs: sourceTabs, activeId: toolId } = workbench;
  const tabs = sourceTabs.map(localizeTool);
  const navigationRevision = useRef(0);
  const setView = (next: View) => {
    navigationRevision.current += 1;
    changeView(() => dispatch({ type: 'view', view: next }));
  };
  const [focusedTool, setFocusedTool] = useState('');
  const { appearance, setAppearance, mode } = useAppearance();
  const [savedRecent, setRecent] = useLocal<string[]>('recent-tools', []);
  const recentIds = Array.isArray(savedRecent)
    ? savedRecent.filter((id) => typeof id === 'string')
    : [];
  function rememberTool(id: string) {
    setRecent([id, ...recentIds.filter((item) => item !== id)].slice(0, 12));
  }
  const [fontSize, setFontSize] = useLocal('terminal-font', 13);
  const [sidebarCollapsed, setSidebarCollapsed] = useLocal('sidebar-collapsed', false);
  const [settings, setSettings] = useState(false);
  const [notification, setNotification] = useState('');
  const [palette, setPalette] = useState(false);
  const [query, setQuery] = useState('');
  const [pending, setPending] = useState<Pending | null>(null);
  const [busy, setBusy] = useState(false);
  const [diagnostic, setDiagnostic] = useState<{
    tool: Manifest;
    report: RuntimeDiagnostic | null;
  } | null>(null);
  const openingRef = useRef(false);
  const [opening, setOpening] = useState('');
  const catalogRequest = useRef(0);
  const [catalogError, setCatalogError] = useState('');
  const [maximized, setMaximized] = useState(false);
  const toast = useCallback((message: string) => setNotification(hostMessage(message)), []);
  useEffect(() => {
    if (native && window.pywebview?.api.set_locale)
      void hostCall('set_locale', locale).catch(() => undefined);
  }, [locale, native]);
  const refresh = useCallback(async () => {
    if (!window.pywebview?.api) return;
    const request = ++catalogRequest.current;
    const next = await window.pywebview.api.catalog();
    if (request !== catalogRequest.current) return;
    setNative(true);
    setCatalog(next);
    setCatalogError('');
    dispatch({ type: 'reconcile', tools: next.tools });
    if (next.windowState) setMaximized(next.windowState.maximized);
  }, []);
  const onConnection = useCallback(() => {
    void refresh().catch(() => undefined);
  }, [refresh]);
  const onFocusChange = useCallback(
    (id: string, focused: boolean) =>
      setFocusedTool((current) => (focused ? id : current === id ? '' : current)),
    [],
  );
  useEffect(() => {
    const load = () => {
      void refresh().catch(() => setCatalogError(t('无法读取桌面运行时，请重试。')));
    };
    load();
    window.addEventListener('pywebviewready', load);
    const timer = setInterval(load, 2500),
      stop = startEvents();
    const off = subscribe((event) => {
      if (event.event === 'status') load();
    });
    return () => {
      clearInterval(timer);
      stop();
      off();
      window.removeEventListener('pywebviewready', load);
    };
  }, [refresh, toast]);
  useEffect(() => {
    const update = (event: Event) =>
      setMaximized((event as CustomEvent<{ maximized: boolean }>).detail.maximized);
    window.addEventListener('cove-window-state', update);
    return () => window.removeEventListener('cove-window-state', update);
  }, []);
  useEffect(() => {
    if (!notification) return;
    const timer = setTimeout(() => setNotification(''), 4800);
    return () => clearTimeout(timer);
  }, [notification]);
  useEffect(() => {
    const keydown = (event: KeyboardEvent) => {
      if (
        (event.ctrlKey || event.metaKey) &&
        event.key.toLowerCase() === 'k' &&
        !document.querySelector('dialog[open]')
      ) {
        event.preventDefault();
        setPalette(true);
        setQuery('');
      }
    };
    window.addEventListener('keydown', keydown);
    return () => window.removeEventListener('keydown', keydown);
  }, []);
  async function openTool(tool: Manifest) {
    const source = sourceCatalog.tools.find((item) => item.id === tool.id) || tool;
    if (tool.compatibilityStatus?.supported === false) {
      toast(tool.compatibilityStatus.reasons.join('；'));
      return false;
    }
    if (tool.enabled === false) {
      toast(t('请先在插件管理中启用这个工具'));
      return false;
    }
    if (tool.ui.surface === 'mcp') {
      navigationRevision.current += 1;
      changeView(() => dispatch({ type: 'open', tool: source }));
      setPalette(false);
      rememberTool(tool.id);
      return true;
    }
    if (openingRef.current) return false;
    const revision = ++navigationRevision.current;
    openingRef.current = true;
    setOpening(tool.id);
    try {
      if (native) await hostCall('plugin_action', tool.id, 'start');
      changeView(() =>
        dispatch({ type: 'open', tool: source, activate: revision === navigationRevision.current }),
      );
      setPalette(false);
      await refresh();
      rememberTool(tool.id);
      return true;
    } catch (error) {
      toast(String((error as Error).message));
      if (native) {
        const report = await hostCall<RuntimeDiagnostic | null>(
          'plugin_diagnostics',
          tool.id,
        ).catch(() => null);
        setDiagnostic({ tool, report });
      }
      return false;
    } finally {
      openingRef.current = false;
      setOpening('');
    }
  }
  function removeTab(id: string) {
    navigationRevision.current += 1;
    changeView(() => dispatch({ type: 'close', id }));
    setFocusedTool((current) => (current === id ? '' : current));
  }
  async function action(id: string, operation: string) {
    const tool = catalog.tools.find((item) => item.id === id);
    const execute = async (confirmed = false) => {
      const response = await hostCall<WorkProtection>('plugin_action', id, operation, confirmed);
      if (response?.needsConfirmation) {
        setPending({
          title: t('停止 {p0} 的活动工作？', { p0: tool?.name || t('工具') }),
          description: protectionDescription(response),
          action: () => execute(true),
        });
        return;
      }
      if (['disable', 'remove', 'stop'].includes(operation)) removeTab(id);
      if (operation === 'restart') dispatch({ type: 'restart', id });
      await refresh();
      toast(
        (
          {
            disable: t('插件已停用'),
            enable: t('插件已启用'),
            remove: t('插件已移除，数据已保留'),
            stop: t('插件进程已停止'),
            restore: t('插件已添加'),
            restart: t('插件已重启'),
          } as Record<string, string>
        )[operation] || t('插件已启动'),
      );
    };
    if (operation === 'remove') {
      setPending({
        title: t('移除 {p0}？', { p0: tool?.name || t('工具') }),
        description: t('此操作会结束连接和后台任务，并移除插件代码。配置和数据保留。'),
        action: () => execute(true),
      });
    } else await execute();
  }
  async function closeTab(tool: Manifest) {
    const execute = async (confirmed = false) => {
      if (native && tool.ui.surface !== 'mcp') {
        const response = await hostCall<WorkProtection>(
          'plugin_action',
          tool.id,
          'stop',
          confirmed,
        );
        if (response?.needsConfirmation) {
          setPending({
            title: t('关闭 {p0}？', { p0: tool.name }),
            description: protectionDescription(response),
            action: () => execute(true),
          });
          return;
        }
      }
      removeTab(tool.id);
      await refresh();
    };
    await execute();
  }
  async function windowAction(operation: string, confirmed = false) {
    try {
      const response = await hostCall<WorkProtection & { maximized?: boolean }>(
        'window_action',
        operation,
        confirmed,
      );
      if (typeof response?.maximized === 'boolean') setMaximized(response.maximized);
      if (response?.needsConfirmation)
        setPending({
          title: t('退出 {p0}？', { p0: productName }),
          description: protectionDescription(response),
          action: async () => {
            await hostCall('window_action', 'close', true);
          },
        });
    } catch (error) {
      toast(String((error as Error).message));
    }
  }
  useEffect(() => {
    const close = () => {
      void windowAction('close');
    };
    window.addEventListener('cove-close-request', close);
    return () => window.removeEventListener('cove-close-request', close);
  });
  async function releaseIdle() {
    try {
      const result = await hostCall<{ stopped: number }>('plugin_action', '', 'stop_idle');
      await refresh();
      toast(
        result.stopped
          ? t('已释放 {p0} 个空闲进程', { p0: result.stopped })
          : t('没有需要释放的空闲进程'),
      );
    } catch (failure) {
      toast((failure as Error).message);
    }
  }
  const enabled = catalog.tools.filter((tool) => tool.enabled !== false);
  const matchingTools = enabled.filter((tool) =>
    `${tool.name} ${tool.description}`.toLowerCase().includes(query.toLowerCase()),
  );
  return (
    <div
      className={`app-shell ${sidebarCollapsed ? 'sidebar-collapsed' : ''} ${focusedTool ? 'has-focus' : ''} ${maximized ? 'is-maximized' : ''}`}
    >
      {native &&
        ['n', 's', 'w', 'e', 'nw', 'ne', 'sw', 'se'].map((edge) => (
          <div
            key={edge}
            aria-hidden="true"
            className={`window-resize resize-${edge}`}
            onPointerDown={() => void hostCall('resize_window', edge).catch(() => undefined)}
          />
        ))}
      <header
        className="window-titlebar"
        onPointerDown={(event) => {
          if (
            native &&
            event.button === 0 &&
            document.documentElement.dataset.windowDrag !== 'native' &&
            !(event.target as Element).closest('button, input, select, a')
          ) {
            event.preventDefault();
            void windowAction('drag');
          }
        }}
        onDoubleClick={(event) => {
          if (
            native &&
            document.documentElement.dataset.windowDrag !== 'native' &&
            !(event.target as Element).closest('button, input, select, a')
          )
            void windowAction('maximize');
        }}
      >
        <div className="wordmark">
          <span className="cove-mark">
            <CoveMark />
          </span>
          <b>{productName}</b>
        </div>
        <button
          className="icon-button sidebar-toggle"
          aria-label={sidebarCollapsed ? t('展开侧栏') : t('收起侧栏')}
          aria-controls="management-sidebar"
          aria-expanded={!sidebarCollapsed}
          title={sidebarCollapsed ? t('展开侧栏') : t('收起侧栏')}
          disabled={Boolean(focusedTool)}
          onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
        >
          <NavigationIcon kind={sidebarCollapsed ? 'expand' : 'collapse'} />
        </button>
        <div className="window-drag"></div>
        <button
          className="titlebar-command"
          onClick={() => {
            setPalette(true);
            setQuery('');
          }}
        >
          <Search size={13} />
          <span>{t('搜索')}</span>
          <kbd>Ctrl K</kbd>
        </button>
        <div className="window-controls">
          <button
            aria-label={t('最小化')}
            title={t('最小化')}
            disabled={!native}
            onClick={() => void windowAction('minimize')}
          >
            <Minus size={15} />
          </button>
          <button
            aria-label={maximized ? t('还原窗口') : t('最大化窗口')}
            title={maximized ? t('还原') : t('最大化')}
            disabled={!native}
            onClick={() => void windowAction('maximize')}
          >
            {maximized ? <Copy size={12} /> : <Square size={12} />}
          </button>
          <button
            className="window-close"
            aria-label={t('关闭窗口')}
            title={t('关闭')}
            disabled={!native}
            onClick={() => void windowAction('close')}
          >
            <X size={16} />
          </button>
        </div>
      </header>
      <div className="shell-body">
        <aside id="management-sidebar" className="app-sidebar" inert={Boolean(focusedTool)}>
          <nav aria-label={t('主导航')}>
            <button
              title={t('工作台')}
              className={view === 'home' ? 'active' : ''}
              onClick={() => setView('home')}
            >
              <NavigationIcon kind="workbench" />
              <span>{t('工作台')}</span>
            </button>
            <button
              title={t('智能体工具')}
              className={view === 'ai-tools' ? 'active' : ''}
              onClick={() => setView('ai-tools')}
            >
              <NavigationIcon kind="agents" />
              <span>{t('智能体工具')}</span>
            </button>
            <div className="sidebar-divider" />
            <button
              title={t('插件')}
              className={view === 'plugins' ? 'active' : ''}
              onClick={() => setView('plugins')}
            >
              <NavigationIcon kind="plugins" />
              <span>{t('插件')}</span>
            </button>
            <button
              title={t('开发指南')}
              className={view === 'guide' ? 'active' : ''}
              onClick={() => setView('guide')}
            >
              <NavigationIcon kind="guide" />
              <span>{t('开发指南')}</span>
            </button>
          </nav>
          <div className="sidebar-bottom">
            <button title={t('设置')} onClick={() => setSettings(true)}>
              <NavigationIcon kind="settings" />
              <span>{t('设置')}</span>
            </button>
            <span className="sidebar-version">
              {productName} {catalog.hostVersion}
            </span>
          </div>
        </aside>
        <div className="shell-content">
          <WorkspaceTabs
            tabs={tabs}
            activeId={view === 'tool' ? toolId : ''}
            catalog={catalog}
            focused={Boolean(focusedTool)}
            onActivate={(id) => {
              navigationRevision.current += 1;
              changeView(() => dispatch({ type: 'activate', id }));
            }}
            onClose={(tool) => void closeTab(tool).catch((failure) => toast(failure.message))}
            onAdd={() => {
              setPalette(true);
              setQuery('');
            }}
          />

          <main
            className={
              view === 'tool'
                ? `workspace-main ${tabs.find((tool) => tool.id === toolId)?.ui.surface === 'mcp' ? 'mcp-main' : ''}`
                : 'content-main'
            }
          >
            {catalogError && (
              <div className="error-note runtime-error" role="alert">
                {hostMessage(catalogError)}
                <button
                  className="text-button"
                  onClick={() => void refresh().catch(() => undefined)}
                >
                  {t('重新连接')}
                </button>
              </div>
            )}
            {view === 'home' && (
              <WorkbenchHome
                catalog={catalog}
                native={native}
                opening={opening}
                recentIds={recentIds}
                onOpen={(tool) => void openTool(tool)}
                onPlugins={() => setView('plugins')}
                onStop={(tool) =>
                  void action(tool.id, 'stop').catch((failure) => toast(failure.message))
                }
                onRelease={() => void releaseIdle()}
              />
            )}
            <div hidden={view !== 'ai-tools'}>
              <AiTools
                catalog={catalog}
                native={native}
                active={view === 'ai-tools'}
                toast={toast}
                onPlugins={() => setView('plugins')}
                onMcp={() => {
                  const service = catalog.tools.find((tool) => tool.ui.surface === 'mcp');
                  if (service) void openTool(service);
                }}
              />
            </div>
            {view === 'plugins' && (
              <PluginManager
                catalog={catalog}
                native={native}
                onOpen={(tool) => void openTool(tool)}
                onAction={action}
                refresh={refresh}
                toast={toast}
                onRemoved={removeTab}
              />
            )}
            {view === 'guide' && <DeveloperGuide native={native} toast={toast} />}

            <div className="tool-workspaces" hidden={view !== 'tool'}>
              {tabs.map((tool) => (
                <div
                  className={`tool-slot ${tool.ui.surface === 'mcp' ? 'mcp-slot' : ''}`}
                  role="tabpanel"
                  id={`panel-${tool.id}`}
                  aria-labelledby={`tab-${tool.id}`}
                  key={`${tool.id}:${workbench.epochs[tool.id] || 0}`}
                  hidden={toolId !== tool.id}
                >
                  {tool.ui.surface === 'mcp' ? (
                    <McpWorkspace
                      native={native}
                      active={view === 'tool' && toolId === tool.id}
                      toast={toast}
                      onTools={() => setView('ai-tools')}
                    />
                  ) : (
                    <ToolWorkspace
                      manifest={tool}
                      active={view === 'tool' && toolId === tool.id}
                      native={native}
                      runtime={catalog.tools.find((item) => item.id === tool.id)?.runtime}
                      fontSize={fontSize}
                      onConnection={onConnection}
                      onFocusChange={onFocusChange}
                      toast={toast}
                    />
                  )}
                </div>
              ))}
            </div>
          </main>
        </div>
      </div>
      <WorkbenchStatus
        catalog={catalog}
        native={native}
        error={Boolean(catalogError)}
        onPlugins={() => setView('plugins')}
      />
      <ToolApprovals enabled={native} />
      <DialogPresence>
        {diagnostic && (
          <RuntimeDiagnostics
            tool={diagnostic.tool}
            report={diagnostic.report}
            onClose={() => setDiagnostic(null)}
          />
        )}
      </DialogPresence>
      <DialogPresence>
        {settings && (
          <SettingsDialog
            appearance={appearance}
            mode={mode}
            onAppearance={setAppearance}
            fontSize={fontSize}
            onFontSize={setFontSize}
            catalog={catalog}
            onClose={() => setSettings(false)}
          />
        )}
      </DialogPresence>
      <DialogPresence>
        {palette && (
          <Dialog
            labelId="palette-title"
            onClose={() => setPalette(false)}
            className="command-palette"
            initialFocus="input"
          >
            <h2 className="sr-only" id="palette-title">
              {t('查找工具')}
            </h2>
            <div className="palette-search">
              <Search size={19} />
              <input
                aria-label={t('查找工具')}
                placeholder={t('查找工具…')}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' && matchingTools[0]) void openTool(matchingTools[0]);
                }}
                value={query}
                onChange={(event) => setQuery(event.target.value)}
              />
              <kbd>Esc</kbd>
            </div>
            {matchingTools.map((tool) => (
              <button className="palette-item" key={tool.id} onClick={() => void openTool(tool)}>
                <ToolIcon tool={tool} />
                <span>
                  <b>{tool.name}</b>
                  <small>{tool.category}</small>
                </span>
                <ArrowRight size={16} />
              </button>
            ))}
            {!matchingTools.length && (
              <div className="list-empty compact">
                <Search size={24} />
                <p>{t('没有找到匹配的工具')}</p>
              </div>
            )}
          </Dialog>
        )}
      </DialogPresence>
      <DialogPresence>
        {pending && (
          <Dialog labelId="confirm-title" onClose={() => setPending(null)} busy={busy}>
            <div className="modal-icon">
              <CircleHelp size={24} />
            </div>
            <h2 id="confirm-title">{pending.title}</h2>
            <p>{pending.description}</p>
            <div className="modal-actions">
              <button className="button" disabled={busy} onClick={() => setPending(null)}>
                {t('取消')}
              </button>
              <button
                className="button primary"
                disabled={busy}
                onClick={async () => {
                  setBusy(true);
                  try {
                    await pending.action();
                    setPending(null);
                  } catch (error) {
                    toast(String((error as Error).message));
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                {busy && <LoaderCircle size={14} className="spin" />}
                {t('确认')}
              </button>
            </div>
          </Dialog>
        )}
      </DialogPresence>
      <StatusToast message={notification} onClose={() => setNotification('')} />
    </div>
  );
}
