import { t } from '../../../core/i18n.ts';
import { useState } from 'react';
import { Pause, Play, RefreshCw, Square, Zap } from 'lucide-react';
import type { InstrumentSession } from './useInstrumentSession';

export default function AcquisitionToolbar({
  session,
  connected,
  onError,
}: {
  session: InstrumentSession;
  connected: boolean;
  onError: (message: string) => void;
}) {
  const { data, busy, run, live, setLive } = session;
  const [control, setControl] = useState('');
  const disabled = !connected || Boolean(busy);
  return (
    <>
      <div className="scope-toolbar" aria-label={t('采集控制')}>
        <span className={`scope-acquisition ${data.status?.trigger === 'STOP' ? 'stopped' : ''}`}>
          {data.status?.trigger || t('待连接')}
        </span>
        <button
          className="button primary"
          disabled={disabled}
          onClick={() => void run('acquisition', { action: 'run' })}
        >
          <Play size={14} />
          {t('运行')}
        </button>
        <button
          className="button"
          disabled={disabled}
          onClick={() => void run('acquisition', { action: 'stop' })}
        >
          <Square size={14} />
          {t('停止')}
        </button>
        <button
          className="button"
          disabled={disabled}
          onClick={() => void run('acquisition', { action: 'single' })}
        >
          {t('单次')}
        </button>
        <button
          className="button"
          disabled={disabled}
          onClick={() => void run('acquisition', { action: 'force' })}
        >
          <Zap size={14} />
          {t('强制触发')}
        </button>
        <button
          className="button"
          disabled={disabled}
          onClick={() => setControl(control ? '' : 'autoset')}
        >
          {t('自动设置…')}
        </button>
        <span className="spacer" />
        <button
          className="icon-button"
          title={t('刷新仪器状态')}
          aria-label={t('刷新仪器状态')}
          disabled={disabled}
          onClick={() => void run('status')}
        >
          <RefreshCw size={16} />
        </button>
        <button
          className={`button ${live ? 'scope-live-selected' : ''}`}
          disabled={!connected}
          onClick={() => {
            onError('');
            setLive((value) => !value);
          }}
        >
          {live ? <Pause size={14} /> : <Play size={14} />} {live ? t('暂停显示') : t('实时显示')}
        </button>
      </div>
      {control === 'autoset' && (
        <div className="inline-note scope-note">
          {t('自动设置会调整通道、时基和触发。')}
          <button className="button" onClick={() => setControl('')}>
            {t('取消')}
          </button>
          <button
            className="button primary"
            disabled={disabled}
            onClick={() => {
              setControl('');
              void run('acquisition', { action: 'autoset' });
            }}
          >
            {t('确认自动设置')}
          </button>
        </div>
      )}
    </>
  );
}
