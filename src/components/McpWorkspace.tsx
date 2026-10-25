import { t, hostMessage } from '../core/i18n.ts';
import { useEffect, useRef, useState } from 'react';
import {
  Check,
  ChevronRight,
  Copy,
  CircleHelp,
  LoaderCircle,
  Plus,
  RefreshCw,
  Unplug,
  X,
} from 'lucide-react';
import { hostCall } from '../core/bridge';
import { useLocal } from '../core/storage';
import { useAssistantState } from '../core/useAssistantState';
import Dialog, { DialogPresence } from './Dialog';
import ProviderLogo from './ProviderLogo';
import { getHarnessGuides, getTestPrompt } from '../content/harnessGuide';

interface Client {
  id: string;
  name: string;
  vendor: string;
  configured: boolean;
  connected: boolean;
  paused?: boolean;
  needsReload?: boolean;
  needsUpdate?: boolean;
  adapterVersions?: string[];
  managed?: boolean;
  needsRepair?: boolean;
  backupCleanupPending?: boolean;
  canInstall: boolean;
  config: string;
  path: string;
  location: string;
  docs: string;
  steps: string;
  issue: string;
  installCommand?: string;
}
interface Installed {
  client: Client;
  backupId?: string;
  changed: boolean;
  path: string;
}
const preview: Client[] = [
  ['codex', 'Codex', 'OpenAI'],
  ['claude-code', 'Claude Code', 'Anthropic'],
  ['cursor', 'Cursor', 'Cursor'],
  ['deepseek-harness', 'DeepSeek Harness', 'DeepSeek'],
  ['zcode', 'ZCode', 'Z.ai'],
  ['workbuddy', 'WorkBuddy', 'Tencent'],
  ['trae', 'TRAE', 'ByteDance'],
].map(([id, name, vendor]) => ({
  id,
  name,
  vendor,
  configured: false,
  connected: false,
  canInstall: false,
  config: '',
  path: '',
  location: '',
  docs: '',
  steps: '',
  issue: '',
}));

