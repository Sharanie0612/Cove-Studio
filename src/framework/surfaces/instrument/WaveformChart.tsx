import { t } from '../../../core/i18n.ts';
import { Activity } from 'lucide-react';
import { engineering, cursorReadout } from '../instrumentView';
import type { Status, Waveform } from './types';
import type { waveformGeometry } from './waveformGeometry';

export default function WaveformChart({
  pluginId,
  channel,
  wave,
  selected,
  edge,
  grid,
  dots,
  cursors,
  cursor,
  geometry,
}: {
  pluginId: string;
  channel: number;
  wave: Waveform | undefined;
  selected: Status['channels'][number] | undefined;
  edge: Status['edge_trigger'];
  grid: boolean;
  dots: boolean;
  cursors: boolean;
  cursor: ReturnType<typeof cursorReadout>;
  geometry: ReturnType<typeof waveformGeometry>;
}) {
  const { min, max, x, y, path } = geometry;
  const triggerVisible =
    edge?.mode === 'EDGE' &&
    edge.source === `CHAN${channel}` &&
    edge.level_v != null &&
    y(edge.level_v) >= 38 &&
    y(edge.level_v) <= 326;
  return (
    <div className="scope-chart-wrap" data-channel={channel}>
      <svg
        className="waveform-chart"
        viewBox="0 0 1000 365"
        role="img"
        aria-label={
          wave
            ? t('CH{p0} 波形，{p1} 点，峰峰值 {p2}', {
                p0: channel,
                p1: wave.points,
                p2: engineering(wave.vpp_v, 'V'),
              })
            : t('CH{p0} 等待读取波形', { p0: channel })
        }
      >
        <defs>
          <clipPath id={`clip-${pluginId}`}>
            <rect x="52" y="38" width="896" height="288" />
          </clipPath>
        </defs>
        {grid && (
          <g className="scope-grid">
            {Array.from({ length: 11 }, (_, i) => (
              <line key={`x${i}`} x1={52 + i * 89.6} x2={52 + i * 89.6} y1="38" y2="326" />
            ))}
            {Array.from({ length: 9 }, (_, i) => (
              <line key={`y${i}`} x1="52" x2="948" y1={38 + i * 36} y2={38 + i * 36} />
            ))}
          </g>
        )}
        <path className="scope-axis" d="M52 182H948 M500 38V326" />
        {y(0) >= 38 && y(0) <= 326 && (
          <g className="scope-zero">
            <path d={`M43 ${y(0) - 5} L51 ${y(0)} L43 ${y(0) + 5} Z`} />
            <text x="17" y={y(0) + 4}>
              0
            </text>
          </g>
        )}
        {triggerVisible && (
          <g className="scope-trigger-line">
            <path d={`M52 ${y(edge!.level_v!)}H948`} />
            <text x="953" y={y(edge!.level_v!) + 4}>
              T
            </text>
          </g>
        )}
        {wave && (
          <g clipPath={`url(#clip-${pluginId})`}>
            {dots ? (
              wave.voltage_v.map((v, i) => (
                <circle className="scope-trace-dot" key={i} cx={x(i)} cy={y(v)} r="1.4" />
              ))
            ) : (
              <path
                className="scope-trace"
                d={path}
                fill="none"
                strokeWidth="1.8"
                vectorEffect="non-scaling-stroke"
              />
            )}
            {cursors && cursor && (
              <g className="scope-cursors">
                {[cursor.ia, cursor.ib].map((i, n) => (
                  <g key={n}>
                    <path d={`M${x(i)} 38V326`} />
                    <circle cx={x(i)} cy={y(wave.voltage_v[i])} r="4" />
                    <text x={x(i) + 6} y="55">
                      {n ? 'B' : 'A'}
                    </text>
                  </g>
                ))}
              </g>
            )}
          </g>
        )}
        <g className="scope-labels">
          <text x="53" y="25">
            {engineering(max, 'V')}
          </text>
          <text x="53" y="345">
            {engineering(min, 'V')}
          </text>
          <text x="170" y="345">
            {wave ? engineering(wave.time_s[0], 's') : '—'}
          </text>
          <text x="500" y="345" textAnchor="middle">
            {wave ? engineering((wave.time_s[0] + wave.time_s.at(-1)!) / 2, 's') : '—'}
          </text>
          <text x="947" y="345" textAnchor="end">
            {wave ? engineering(wave.time_s.at(-1), 's') : '—'}
          </text>
        </g>
      </svg>
      {!wave && (
        <div className="scope-chart-empty">
          <Activity size={28} />
          <b>
            {selected && !selected.enabled
              ? t('CH{p0} 已关闭', { p0: channel })
              : t('等待读取波形')}
          </b>
          <p>
            {selected && !selected.enabled
              ? t('在垂直面板开启通道后读取')
              : t('开启实时显示，或获取一帧查看')}
          </p>
        </div>
      )}
    </div>
  );
}
