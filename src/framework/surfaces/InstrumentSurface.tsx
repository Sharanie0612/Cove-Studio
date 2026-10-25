import { t } from '../../core/i18n.ts';
import { useState } from 'react';
import { Activity, Settings2 } from 'lucide-react';
import type { Manifest } from '../../core/types';
import { useInstrumentSession } from './instrument/useInstrumentSession';
import { useInstrumentSettings } from './instrument/useInstrumentSettings';
import AcquisitionToolbar from './instrument/AcquisitionToolbar';
import WaveformDisplay from './instrument/WaveformDisplay';
import SettingsPanel from './instrument/SettingsPanel';
import './instrument.css';

export default function InstrumentSurface({
  manifest,
  connected,
  active,
  clearToken,
  onError,
  onConfigure,
}: {
  manifest: Manifest;
  connected: boolean;
  active: boolean;
  clearToken: number;
  onError: (message: string) => void;
  onConfigure: () => void;
}) {
  const [channel, setChannel] = useState(1);
  const session = useInstrumentSession({
    manifest,
    connected,
    active,
    clearToken,
    channel,
    onError,
  });
  const { data, busy, notice, run, settingsStatus } = session;
  const settings = useInstrumentSettings(channel, data.status, settingsStatus);
  return (
    <div className="instrument-surface">
      <header className="scope-header">
        <div className="scope-model">
          <Activity size={22} />
          <div>
            <h2>{data.status?.identity.model || manifest.name}</h2>
            <span>
              {connected ? data.status?.address || t('仪器已连接') : t('局域网示波器')}
              {t('· 屏幕波形')}
            </span>
          </div>
        </div>
        <div className="scope-connection">
          <span className={`status-dot ${connected ? 'green' : ''}`} />
          {connected ? t('已连接') : t('未连接')}
          <button
            className="icon-button"
            aria-label={t('连接设置')}
            title={t('连接设置')}
            onClick={onConfigure}
          >
            <Settings2 size={16} />
          </button>
        </div>
      </header>
      {!connected && (
        <div className="inline-note scope-note">
          {t('在连接配置中填写仪器地址。保存后，点击连接建立仪器会话。')}
          <button className="button primary" onClick={onConfigure}>
            {t('连接示波器')}
          </button>
        </div>
      )}
      <AcquisitionToolbar session={session} connected={connected} onError={onError} />
      <div className="scope-console">
        <WaveformDisplay
          manifest={manifest}
          connected={connected}
          active={active}
          channel={channel}
          setChannel={setChannel}
          session={session}
          fallbackScale={Number(settings.vscale)}
        />
        <SettingsPanel
          status={data.status}
          channel={channel}
          disabled={!connected || Boolean(busy)}
          run={run}
          settings={settings}
        />
      </div>
      <footer className="scope-footnote">
        <span>{t('显示暂停保留仪器采集状态。滑条松开应用，实际值以回读为准。')}</span>
        {notice && (
          <span className="scope-notice" role="status">
            {notice}
          </span>
        )}
      </footer>
      <details className="instrument-card scope-ai-guide">
        <summary>{t('MCP / AI 接入与按需调用')}</summary>
        <ol>
          <li>
            {t(
              '在这里连接仪器并刷新状态。在 智能体工具页授权本工具，然后在 MCP 连接页按目标客户端说明保存配置。',
            )}
          </li>
          <li>
            {t(
              '在目标客户端重连 Cove MCP 适配器，发现工具后按参数说明调用只读工具。 保存配置、适配器在线、工具成功分别核验。',
            )}
          </li>
          <li>
            {t(
              '按问题读取状态、测量、波形或截图；参数和返回范围以插件工具说明为准。AI 不持续轮询。',
            )}
          </li>
          <li>
            {t('仪器设置和采集控制按插件声明的写工具调用，经 Cove 确认后执行。拒绝后不自动重试。')}
          </li>
          <li>
            {t(
              '停止刷新或断线后显示的是缓存。波形点数与采集范围由插件和设备决定；以实际连接和工具返回为准。',
            )}
          </li>
        </ol>
      </details>
    </div>
  );
}
