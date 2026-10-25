import { t } from '../../core/i18n.ts';
import { ArrowRight, FolderKey, Maximize2, Minimize2, Plus, Trash2, Unplug } from 'lucide-react';
import type { Manifest } from '../../core/types';
import { isExternalProfile, profileSourceLabel } from '../profiles';
import type { WorkspaceConfiguration } from './useWorkspaceConfiguration';
import type { WorkspaceSession } from './useWorkspaceSession';

export default function WorkspaceHeader({
  manifest,
  native,
  runtime,
  configuration,
  session,
  busy,
  focused,
  onToggleFocus,
  toast,
}: {
  manifest: Manifest;
  native: boolean;
  runtime?: Manifest['runtime'];
  configuration: WorkspaceConfiguration;
  session: WorkspaceSession;
  busy: boolean;
  focused: boolean;
  onToggleFocus: () => void;
  toast: (message: string) => void;
}) {
  const { store, selected, currentProfile, configure, setManagerOpen, trigger } = configuration;
  const { connected, sessionLabel, run } = session;
  const hasConnection = Boolean(manifest.ui.connection);
  return (
    <div className="terminal-toolbar">
      <div className="connection-picker">
        {hasConnection ? (
          <>
            <span className={`status-dot ${connected ? 'green' : ''}`} />
            {connected ? (
              <b>{sessionLabel}</b>
            ) : (
              <select
                aria-label={t('选择连接')}
                value={selected}
                onChange={(event) => {
                  const profile = store.profiles.find((item) => item.id === event.target.value);
                  if (profile) configure(profile);
                }}
              >
                <option value="">{t('选择连接')}</option>
                {store.profiles.map((profile) => (
                  <option key={profile.id} value={profile.id}>
                    {profile.name}
                    {isExternalProfile(profile) ? ` · ${profileSourceLabel(profile)}` : ''}
                  </option>
                ))}
              </select>
            )}
            <span className="surface-status">
              {connected
                ? t('已连接')
                : runtime?.running === false && native
                  ? t('进程已休眠')
                  : t('未连接')}
            </span>
          </>
        ) : (
          <b>{manifest.name}</b>
        )}
      </div>
      <div className="terminal-tools">
        {currentProfile && !connected && (
          <button className="quiet-button" onClick={() => configure(currentProfile)}>
            <ArrowRight size={14} />
            {t('连接配置')}
          </button>
        )}
        {hasConnection && (
          <button
            className="icon-button"
            title={t('管理连接')}
            aria-label={t('管理连接')}
            onClick={() => {
              setManagerOpen(true);
              void store.refresh().catch((failure) => toast(String(failure.message)));
            }}
          >
            <FolderKey size={16} />
          </button>
        )}
        {connected && manifest.ui.connection ? (
          <button
            className="quiet-button danger"
            disabled={busy}
            onClick={() => void run(manifest.ui.connection!.disconnect)}
          >
            <Unplug size={14} />
            {t('断开')}
          </button>
        ) : (
          <button className="quiet-button" ref={trigger} onClick={() => configure()}>
            <Plus size={14} />
            {hasConnection ? t('新建连接') : t('配置工具')}
          </button>
        )}
        <span className="toolbar-separator" />
        <button
          className="icon-button"
          aria-label={manifest.ui.surface === 'terminal' ? t('清空终端显示') : t('清空结果')}
          title={t('清空显示')}
          onClick={session.clear}
        >
          <Trash2 size={14} />
        </button>
        <button
          className="icon-button"
          aria-label={focused ? t('退出专注模式') : t('进入专注模式')}
          title={t('专注模式 · Ctrl Shift F')}
          onClick={onToggleFocus}
        >
          {focused ? <Minimize2 size={15} /> : <Maximize2 size={15} />}
        </button>
      </div>
    </div>
  );
}
