import { t, hostMessage } from '../core/i18n.ts';
import { useState } from 'react';
import { localizeTool } from '../core/pluginPresentation';
import {
  ArrowRight,
  Check,
  ChevronDown,
  Download,
  FileArchive,
  FolderOpen,
  LoaderCircle,
  Package,
  Power,
  RefreshCw,
  Search,
  Settings2,
  ShieldCheck,
  Trash2,
  X,
} from 'lucide-react';
import { hostCall } from '../core/bridge';
import type {
  Catalog,
  Manifest,
  PackagePreview,
  ExportPreview,
  RuntimeDiagnostic,
} from '../core/types';
import Dialog, { DialogPresence } from './Dialog';
import RuntimeDiagnostics from './RuntimeDiagnostics';
import ExportDialog from './ExportDialog';
import { ToolIcon, memoryLabel } from './ToolIcon';

const permissions: Record<string, string> = {
  'network.tcp': 'TCP 网络连接',
  'network.udp': 'UDP 网络连接',
  'network.http': 'HTTP 网络连接',
  'host.tools': '访问已授权的工作台工具',
  'filesystem.read': '读取文件',
};
export default function PluginManager({
  catalog,
  native,
  onOpen,
  onAction,
  refresh,
  toast,
  onRemoved,
}: {
  catalog: Catalog;
  native: boolean;
  onOpen: (tool: Manifest) => void;
  onAction: (id: string, action: string) => Promise<void>;
  refresh: () => Promise<void>;
  toast: (message: string) => void;
  onRemoved: (id: string) => void;
}) {
  const [query, setQuery] = useState('');
  const [diagnostic, setDiagnostic] = useState<{
    tool: Manifest;
    report: RuntimeDiagnostic | null;
  } | null>(null);
  const [exportPreview, setExportPreview] = useState<ExportPreview | null>(null);
  const [filter, setFilter] = useState('all');
  const [busy, setBusy] = useState('');
  const [sourcePreview, setPreview] = useState<PackagePreview | null>(null);
  const preview = sourcePreview && {
    ...sourcePreview,
    manifest: localizeTool(sourcePreview.manifest),
  };
  const [trusted, setTrusted] = useState(false);
  const [error, setError] = useState('');
  async function perform(id: string, action: string) {
    setBusy(id);
    try {
      await onAction(id, action);
    } catch (failure) {
      toast(String((failure as Error).message));
    } finally {
      setBusy('');
    }
  }
  async function exportTool(id = '') {
    setBusy(id || 'pack');
    try {
      const result = await hostCall<ExportPreview | null>('prepare_plugin_export', id);
      if (result) setExportPreview(result);
    } catch (failure) {
      toast(String((failure as Error).message));
    } finally {
      setBusy('');
    }
  }
  async function inspect() {
    setBusy('import');
    setError('');
    try {
      const result = await hostCall<PackagePreview | null>('inspect_plugin_package');
      if (result) {
        setPreview(result);
        setTrusted(false);
      }
    } catch (failure) {
      toast(String((failure as Error).message));
    } finally {
      setBusy('');
    }
  }
  async function install() {
    if (!preview || !trusted) return;
    setBusy('install');
    setError('');
    try {
      const result = await hostCall<{ id: string }>('install_plugin', preview.ticket);
      onRemoved(result.id);
      await refresh();
      setPreview(null);
      toast(t('插件已导入，可在工作台中打开'));
    } catch (failure) {
      setError(String((failure as Error).message));
    } finally {
      setBusy('');
    }
  }
  async function runtime(tool: Manifest) {
    setBusy(tool.id);
    try {
      const result = await hostCall('configure_plugin_runtime', tool.id);
      if (result) {
        onRemoved(tool.id);
        await refresh();
        toast(t('已更新插件的 Python 运行环境'));
      }
    } catch (failure) {
      toast(String((failure as Error).message));
    } finally {
      setBusy('');
    }
  }
  const filtered = catalog.tools.filter(
    (tool) =>
      `${tool.name} ${tool.id}`.toLowerCase().includes(query.toLowerCase()) &&
      (filter === 'all' || (tool.enabled !== false) === (filter === 'enabled')),
  );
  return (
    <div className="page-body plugin-page">
      <div className="page-heading">
        <div>
          <h1>{t('插件')}</h1>
        </div>
        <div className="page-actions">
          <div className="plugin-toolbar">
            <button
              className="button"
              title={catalog.pluginsPath || t('插件目录')}
              disabled={!native || Boolean(busy)}
              onClick={() =>
                void hostCall('open_plugins_folder').catch((failure) => toast(failure.message))
              }
            >
              <FolderOpen size={16} />
              {t('插件目录')}
            </button>
            <button
              className="icon-button"
              aria-label={t('重新扫描')}
              title={t('重新扫描')}
              disabled={!native || Boolean(busy)}
              onClick={() => {
                setBusy('scan');
                void hostCall('rescan_plugins')
                  .then(refresh)
                  .then(() => toast(t('已刷新')))
                  .catch((failure) => toast(failure.message))
                  .finally(() => setBusy(''));
              }}
            >
              <RefreshCw size={16} />
            </button>
          </div>
          <button className="button" disabled={Boolean(busy)} onClick={() => void exportTool()}>
            <FileArchive size={15} />
            {t('打包项目')}
          </button>
          <button
            className="button primary"
            disabled={Boolean(busy)}
            onClick={() => void inspect()}
          >
            {busy === 'import' ? (
              <LoaderCircle size={15} className="spin" />
            ) : (
              <Download size={15} />
            )}
            {t('导入插件')}
          </button>
        </div>
      </div>
      <div className="plugin-filter">
        <div className="segmented" aria-label={t('插件筛选')}>
          {[
            ['all', t('全部')],
            ['enabled', t('已启用')],
            ['disabled', t('已停用')],
          ].map(([value, label]) => (
            <button
              className={filter === value ? 'selected' : ''}
              key={value}
              onClick={() => setFilter(value)}
            >
              {label}
            </button>
          ))}
        </div>
        <label className="search-field">
          <Search size={15} />
          <input
            aria-label={t('搜索插件')}
            placeholder={t('搜索插件')}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </label>
      </div>
      <div className="plugin-list">
        {filtered.map((tool) => (
          <article
            className={`panel plugin-entry ${tool.enabled === false ? 'disabled-plugin' : ''}`}
            key={tool.id}
          >
            <div className="plugin-overview">
              <ToolIcon tool={tool} />
              <div className="plugin-description">
                <h2>
                  {tool.name}
                  {(tool.ui.surface === 'mcp' || tool.builtin) && (
                    <span className="small-tag">
                      {tool.ui.surface === 'mcp' ? t('内置') : t('预置')}
                    </span>
                  )}
                </h2>
                <small>
                  v{tool.version} <span>·</span>{' '}
                  {tool.ui.surface === 'mcp'
                    ? tool.enabled === false
                      ? t('已停用')
                      : t('服务已启用')
                    : tool.runtime?.running
                      ? `${tool.runtime.connected ? t('连接中') : t('已启动')} · ${memoryLabel(tool.runtime.memoryBytes)}`
                      : tool.enabled === false
                        ? t('已停用')
                        : t('未启动')}
                </small>
              </div>
              {
                <button
                  role="switch"
                  aria-checked={tool.enabled !== false}
                  aria-label={`${tool.enabled === false ? t('启用') : t('停用')} ${tool.name}`}
                  className={`toggle ${tool.enabled !== false ? 'on' : ''}`}
                  disabled={Boolean(busy)}
                  onClick={() =>
                    void perform(tool.id, tool.enabled === false ? 'enable' : 'disable')
                  }
                >
                  <span />
                </button>
              }
              <button
                className="button"
                disabled={
                  tool.enabled === false ||
                  tool.compatibilityStatus?.supported === false ||
                  Boolean(busy)
                }
                onClick={() => onOpen(tool)}
              >
                {t('打开')}
                <ArrowRight size={14} />
              </button>
            </div>
            {tool.compatibilityStatus?.supported === false && (
              <div className="error-note" role="alert">
                {tool.compatibilityStatus.reasons.join('；')}
              </div>
            )}
            <details className="plugin-details">
              <summary>
                {t('详情')}
                <ChevronDown size={13} />
              </summary>
              <div className="plugin-detail-body">
                <p className="plugin-full-description">{tool.description}</p>
                <div className="plugin-facts">
                  <span>
                    {t('作者')}
                    <b>{tool.author}</b>
                  </span>
                  <span>
                    {t('插件标识')}
                    <code>{tool.id}</code>
                  </span>
                  <span>
                    {t('界面部件')}
                    <b>
                      {tool.ui.surface === 'terminal'
                        ? t('终端与连接管理')
                        : tool.ui.surface === 'mcp'
                          ? t('MCP 连接中心')
                          : t('表单与结果')}
                    </b>
                  </span>
                  <span>
                    {t('SDK 兼容')}
                    <b>
                      v{tool.sdkVersion} ·{' '}
                      {tool.compatibilityStatus?.supported === false ? t('不兼容') : t('兼容')}
                    </b>
                  </span>
                  <span>
                    {t('Python 环境')}
                    <b>{tool.customRuntime ? t('独立解释器') : t('工作台运行时')}</b>
                  </span>
                </div>
                <div className="permission-line">
                  <ShieldCheck size={14} />
                  <span>
                    {t('声明能力：')}
                    {tool.permissions.length
                      ? tool.permissions.map((value) => t(permissions[value] || value)).join('、')
                      : t('未声明额外能力')}
                  </span>
                </div>
                <div className="plugin-operations">
                  {tool.ui.surface !== 'mcp' && (
                    <button
                      className="button danger"
                      disabled={Boolean(busy)}
                      onClick={() => void perform(tool.id, 'remove')}
                    >
                      <Trash2 size={14} />
                      {t('移除插件')}
                    </button>
                  )}
                  <button
                    className="button"
                    disabled={!native || Boolean(busy)}
                    onClick={() =>
                      void hostCall<RuntimeDiagnostic | null>('plugin_diagnostics', tool.id)
                        .then((report) => setDiagnostic({ tool, report }))
                        .catch((failure) => toast(failure.message))
                    }
                  >
                    {t('运行诊断')}
                  </button>
                  {tool.ai?.tools.some((item) => item.readOnly) && (
                    <button
                      className="button"
                      disabled={Boolean(busy)}
                      onClick={() => {
                        setBusy(tool.id);
                        void hostCall<{ path: string } | null>('export_dsh_plugin', tool.id)
                          .then((result) => {
                            if (result) toast(t('DSH 插件已导出'));
                          })
                          .catch((failure) => toast(failure.message))
                          .finally(() => setBusy(''));
                      }}
                    >
                      <FileArchive size={13} />
                      {t('导出 DSH')}
                    </button>
                  )}
                  <button
                    className="button"
                    disabled={Boolean(busy)}
                    onClick={() => void exportTool(tool.id)}
                  >
                    <FileArchive size={13} />
                    {t('导出插件')}
                  </button>
                  {tool.runtime?.running && (
                    <>
                      <button
                        className="button"
                        disabled={Boolean(busy)}
                        onClick={() => void perform(tool.id, 'stop')}
                      >
                        <Power size={13} />
                        {t('停止进程')}
                      </button>
                      <button
                        className="button"
                        disabled={Boolean(busy)}
                        onClick={() => void perform(tool.id, 'restart')}
                      >
                        <RefreshCw size={13} />
                        {t('重启')}
                      </button>
                    </>
                  )}
                  {tool.ui.surface !== 'mcp' && (
                    <button
                      className="button"
                      disabled={Boolean(busy) || tool.runtime?.connected}
                      title={
                        tool.runtime?.connected
                          ? t('请先断开连接')
                          : t('选择此插件专用的 Python 解释器')
                      }
                      onClick={() => void runtime(tool)}
                    >
                      <Settings2 size={13} />
                      {t('运行环境')}
                    </button>
                  )}
                  {busy === tool.id && <LoaderCircle size={15} className="spin" />}
                </div>
              </div>
            </details>
          </article>
        ))}
      </div>
      {!filtered.length && (
        <div className="list-empty">
          <Package size={28} />
          <b>{t('没有匹配的插件')}</b>
          <p>{t('调整筛选条件，或导入一个新插件。')}</p>
        </div>
      )}
      {!!catalog.available?.length && (
        <section className="available-plugins">
          <div className="section-heading">
            <h2>{t('可添加的插件')}</h2>
          </div>
          {catalog.available
            .filter((tool) => `${tool.name} ${tool.id}`.toLowerCase().includes(query.toLowerCase()))
            .map((tool) => (
              <article className="panel available-plugin" key={tool.id}>
                <ToolIcon tool={tool} />
                <div>
                  <h3>{tool.name}</h3>
                </div>
                <button
                  className="button"
                  disabled={Boolean(busy)}
                  onClick={() => void perform(tool.id, 'restore')}
                >
                  <Package size={14} />
                  {t('添加')}
                </button>
              </article>
            ))}
        </section>
      )}
      {catalog.issues.map((issue) => (
        <div className="error-note" key={issue.folder}>
          {issue.folder}：{issue.error}
        </div>
      ))}
      {!native && (
        <p className="preview-note">
          {t('当前为界面预览。导入、停用和进程管理在 Cove 桌面版中可用。')}
        </p>
      )}
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
        {preview && (
          <Dialog
            labelId="import-title"
            onClose={() => setPreview(null)}
            busy={busy === 'install'}
            className="import-dialog"
          >
            <div className="dialog-heading">
              <div>
                <h2 id="import-title">{preview.previousVersion ? t('更新插件') : t('导入插件')}</h2>
                <p>{t('确认来源和运行要求后再安装。')}</p>
              </div>
              <button
                className="icon-button"
                aria-label={t('取消导入')}
                disabled={busy === 'install'}
                onClick={() => setPreview(null)}
              >
                <X size={18} />
              </button>
            </div>
            <div className="import-body">
              <div className="import-identity">
                <ToolIcon tool={preview.manifest} />
                <div>
                  <h3>{preview.manifest.name}</h3>
                  <p>
                    {preview.manifest.author} ·{' '}
                    {preview.previousVersion ? `${preview.previousVersion} → ` : ''}
                    {preview.manifest.version}
                  </p>
                </div>
              </div>
              <p>{preview.manifest.description}</p>
              <div className="import-facts">
                <span>
                  {t('标识')}
                  <code>{preview.manifest.id}</code>
                </span>
                <span>
                  {preview.fileCount}
                  {t('个文件 ·')}
                  {(preview.sizeBytes / 1024).toFixed(1)} KB
                </span>
                <span>
                  {t('能力')}{' '}
                  {preview.manifest.permissions
                    .map((value) => t(permissions[value] || value))
                    .join('、') || t('未声明')}
                </span>
              </div>
              {preview.requirements && (
                <div className="inline-note">
                  <b>{t('依赖要求')}</b>
                  <pre>{preview.requirements}</pre>
                  <p>
                    {t(
                      '导入不会自动执行 pip。插件需自带兼容的 vendor 依赖，或安装后指定已配好依赖的 Python 环境。',
                    )}
                  </p>
                </div>
              )}
              <details className="checksum">
                <summary>{t('文件校验值')}</summary>
                <code>SHA-256 {preview.sha256}</code>
              </details>
              <label className="trust-checkbox">
                <input
                  type="checkbox"
                  checked={trusted}
                  onChange={(event) => setTrusted(event.target.checked)}
                />
                <span>
                  {t('我信任这个插件的来源，允许它以当前用户权限运行。')}
                  {preview.previousVersion && t('更新会停止旧插件及其连接。')}
                </span>
              </label>
              {error && (
                <div className="error-note" role="alert">
                  {hostMessage(error)}
                </div>
              )}
            </div>
            <div className="modal-actions">
              <button
                className="button"
                disabled={busy === 'install'}
                onClick={() => setPreview(null)}
              >
                {t('取消')}
              </button>
              <button
                className="button primary"
                disabled={!trusted || busy === 'install'}
                onClick={() => void install()}
              >
                {busy === 'install' ? (
                  <LoaderCircle size={14} className="spin" />
                ) : (
                  <Check size={14} />
                )}
                {preview.previousVersion ? t('确认更新') : t('确认导入')}
              </button>
            </div>
          </Dialog>
        )}
      </DialogPresence>
      <DialogPresence>
        {exportPreview && (
          <ExportDialog
            preview={exportPreview}
            onClose={() => setExportPreview(null)}
            toast={toast}
          />
        )}
      </DialogPresence>
    </div>
  );
}
