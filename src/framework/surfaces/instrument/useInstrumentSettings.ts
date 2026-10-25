import { useEffect, useState } from 'react';
import type { Status } from './types';
import { initialSettings, synchronizeSettings, type SettingsDraft } from './settingsDraft';

/** Manual drafts only synchronize after explicit readback or a channel change. */
export function useInstrumentSettings(
  channel: number,
  status: Status | undefined,
  synchronized: Status | undefined,
) {
  const [draft, setDraft] = useState(initialSettings);

  useEffect(() => {
    setDraft((current) => synchronizeSettings(current, synchronized, channel, 'all'));
  }, [synchronized]);

  useEffect(() => {
    setDraft((current) => synchronizeSettings(current, status, channel, 'channel'));
  }, [channel]);

  const update = <Key extends keyof SettingsDraft>(key: Key, value: SettingsDraft[Key]) =>
    setDraft((current) => ({ ...current, [key]: value }));
  return {
    ...draft,
    setScale: (value: string) => update('scale', value),
    setVscale: (value: string) => update('vscale', value),
    setOffset: (value: string) => update('offset', value),
    setCoupling: (value: string) => update('coupling', value),
    setLevel: (value: string) => update('level', value),
    setSlope: (value: string) => update('slope', value),
    setSweep: (value: string) => update('sweep', value),
    setTriggerChannel: (value: number) => update('triggerChannel', value),
  };
}

export type InstrumentSettings = ReturnType<typeof useInstrumentSettings>;
