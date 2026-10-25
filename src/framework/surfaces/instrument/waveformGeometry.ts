import type { Status, Waveform } from './types';

/** Plot coordinates retain the instrument's eight vertical divisions unless fitted locally. */
export function waveformGeometry(
  wave: Waveform | undefined,
  selected: Status['channels'][number] | undefined,
  fallbackScale: number,
  fit: boolean,
) {
  const actualScale = selected?.scale_v_div || fallbackScale;
  const actualOffset = selected?.offset_v ?? 0;
  const instrumentRange = !fit && selected && selected.scale_v_div > 0;
  const min = instrumentRange
    ? -actualOffset - actualScale * 4
    : wave
      ? Math.min(...wave.voltage_v)
      : -1;
  const max = instrumentRange
    ? -actualOffset + actualScale * 4
    : wave
      ? Math.max(...wave.voltage_v)
      : 1;
  const range = max - min || Math.max(Math.abs(max) * 0.1, 0.001);
  const x = (i: number) => 52 + (i / Math.max(1, (wave?.points || 1) - 1)) * 896;
  const y = (v: number) => 326 - ((v - min) / range) * 288;
  const path = wave?.voltage_v.map((v, i) => `${i ? 'L' : 'M'}${x(i)},${y(v)}`).join(' ');
  return { min, max, x, y, path };
}
