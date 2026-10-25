import type { Data, Measurement, Status, Waveform } from './types';

export interface AcquisitionTiming {
  metadataAt: number;
  lastFrameAt: number;
}

interface FrameReader {
  waveform: () => Promise<Waveform>;
  status: () => Promise<Status>;
  measurements: () => Promise<Measurement>;
  accept: (kind: keyof Data, result: Waveform | Status | Measurement) => void;
  canReadMetadata: () => boolean;
  timing: AcquisitionTiming;
  now: () => number;
  onFrame: (fps: number) => void;
}

/** A frame is mandatory; optional reads yield when a control or pause arrives. */
export async function readInstrumentFrame(reader: FrameReader) {
  const { timing } = reader;
  reader.accept('waveform', await reader.waveform());
  const now = reader.now();
  reader.onFrame(timing.lastFrameAt ? 1000 / (now - timing.lastFrameAt) : 0);
  timing.lastFrameAt = now;
  if (reader.canReadMetadata() && now - timing.metadataAt >= 2000) {
    reader.accept('status', await reader.status());
    if (reader.canReadMetadata()) reader.accept('measurements', await reader.measurements());
    timing.metadataAt = now;
  }
}

/** Worker events and command replies can arrive out of order for the same reading. */
export function mergeInstrumentData(previous: Data, kind: string, result: unknown): Data {
  const before = previous[kind as keyof Data];
  const incoming = result as { timestamp?: string };
  if (before?.timestamp && incoming.timestamp && before.timestamp > incoming.timestamp)
    return previous;
  return { ...previous, [kind]: result };
}