export default function McpWorkspace({
  native,
  active = true,
  toast,
  onTools,
}: {
  native: boolean;
  active?: boolean;
  toast: (text: string) => void;
  onTools: () => void;
}) {
  const testPrompt = getTestPrompt();
  const harnessGuides = getHarnessGuides();
  const { state, error: stateError } = useAssistantState(native, active);
  const [clients, setClients] = useState<Client[]>(preview);
  const [detail, setDetail] = useState<Client | null>(null);
  const [installed, setInstalled] = useLocal<Installed | null>('mcp-last-connection-v1', null);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [check, setCheck] = useState('');
  const [copied, setCopied] = useState('');
  const [disconnecting, setDisconnecting] = useState<Client | null>(null);
  const [loadError, setLoadError] = useState('');
  const [loaded, setLoaded] = useState(false);
  const mutation = useRef(false);
  const revision = useRef(0);
  async function refresh() {
    const request = ++revision.current;
    const next = await hostCall<Client[]>('mcp_clients');
    if (request !== revision.current) return;
    setClients(next);
    setLoaded(true);
    setLoadError('');
  }
  useEffect(() => {
    if (!native || !active) return;
    let alive = true,
      pending = false;
    async function update() {
      if (pending || mutation.current) return;
      pending = true;
      const request = ++revision.current;
      try {
        const nextClients = await hostCall<Client[]>('mcp_clients');
        if (alive && request === revision.current) {
          setClients(nextClients);
          setLoaded(true);
          setLoadError('');
        }
      } catch (failure) {
        if (alive && request === revision.current) setLoadError((failure as Error).message);
      } finally {
        pending = false;
      }
    }
    void update();
    const timer = setInterval(() => void update(), 2500);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, [native, active]);
  const plugins = [...new Map(state.tools.map((tool) => [tool.pluginId, tool])).values()];
  const shared = plugins.filter((tool) => state.selected.includes(tool.pluginId));
  async function copy(text: string) {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(text);
      toast(t('已复制'));
    } catch {
      setError(t('复制失败，请在详情中手动选择文本。'));
    }
  }
  async function connect(client: Client) {
    if (!native || mutation.current) return;
    setError('');
    if (client.paused && (client.configured || !client.canInstall) && !client.needsRepair) {
      await connection(client, true);
      return;
    }
    if (!client.canInstall) {
      setDetail(client);
      setCopied('');
      return;
    }
    setBusy(client.id);
    mutation.current = true;
    revision.current++;
    try {
      const result = await hostCall<Omit<Installed, 'client'>>('mcp_install', client.id);
      setInstalled({ ...result, client });
      setCopied('');
      if (client.paused) await hostCall('mcp_connection', client.id, true);
      await refresh();
      toast(t('{p0} 配置已保存，等待客户端加载', { p0: client.name }));
    } catch (failure) {
      setError((failure as Error).message);
    } finally {
      setBusy('');
      mutation.current = false;
    }
  }
  async function undo() {
    if (!installed?.backupId || mutation.current) return;
    mutation.current = true;
    revision.current++;
    setBusy('undo');
    setError('');
    try {
      await hostCall('mcp_restore', installed.backupId);
      setInstalled(null);
      await refresh();
      toast(t('已恢复连接前的配置'));
    } catch (failure) {
      setError((failure as Error).message);
    } finally {
      setBusy('');
      mutation.current = false;
    }
  }
  async function verify() {
    if (mutation.current) return;
    mutation.current = true;
    setBusy('check');
    setError('');
    try {
      const value = await hostCall<{ toolCount: number }>('assistant_check');
      setCheck(t('自检通过 · {p0} 个授权工具', { p0: value.toolCount }));
    } catch (failure) {
      setError((failure as Error).message);
    } finally {
      setBusy('');
      mutation.current = false;
    }
  }
  async function manage(client: Client) {
    if (mutation.current) return;
    mutation.current = true;
    revision.current++;
    setBusy(client.id);
    setError('');
    try {
      await hostCall('mcp_manage', client.id, !client.managed);
      await refresh();
    } catch (failure) {
      setError((failure as Error).message);
    } finally {
      setBusy('');
      mutation.current = false;
    }
  }
  async function connection(client: Client, enabled: boolean) {
    if (mutation.current) return;
    mutation.current = true;
    revision.current++;
    setBusy(client.id);
    setError('');
    try {
      await hostCall('mcp_connection', client.id, enabled);
      await refresh();
      setDisconnecting(null);
      toast(
        enabled
          ? t('{p0} 已允许连接，等待客户端响应', { p0: client.name })
          : t('{p0} 已断开，配置已保留', { p0: client.name }),
      );
    } catch (failure) {
      setError((failure as Error).message);
    } finally {
      mutation.current = false;
      setBusy('');
    }
  }
  return (
    <div className="page-body mcp-page">
      <div className="page-heading">
        <div>
          <h1>{t('MCP 连接')}</h1>
        </div>
        <button
          className="service-status"
          disabled={!native || !!busy || !state.enabled}
          onClick={() => void verify()}
        >
          {busy === 'check' ? (
            <LoaderCircle size={14} className="spin" />
          ) : (
            <span
              className={`status-dot ${native && state.enabled && !stateError ? 'green' : ''}`}
            />
          )}
          {hostMessage(check) ||
            (native && state.enabled && !stateError ? t('本机服务自检') : t('连接服务未就绪'))}
        </button>
      </div>
      {!shared.length && (
        <div className="connection-feedback">
          <span>{t('还没有向 AI 授权工具。')}</span>
          <button className="text-button" onClick={onTools}>
            {t('前往智能体工具')}
          </button>
        </div>
      )}
      <div className="mcp-summary" aria-label={t('连接状态')}>
        <div>
          <span>{t('客户端配置')}</span>
          <b>
            {clients.filter((client) => client.configured).length}
            {t('个已保存')}
          </b>
        </div>
        <div>
          <span>{t('适配器')}</span>
          <b>
            {clients.filter((client) => client.connected).length}
            {t('个在线')}
          </b>
        </div>
        <div>
          <span>{t('工具调用')}</span>
          <b>
            {state.audit.some((item) => item.owner === 'mcp' && item.ok)
              ? t('已验证')
              : t('未验证')}
          </b>
        </div>
        <button className="text-button" onClick={onTools}>
          {t('管理授权')}
          <ChevronRight size={14} />
        </button>
      </div>
      {(error || loadError || stateError) && (
        <div className="error-note" role="alert">
          {hostMessage(error || loadError || stateError)}
          {loadError && (
            <button
              className="text-button"
              disabled={!!busy}
              onClick={() =>
                void refresh().catch((failure: Error) => setLoadError(failure.message))
              }
            >
              {t('重新读取状态')}
            </button>
          )}
          <button
            className="icon-button"
            aria-label={t('关闭错误提示')}
            onClick={() => setError('')}
          >
            <X size={15} />
          </button>
        </div>
      )}
      {!loaded && native && !loadError && (
        <p className="mcp-feedback" role="status">
          {t('正在读取客户端状态…')}
        </p>
      )}
      {installed && (
        <div className="connection-feedback">
          <Check size={17} />
          <span>
            {installed.client.name}
            {t('配置已保存')}
          </span>
          <button className="text-button" onClick={() => void copy(testPrompt)}>
            {t('复制试用消息')}
          </button>
          <button className="text-button" onClick={() => setDetail(installed.client)}>
            {t('打开使用指南')}
          </button>
          {installed.backupId && (
            <button className="text-button" disabled={!!busy} onClick={() => void undo()}>
              {t('撤销')}
            </button>
          )}
          <button
            className="icon-button"
            aria-label={t('关闭连接提示')}
            onClick={() => setInstalled(null)}
          >
            <X size={14} />
          </button>
        </div>
      )}
      <div className="provider-grid">
        {clients.map((client) => (
          <article
            className={`provider-card ${client.connected ? 'is-connected' : ''} ${client.paused ? 'is-paused' : ''}`}
            key={client.id}
          >
            <div className="provider-card-top">
              <ProviderLogo id={client.id} name={client.name} />
              <button
                className="icon-button"
                aria-label={t('{p0} 连接详情', { p0: client.name })}
                title={t('连接详情与帮助')}
                onClick={() => {
                  setDetail(client);
                  setCopied('');
                }}
              >
                <CircleHelp size={18} />
              </button>
            </div>
            <div className="provider-identity">
              <h2>{client.name}</h2>
            </div>
            <div className="provider-card-footer">
              <span className={`provider-state ${client.connected ? 'live' : ''}`}>
                {!loaded && native ? (
                  t('状态待确认')
                ) : client.paused ? (
                  t('已断开')
                ) : client.connected ? (
                  <>
                    <span className="status-dot green" />
                    {t('适配器在线')}
                  </>
                ) : client.needsRepair ? (
                  t('需要修复')
                ) : client.configured ? (
                  <>
                    <Check size={13} />
                    {t('等待客户端')}
                  </>
                ) : (
                  t('未接入')
                )}
              </span>
              <button
                className={`button ${client.configured && !client.needsRepair ? '' : 'primary'}`}
                disabled={!native || !loaded || !!busy || !state.enabled}
                onClick={() =>
                  client.needsReload
                    ? setDetail(client)
                    : client.connected && !client.paused
                      ? setDisconnecting(client)
                      : client.configured && !client.paused && !client.needsRepair
                        ? setDetail(client)
                        : void connect(client)
                }
              >
                {busy === client.id ? (
                  <LoaderCircle size={15} className="spin" />
                ) : client.connected ? (
                  <Unplug size={14} />
                ) : client.configured ? (
                  <RefreshCw size={14} />
                ) : (
                  <Plus size={15} />
                )}{' '}
                {busy === client.id
                  ? t('处理中…')
                  : client.paused
                    ? t('重新连接')
                    : client.needsReload
                      ? t('更新会话')
                      : client.connected
                        ? t('断开')
                        : client.needsRepair
                          ? t('修复连接')
                          : client.configured
                            ? t('继续连接')
                            : client.canInstall
                              ? t('一键接入')
                              : t('手动接入')}
              </button>
            </div>
            <div className="provider-description">
              <p className="provider-caption">
                {client.needsReload
                  ? t('旧版适配器仍在运行，请在客户端重新加载 Cove MCP。')
                  : client.needsUpdate
                    ? t('旧版本会话仍在运行，可在客户端重新加载 Cove MCP 更新。')
                    : client.paused
                      ? t('配置已保留，可随时重新连接。')
                      : client.connected
                        ? t('客户端已连接，可使用已授权工具。')
                        : client.configured
                          ? t('配置已保存，在客户端中启用 Cove。')
                          : t('接入后，在客户端中使用 Cove 工具。')}
              </p>
              {client.issue && <p className="mcp-client-issue">{hostMessage(client.issue)}</p>}
            </div>
            {!!client.adapterVersions?.length && (
              <small
                className="provider-version"
                title={t('会话版本：{p0}', { p0: client.adapterVersions.join(' / ') })}
              >
                {t('会话版本：{p0}', { p0: client.adapterVersions.join(' / ') })}
              </small>
            )}
          </article>
        ))}
      </div>
      {!!state.audit.length && (
        <details className="activity-disclosure">
          <summary>
            {t('最近的工具调用')}
            <ChevronRight size={15} />
          </summary>
          <div className="mcp-activity">
            {state.audit
              .slice(-8)
              .reverse()
              .map((item) => (
                <div key={item.id}>
                  <span className={`status-dot ${item.ok ? 'green' : ''}`} />
                  <b>{item.pluginName}</b>
                  <span>{item.readOnly ? t('读取') : t('操作')}</span>
                  <span>{item.ok ? t('成功') : t('失败')}</span>
                </div>
              ))}
          </div>
        </details>
      )}
      <DialogPresence>
        {disconnecting && (
          <Dialog
            labelId="disconnect-client"
            busy={!!busy}
            onClose={() => setDisconnecting(null)}
            initialFocus=".cancel-disconnect"
          >
            <h2 id="disconnect-client">{t('断开 {p0}？', { p0: disconnecting.name })}</h2>
            <p>
              {t(
                '断开后，此客户端的新工具请求将被暂停。已有配置和 智能体工具授权会保留，正在执行的任务会继续完成。',
              )}
            </p>
            {error && (
              <div className="error-note" role="alert">
                {hostMessage(error)}
              </div>
            )}
            <div className="modal-actions">
              <button
                className="button cancel-disconnect"
                disabled={!!busy}
                onClick={() => setDisconnecting(null)}
              >
                {t('取消')}
              </button>
              <button
                className="button"
                disabled={!!busy}
                onClick={() => void connection(disconnecting, false)}
              >
                {busy ? <LoaderCircle size={14} className="spin" /> : <Unplug size={14} />}
                {t('断开连接')}
              </button>
            </div>
          </Dialog>
        )}
      </DialogPresence>
      <DialogPresence>
        {detail &&
          (() => {
            const client = clients.find((item) => item.id === detail.id) || detail;
            const guide = harnessGuides[client.id];
            return (
              <Dialog
                labelId="client-details"
                className="client-details"
                busy={!!busy}
                onClose={() => setDetail(null)}
              >
                <div className="dialog-heading">
                  <div className="client-details-name">
                    <ProviderLogo id={client.id} name={client.name} />
                    <div>
                      <h2 id="client-details">{t('在 {p0} 中使用', { p0: client.name })}</h2>
                      <p>
                        {client.connected
                          ? t('客户端适配器已连接到 Cove')
                          : client.managed
                            ? t('配置已保存，Cove 启动时自动维护')
                            : client.canInstall
                              ? t('在 Cove 内完成配置与自检')
                              : t('此客户端需要手动导入')}
                      </p>
                    </div>
                  </div>
                  <button
                    className="icon-button"
                    aria-label={t('关闭使用指南')}
                    disabled={!!busy}
                    onClick={() => setDetail(null)}
                  >
                    <X size={18} />
                  </button>
                </div>
                {client.needsReload && (
                  <div className="inline-note" role="status">
                    {t(
                      '此客户端仍使用升级前的适配器。请在客户端重新加载 Cove MCP；重载后即可在这里断开和重新连接。',
                    )}
                  </div>
                )}
                <ol className="connection-steps">
                  <li className={client.configured ? 'complete' : ''}>
                    <span className="step-number">
                      {client.configured ? <Check size={15} /> : '1'}
                    </span>
                    <div>
                      <h3>{client.configured ? t('连接配置已保存') : t('添加 Cove 连接')}</h3>
                      <p>
                        {client.canInstall
                          ? t('由 Cove 保存配置，保留你已有的其他 MCP 服务。')
                          : t('复制专用配置，再按下一步在客户端中添加。')}
                      </p>
                      {client.canInstall && (
                        <p>
                          {t(
                            '撤销备份包含原配置中的全部内容，可能包含其他服务的密钥。备份受本机账户权限保护，每个客户端保留最近 5 份、最长 30 天；成功撤销后删除对应备份。',
                          )}
                        </p>
                      )}
                      {client.backupCleanupPending && (
                        <p role="status">
                          {t(
                            '部分旧备份暂时无法清理，已保留并将在下次启动或配置更新时重试；不影响已保存的连接配置。',
                          )}
                        </p>
                      )}
                      <button
                        className="button"
                        disabled={!native || !!busy || (!client.canInstall && !client.config)}
                        onClick={() =>
                          client.canInstall ? void connect(client) : void copy(client.config)
                        }
                      >
                        {busy === client.id ? (
                          <LoaderCircle size={14} className="spin" />
                        ) : client.configured ? (
                          <ChevronRight size={14} />
                        ) : (
                          <Copy size={14} />
                        )}{' '}
                        {client.canInstall
                          ? client.configured
                            ? t('更新连接配置')
                            : t('保存连接配置')
                          : t('复制 TRAE 配置')}
                      </button>
                    </div>
                  </li>
                  <li>
                    <span className="step-number">2</span>
                    <div>
                      <h3>{t('启动后直接使用')}</h3>
                      <p>{guide?.open || client.steps}</p>
                      <p>
                        {t(
                          '通过固定的发现、读取和操作入口，AI 获取最新授权。以后增减授权或重启 Cove，无需重新添加连接。',
                        )}
                      </p>
                      {client.configured && client.canInstall && (
                        <label className="mcp-manage-toggle">
                          <input
                            type="checkbox"
                            checked={!!client.managed}
                            disabled={!!busy || !native}
                            onChange={() => void manage(client)}
                          />
                          {t('Cove 启动时自动维护此连接')}
                        </label>
                      )}
                      <details className="connection-help">
                        <summary>{t('客户端未加载时排查')}</summary>
                        <p>{guide?.check}</p>
                        {guide?.command && (
                          <button
                            className="guide-command"
                            onClick={() => void copy(guide.command!)}
                          >
                            <code>{guide.command}</code>
                            <Copy size={14} />
                          </button>
                        )}
                      </details>
                    </div>
                  </li>
                  <li>
                    <span className="step-number">3</span>
                    <div>
                      <h3>{t('验证第一次工具调用')}</h3>
                      <p>
                        {t(
                          '在客户端的对话框中发送下面这句话。看到实际的工具结果后，回到 Cove 查看下方调用记录。',
                        )}
                      </p>
                      <button className="test-prompt" onClick={() => void copy(testPrompt)}>
                        <span>{testPrompt}</span>
                        {copied === testPrompt ? <Check size={17} /> : <Copy size={17} />}
                      </button>
                      <div
                        className={`client-live-state ${client.connected ? 'live' : ''}`}
                        role="status"
                      >
                        <span className={`status-dot ${client.connected ? 'green' : ''}`} />
                        {client.paused
                          ? t('已在 Cove 中断开')
                          : client.connected
                            ? t('已检测到客户端连接')
                            : t('等待客户端连接…')}
                        <span>{t('自动更新')}</span>
                      </div>
                      <p>
                        {state.audit.some((item) => item.owner === 'mcp' && item.ok)
                          ? t('已记录成功的 MCP 工具调用，可在最近调用中查看。')
                          : t('尚未记录成功的 MCP 工具调用。')}
                      </p>
                    </div>
                  </li>
                </ol>
                <details className="connection-help">
                  <summary>{t('没有连接成功？')}</summary>
                  <p>
                    {t(
                      '保持 Cove 打开，并在同一台 Windows 电脑上运行客户端。WSL、 远程会话和云端任务不能直接使用这份本地配置。',
                    )}
                  </p>
                  <p>
                    {t(
                      '若没有 cove：回到第一步更新配置并重启客户端；若工具为空：关闭本指南，在左侧「智能体工具」中选择需要授权的工具并保存；尚未添加工具时，空列表属于正常结果。若出现错误：展开下方配置，核对路径，并查看客户端的 MCP 日志。',
                    )}
                  </p>
                  <p>
                    {t(
                      '配置保存、适配器在线与工具调用成功是三个独立状态。这里检测的是适配器在线。你仍需在客户端完成模型登录或配置，才能发起 AI 对话。',
                    )}
                  </p>
                </details>
                <details className="connection-help">
                  <summary>{t('高级配置与安装命令')}</summary>
                  {client.issue && <div className="error-note">{hostMessage(client.issue)}</div>}
                  <code className="config-path">{client.path || client.location}</code>
                  <pre className="bridge-config" tabIndex={0}>
                    {client.config || t('请在桌面版中查看本机配置。')}
                  </pre>
                  <div className="modal-actions">
                    {client.installCommand && (
                      <button
                        className="button"
                        onClick={() => void copy(client.installCommand || '')}
                      >
                        {t('复制安装命令')}
                      </button>
                    )}
                    <button
                      className="button"
                      disabled={!client.config}
                      onClick={() => void copy(client.config)}
                    >
                      <Copy size={15} />
                      {t('复制配置')}
                    </button>
                  </div>
                </details>
                {error && (
                  <div className="error-note" role="alert">
                    {hostMessage(error)}
                  </div>
                )}
                <div className="modal-actions">
                  {client.paused ? (
                    <button
                      className="button"
                      disabled={!!busy}
                      onClick={() => void connect(client)}
                    >
                      {t('重新连接')}
                    </button>
                  ) : (
                    (client.configured || client.connected) && (
                      <button
                        className="button"
                        disabled={!!busy || client.needsReload}
                        onClick={() => {
                          setDetail(null);
                          setError('');
                          setDisconnecting(client);
                        }}
                      >
                        <Unplug size={14} />
                        {t('断开客户端')}
                      </button>
                    )
                  )}
                  <a
                    className="text-button"
                    href={client.docs || undefined}
                    target="_blank"
                    rel="noreferrer"
                  >
                    {t('官方说明 ↗')}
                  </a>
                  <button className="button primary" onClick={() => setDetail(null)}>
                    {t('回到连接页')}
                  </button>
                </div>
              </Dialog>
            );
          })()}
      </DialogPresence>
    </div>
  );
}
