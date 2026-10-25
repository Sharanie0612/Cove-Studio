import { getLocale } from '../../../core/i18n.ts';
import { t } from '../../../core/i18n.ts';
import { useState } from 'react';
import { Activity, Camera, Crosshair, Download, LoaderCircle } from 'lucide-react';
import type { Manifest } from '../../../core/types';
import { engineering, cursorReadout } from '../instrumentView';
import type { InstrumentSession } from './useInstrumentSession';
import { waveformGeometry } from './waveformGeometry';
import WaveformChart from './WaveformChart';
import Measurements from './Measurements';
import DisplayOptions from './DisplayOptions';

/** Local display preferences survive navigation independently of device acquisition. */
export default function WaveformDisplay({
  manifest,
  connected,
  active,
  channel,
  setChannel,
  session,
  fallbackScale,
}: {
  manifest: Manifest;
  connected: boolean;
  active: boolean;
  channel: number;
  setChannel: (channel: number) => void;
  session: InstrumentSession;
  fallbackScale: number;
}) {
  const { data, busy, live, visible, fps, interval, setIntervalMs, run } = session;
  const [fit, setFit] = useState(false);
  const [grid, setGrid] = useState(true);
  const [dots, setDots] = useState(false);
  const [cursors, setCursors] = useState(false);
  const [cursorA, setCursorA] = useState(25);
  const [cursorB, setCursorB] = useState(75);
  const wave = data.waveform?.channel === channel ? data.waveform : undefined;
  const selected = data.status?.channels.find((item) => item.channel === channel);
  const geometry = waveformGeometry(wave, selected, fallbackScale, fit);
  const cursor = wave ? cursorReadout(wave.time_s, wave.voltage_v, cursorA, cursorB) : null;
  const liveLabel = live ? (active && visible ? t('实时显示') : t('后台暂停')) : t('显示暂停');
  const disabled = !connected || Boolean(busy);
  function exportCsv() {
    if (!wave) return;
    const csv =
      'time_s,voltage_v\r\n' + wave.time_s.map((t, i) => `${t},${wave.voltage_v[i]}`).join('\r\n');
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = `CH${wave.channel}-waveform.csv`;
    link.click();
    URL.revokeObjectURL(url);
  }
  return (
    <main className="scope-display-column">
      <section className="scope-screen" aria-label={t('波形显示')}>
        <div className="scope-screen-status">
          <span>
            <i className={`status-dot ${live && active && visible ? 'green' : ''}`} />
            {liveLabel}
          </span>
          <span>H {engineering(data.status?.timebase_s_div, 's')}/div</span>
          <span>{engineering(data.status?.sample_rate_hz, 'Sa/s')}</span>
          <small>
            {busy ? (
              <>
                <LoaderCircle size={12} className="spin" />
                {t('处理中')}
              </>
            ) : live && fps > 0 ? (
              `${fps.toFixed(1)} fps`
            ) : (
              t('按响应刷新')
            )}
          </small>
        </div>
        <WaveformChart
          pluginId={manifest.id}
          channel={channel}
          wave={wave}
          selected={selected}
          edge={data.status?.edge_trigger}
          grid={grid}
          dots={dots}
          cursors={cursors}
          cursor={cursor}
          geometry={geometry}
        />
        <div className="scope-channel-strip" aria-label={t('显示通道')}>
          {[1, 2, 3, 4].map((n) => {
            const c = data.status?.channels.find((item) => item.channel === n);
            return (
              <button
                key={n}
                data-channel={n}
                className={channel === n ? 'selected' : ''}
                aria-pressed={channel === n}
                disabled={Boolean(busy)}
                onClick={() => setChannel(n)}
              >
                <b>CH{n}</b>
                <span>
                  {c ? (c.enabled ? `${engineering(c.scale_v_div, 'V')}/div` : t('已关闭')) : '—'}
                </span>
              </button>
            );
          })}
        </div>
        <div className="scope-screen-footer">
          <span>
            {wave ? t('{p0} 点 · 波形视图', { p0: wave.points }) : t('选择单个通道显示')}
            {!connected && wave ? t(' · 断开 / 缓存') : ''}
          </span>
          <time>
            {wave ? new Date(wave.timestamp).toLocaleTimeString(getLocale()) : t('尚未采集')}
          </time>
        </div>
      </section>
      <div className="scope-display-tools">
        <button
          className="button"
          disabled={disabled || selected?.enabled === false}
          onClick={() => void run('waveform', { channel })}
        >
          <Activity size={14} />
          {t('获取一帧')}
        </button>
        <button
          className="icon-button"
          aria-label={t('获取屏幕快照')}
          title={t('获取仪器屏幕快照')}
          disabled={disabled}
          onClick={() => void run('screenshot')}
        >
          <Camera size={16} />
        </button>
        <button
          className="icon-button"
          aria-label={t('导出波形 CSV')}
          title={t('导出波形 CSV')}
          disabled={!wave}
          onClick={exportCsv}
        >
          <Download size={16} />
        </button>
        <button
          className={`button ${cursors ? 'scope-live-selected' : ''}`}
          aria-pressed={cursors}
          onClick={() => setCursors(!cursors)}
        >
          <Crosshair size={14} />
          {t('游标')}
        </button>
        <span className="spacer" />
        <label>
          {t('刷新')}{' '}
          <select
            aria-label={t('实时刷新速度')}
            value={interval}
            onChange={(e) => setIntervalMs(Number(e.target.value))}
          >
            <option value={1000}>1 fps</option>
            <option value={500}>2 fps</option>
            <option value={200}>5 fps</option>
          </select>
        </label>
      </div>
      {cursors && (
        <section className="scope-cursor-panel">
          <div>
            <b>A</b>
            <input
              aria-label={t('游标 A 位置')}
              type="range"
              min="0"
              max="100"
              step=".1"
              value={cursorA}
              onChange={(e) => setCursorA(Number(e.target.value))}
            />
            <span>
              {engineering(cursor?.ta, 's')} / {engineering(cursor?.va, 'V')}
            </span>
          </div>
          <div>
            <b>B</b>
            <input
              aria-label={t('游标 B 位置')}
              type="range"
              min="0"
              max="100"
              step=".1"
              value={cursorB}
              onChange={(e) => setCursorB(Number(e.target.value))}
            />
            <span>
              {engineering(cursor?.tb, 's')} / {engineering(cursor?.vb, 'V')}
            </span>
          </div>
          <p>
            Δt <b>{engineering(cursor?.dt, 's')}</b> ΔV (B−A) <b>{engineering(cursor?.dv, 'V')}</b>{' '}
            1/Δt <b>{engineering(cursor?.reciprocal, 'Hz')}</b>
            <small>{t('屏幕采样点估读，1/Δt 仅为游标间隔倒数。')}</small>
          </p>
        </section>
      )}
      <Measurements
        measurements={data.measurements}
        channel={channel}
        disabled={disabled}
        run={run}
      />
      <DisplayOptions
        manifest={manifest}
        screenshot={data.screenshot}
        grid={grid}
        setGrid={setGrid}
        dots={dots}
        setDots={setDots}
        fit={fit}
        setFit={setFit}
      />
    </main>
  );
}
