import type { Manifest } from '../../../core/types';

export type Waveform = {
  channel: number;
  time_s: number[];
  voltage_v: number[];
  points: number;
  timestamp: string;
  vpp_v: number;
};
export type Measurement = {
  channel: number;
  timestamp: string;
  items: { item: string; value: number | null; unit: string; valid: boolean }[];
};
export type Status = {
  identity: { model: string; serial: string; firmware: string };
  address: string;
  trigger: string;
  timebase_s_div: number;
  sample_rate_hz: number;
  timestamp: string;
  edge_trigger?: {
    mode: string;
    source?: string;
    level_v?: number;
    slope?: string;
    sweep: string;
  };
  channels: {
    channel: number;
    enabled: boolean;
    scale_v_div: number;
    offset_v: number;
    coupling: string;
  }[];
};
export type Screen = { data_url: string; timestamp: string };
export type Data = {
  waveform?: Waveform;
  measurements?: Measurement;
  status?: Status;
  screenshot?: Screen;
};

export type InstrumentBindings = NonNullable<Manifest['ui']['instrument']>;
export type RunInstrument = (
  key: keyof InstrumentBindings,
  args?: Record<string, unknown>,
) => Promise<void>;
