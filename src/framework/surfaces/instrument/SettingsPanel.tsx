import { t } from '../../../core/i18n.ts';
import { CommitSlider, DivisionControl } from '../InstrumentControls';
import { divisions, engineering } from '../instrumentView';
import type { Status, RunInstrument } from './types';
import type { InstrumentSettings } from './useInstrumentSettings';

const timeDivisions = divisions(5e-10, 1000),
  voltageDivisions = divisions(0.0002, 10000);

export default function SettingsPanel({
  status,
  channel,
  disabled,
  run,
  settings,
}: {
  status: Status | undefined;
  channel: number;
  disabled: boolean;
  run: RunInstrument;
  settings: InstrumentSettings;
}) {
  const {
    scale,
    setScale,
    vscale,
    setVscale,
    offset,
    setOffset,
    coupling,
    setCoupling,
    level,
    setLevel,
    slope,
    setSlope,
    sweep,
    setSweep,
    triggerChannel,
    setTriggerChannel,
  } = settings;
  const selected = status?.channels.find((item) => item.channel === channel);
  const actualScale = selected?.scale_v_div || Number(vscale);
  const actualOffset = selected?.offset_v ?? 0;
  const edge = status?.edge_trigger;
  const triggerSource = status?.channels.find((c) => c.channel === triggerChannel);
  const triggerMin = Math.max(
    -10000,
    -(triggerSource?.scale_v_div || 1) * 4.5 - (triggerSource?.offset_v || 0),
  );
  const triggerMax = Math.min(
    10000,
    (triggerSource?.scale_v_div || 1) * 4.5 - (triggerSource?.offset_v || 0),
  );
  const triggerActual =
    edge?.mode === 'EDGE' && edge.source === `CHAN${triggerChannel}` ? edge.level_v : undefined;
  const triggerArgs = (level_v = Number(level)) => ({
    channel: triggerChannel,
    level_v,
    slope,
    sweep,
  });
  return (
    <aside className="scope-control-panel" aria-label={t('示波器设置')}>
      <section className="scope-control-section">
        <div className="scope-section-title">
          <h3>{t('水平')}</h3>
          <small>HORIZONTAL</small>
        </div>
        <DivisionControl
          label={t('时基')}
          value={status?.timebase_s_div || Number(scale)}
          values={timeDivisions}
          unit="s"
          disabled={disabled}
          onCommit={(scale_s) => void run('timebase', { scale_s })}
        />
        <details className="scope-precision">
          <summary>{t('精确时基')}</summary>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void run('timebase', { scale_s: Number(scale) });
            }}
          >
            <label>
              {t('秒 / 格')}
              <input
                required
                aria-label={t('时基（s/div）')}
                type="number"
                step="any"
                min="5e-10"
                max="1000"
                value={scale}
                onChange={(e) => setScale(e.target.value)}
              />
            </label>
            <button className="button" disabled={disabled}>
              {t('应用')}
            </button>
          </form>
        </details>
      </section>
      <section className="scope-control-section" data-channel={channel}>
        <div className="scope-section-title">
          <h3>
            {t('垂直')}
            <span className="scope-channel-tag">CH{channel}</span>
          </h3>
          <button
            className={`scope-toggle ${selected?.enabled ? 'on' : ''}`}
            role="switch"
            aria-checked={Boolean(selected?.enabled)}
            aria-label={t('CH{p0} 通道开关', { p0: channel })}
            disabled={disabled || !selected}
            onClick={() => void run('channel', { channel, enabled: !selected?.enabled })}
          >
            {selected?.enabled ? t('开启') : t('关闭')}
          </button>
        </div>
        <DivisionControl
          label={t('垂直档位')}
          value={actualScale}
          values={voltageDivisions}
          unit="V"
          disabled={disabled}
          onCommit={(scale_v) => void run('channel', { channel, scale_v })}
        />
        <div className="scope-control-label">
          <label>{t('垂直偏移')}</label>
          <button
            className="text-button"
            disabled={disabled}
            onClick={() => void run('channel', { channel, offset_v: 0 })}
          >
            {t('归零')}
          </button>
        </div>
        <CommitSlider
          label={t('垂直偏移滑条')}
          value={actualOffset}
          min={Math.max(-10000, Math.min(-4 * actualScale, actualOffset))}
          max={Math.min(10000, Math.max(4 * actualScale, actualOffset))}
          step={Math.max(actualScale / 50, 0.000001)}
          disabled={disabled}
          onCommit={(offset_v) => void run('channel', { channel, offset_v })}
          display={(v) => engineering(v, 'V')}
        />
        <div className="scope-control-label">
          <label>{t('耦合')}</label>
          <div className="scope-segments">
            {['DC', 'AC', 'GND'].map((value) => (
              <button
                key={value}
                className={selected?.coupling === value ? 'selected' : ''}
                disabled={disabled}
                onClick={() => void run('channel', { channel, coupling: value })}
              >
                {value}
              </button>
            ))}
          </div>
        </div>
        <details className="scope-precision">
          <summary>{t('精确通道设置')}</summary>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void run('channel', {
                channel,
                scale_v: Number(vscale),
                offset_v: Number(offset),
                coupling,
              });
            }}
          >
            <label>
              {t('伏 / 格')}
              <input
                required
                aria-label={t('垂直档位（V/div）')}
                type="number"
                step="any"
                min="0.0002"
                max="10000"
                value={vscale}
                onChange={(e) => setVscale(e.target.value)}
              />
            </label>
            <label>
              {t('偏移 / V')}
              <input
                required
                aria-label={t('偏移（V）')}
                type="number"
                step="any"
                min="-10000"
                max="10000"
                value={offset}
                onChange={(e) => setOffset(e.target.value)}
              />
            </label>
            <label>
              {t('耦合')}
              <select value={coupling} onChange={(e) => setCoupling(e.target.value)}>
                <option>DC</option>
                <option>AC</option>
                <option>GND</option>
              </select>
            </label>
            <button className="button" disabled={disabled}>
              {t('应用通道')}
            </button>
          </form>
        </details>
      </section>
      <section className="scope-control-section">
        <div className="scope-section-title">
          <h3>{t('触发')}</h3>
          <small>EDGE</small>
        </div>
        <p className="scope-actual">
          {t('实际：')}
          {edge
            ? `${edge.mode} · ${edge.source || '—'} · ${engineering(edge.level_v, 'V')} · ${edge.slope || '—'} · ${edge.sweep}`
            : t('尚未回读')}
        </p>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void run('trigger', triggerArgs());
          }}
        >
          <div className="scope-form-pair">
            <label>
              {t('触发源')}
              <select
                aria-label={t('触发源')}
                disabled={disabled}
                value={triggerChannel}
                onChange={(e) => setTriggerChannel(Number(e.target.value))}
              >
                {[1, 2, 3, 4].map((n) => (
                  <option key={n} value={n}>
                    CH{n}
                  </option>
                ))}
              </select>
            </label>
            <label>
              {t('边沿')}
              <select
                aria-label={t('触发边沿')}
                disabled={disabled}
                value={slope}
                onChange={(e) => setSlope(e.target.value)}
              >
                <option value="POS">{t('上升沿 ↗')}</option>
                <option value="NEG">{t('下降沿 ↘')}</option>
                <option value="RFAL">{t('双边沿')}</option>
              </select>
            </label>
          </div>
          <label>
            {t('扫描模式')}
            <select
              aria-label={t('触发扫描模式')}
              disabled={disabled}
              value={sweep}
              onChange={(e) => setSweep(e.target.value)}
            >
              <option value="AUTO">{t('自动 Auto')}</option>
              <option value="NORM">{t('正常 Normal')}</option>
              <option value="SING">{t('单次 Single')}</option>
            </select>
          </label>
          <label>
            {t('电平 / V')}
            <input
              required
              aria-label={t('边沿电平（V）')}
              type="number"
              step="any"
              min="-10000"
              max="10000"
              value={level}
              onChange={(e) => setLevel(e.target.value)}
            />
          </label>
          <button className="button" disabled={disabled}>
            {t('应用边沿触发')}
          </button>
        </form>
        <div className="scope-control-label">
          <label>{t('当前触发电平')}</label>
          <button
            className="text-button"
            disabled={disabled || triggerActual == null}
            onClick={() => void run('trigger', { channel: triggerChannel, level_v: 0 })}
          >
            {t('置零')}
          </button>
        </div>
        <CommitSlider
          label={t('触发电平滑条')}
          value={Math.max(triggerMin, Math.min(triggerMax, triggerActual ?? 0))}
          min={triggerMin}
          max={triggerMax}
          step={(triggerMax - triggerMin) / 200 || 0.001}
          disabled={disabled || triggerActual == null}
          display={(v) => engineering(v, 'V')}
          onCommit={(level_v) => void run('trigger', { channel: triggerChannel, level_v })}
        />
        <p className="instrument-caption">{t('下拉框为待应用设置；滑条只调整当前源的电平。')}</p>
      </section>
    </aside>
  );
}
