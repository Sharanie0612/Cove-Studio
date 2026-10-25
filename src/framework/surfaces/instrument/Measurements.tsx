import { getLocale } from '../../../core/i18n.ts';
import { t } from '../../../core/i18n.ts';
import { engineering } from '../instrumentView';
import type { Measurement, RunInstrument } from './types';

const measureNames: Record<string, string> = {
  FREQ: '频率',
  VPP: '峰峰值',
  VRMS: '有效值',
  VAVG: '平均值',
  PER: '周期',
};

export default function Measurements({
  measurements,
  channel,
  disabled,
  run,
}: {
  measurements: Measurement | undefined;
  channel: number;
  disabled: boolean;
  run: RunInstrument;
}) {
  return (
    <section className="scope-measurements">
      <div className="scope-section-title">
        <h3>
          CH{channel}
          {t('测量')}
        </h3>
        <button
          className="quiet-button"
          disabled={disabled}
          onClick={() => void run('measure', { channel })}
        >
          {t('更新读数')}
        </button>
      </div>
      <div className="scope-measurement-grid">
        {(measurements?.channel === channel
          ? measurements.items
          : ['FREQ', 'VPP', 'VRMS', 'VAVG'].map((item) => ({
              item,
              value: null,
              unit: '',
              valid: false,
            }))
        ).map((item) => (
          <div key={item.item}>
            <small>{t(measureNames[item.item] || item.item)}</small>
            <b>{item.valid ? engineering(item.value, item.unit) : '—'}</b>
          </div>
        ))}
      </div>
      <p className="instrument-caption">
        {measurements?.channel === channel
          ? t('{p0} · 无效测量显示 —', {
              p0: new Date(measurements.timestamp).toLocaleTimeString(getLocale()),
            })
          : t('读取后显示仪器测量值')}
      </p>
    </section>
  );
}
