import type { Status } from './types';

export interface SettingsDraft {
  scale: string;
  vscale: string;
  offset: string;
  coupling: string;
  level: string;
  slope: string;
  sweep: string;
  triggerChannel: number;
}

export const initialSettings: SettingsDraft = {
  scale: '0.001',
  vscale: '1',
  offset: '0',
  coupling: 'DC',
  level: '0',
  slope: 'POS',
  sweep: 'AUTO',
  triggerChannel: 1,
};

/** Channel selection changes vertical drafts; explicit readback refreshes all settings. */
export function synchronizeSettings(
  draft: SettingsDraft,
  status: Status | undefined,
  channel: number,
  scope: 'channel' | 'all',
): SettingsDraft {
  if (!status) return draft;
  const selected = status.channels.find((item) => item.channel === channel);
  const next = selected
    ? {
        ...draft,
        vscale: String(selected.scale_v_div),
        offset: String(selected.offset_v),
        coupling: selected.coupling,
      }
    : { ...draft };
  if (scope === 'channel') return next;
  next.scale = String(status.timebase_s_div);
  const edge = status.edge_trigger;
  if (edge?.mode === 'EDGE') {
    const source = Number(edge.source?.replace('CHAN', ''));
    if (source >= 1 && source <= 4) next.triggerChannel = source;
    if (edge.level_v != null) next.level = String(edge.level_v);
    if (edge.slope) next.slope = edge.slope;
    if (edge.sweep) next.sweep = edge.sweep;
  }
  return next;
}
