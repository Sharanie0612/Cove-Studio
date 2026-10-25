import { t } from '../../../core/i18n.ts';
import { useEffect, useRef, useState } from 'react';
import { invoke, subscribe } from '../../../core/bridge';
import type { Manifest } from '../../../core/types';
import { InstrumentLive } from '../instrumentLive';
import { mergeInstrumentData, readInstrumentFrame } from './acquisition';
import type { Data, Measurement, Status, Waveform } from './types';

export interface InstrumentSessionOptions {
  manifest: Manifest;
  connected: boolean;
  active: boolean;
  clearToken: number;
  channel: number;
  onError: (message: string) => void;
}

/** Device I/O and its lifecycle; editing drafts and display options live elsewhere. */
export function useInstrumentSession({
  manifest,
  connected,
  active,
  clearToken,
  channel,
  onError,
}: InstrumentSessionOptions) {
  const bindings = manifest.ui.instrument!;
  const [data, setData] = useState<Data>({});
  const [busy, setBusy] = useState('');
  const busyRef = useRef(false);
  const localControls = useRef(new Set<string>());
  const [notice, setNotice] = useState('');
  const [live, setLive] = useState(false);
  const [interval, setIntervalMs] = useState(500);
  const [visible, setVisible] = useState(!document.hidden);
  const [fps, setFps] = useState(0);
  const timing = useRef({ metadataAt: 0, lastFrameAt: 0 });
  const [settingsStatus, syncInputs] = useState<Status>();
  const mounted = useRef(true);
  const pollingAllowed = useRef(false);
  pollingAllowed.current = live && connected && active && visible;
  const poll = useRef<() => Promise<void>>(async () => {});
  const loop = useRef<InstrumentLive | null>(null);
  if (!loop.current)
    loop.current = new InstrumentLive(
      () => poll.current(),
      (error) => {
        if ((error as { code?: string }).code === 'INSTRUMENT_BUSY') return true;
        if (mounted.current) {
          setLive(false);
          onError(t('实时显示已暂停：{p0}', { p0: (error as Error).message }));
        }
        return false;
      },
    );
  const scheduler = loop.current;
  function accept(kind: string, result: unknown) {
    if (!mounted.current) return;
    setData((old) => mergeInstrumentData(old, kind, result));
  }

  poll.current = () =>
    readInstrumentFrame({
      waveform: () => invoke<Waveform>(manifest.id, bindings.waveform, { channel }),
      status: () => invoke<Status>(manifest.id, bindings.status),
      measurements: () => invoke<Measurement>(manifest.id, bindings.measure, { channel }),
      accept,
      canReadMetadata: () => pollingAllowed.current && !scheduler.hasCommands(),
      timing: timing.current,
      now: () => performance.now(),
      onFrame: (nextFps) => {
        if (mounted.current) setFps(nextFps);
      },
    });
  useEffect(() => {
    mounted.current = true;
    const changed = () => setVisible(!document.hidden);
    document.addEventListener('visibilitychange', changed);
    return () => {
      mounted.current = false;
      scheduler.stop();
      document.removeEventListener('visibilitychange', changed);
    };
  }, [scheduler]);
  useEffect(() => {
    if (!connected) setLive(false);
    if (live && connected && active && visible) {
      timing.current.lastFrameAt = 0;
      timing.current.metadataAt = -Infinity;
      setFps(0);
      scheduler.start(interval);
    } else scheduler.stop();
    return () => scheduler.stop();
  }, [scheduler, live, connected, active, visible, interval, channel]);
  useEffect(() => {
    setData({});
    setNotice('');
  }, [clearToken]);
  useEffect(
    () =>
      subscribe((event) => {
        if (event.pluginId !== manifest.id || event.event !== 'instrument') return;
        const kind = String(event.data.kind);
        if (kind === 'control') {
          timing.current.metadataAt = -Infinity;
          const timestamp = (event.data.result as { timestamp?: string })?.timestamp;
          if (timestamp && localControls.current.delete(timestamp)) return;
          if (!connected) return;
          if (!busyRef.current) setNotice(t('已接收确认后的 AI 控制，正在同步实际设置。'));
          void scheduler
            .execute(async () => {
              const status = await invoke<Status>(manifest.id, bindings.status);
              accept('status', status);
              if (status.channels.find((c) => c.channel === channel)?.enabled)
                accept(
                  'waveform',
                  await invoke<Waveform>(manifest.id, bindings.waveform, {
                    channel,
                  }),
                );
              else setLive(false);
            })
            .catch((error) =>
              onError(t('控制后的显示更新失败：{p0}', { p0: (error as Error).message })),
            );
          return;
        }
        if (['status', 'measurements', 'waveform', 'screenshot'].includes(kind))
          accept(kind, event.data.result);
      }),
    [manifest.id, connected, channel, scheduler],
  );
  useEffect(() => {
    if (!connected) return;
    setData({});
    let alive = true;
    void invoke<{ latest: Data }>(manifest.id, bindings.snapshot)
      .then((result) => {
        if (alive) {
          setData((old) => ({ ...result.latest, ...old }));
          if (result.latest.status) syncInputs(result.latest.status);
        }
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, [manifest.id, bindings.snapshot, connected]);
  async function run(key: keyof typeof bindings, args: Record<string, unknown> = {}) {
    if (!connected || busyRef.current) return;
    busyRef.current = true;
    setBusy(key);
    onError('');
    setNotice('');
    try {
      await scheduler.execute(async () => {
        const result = await invoke(manifest.id, bindings[key], args);
        const kind = (
          {
            measure: 'measurements',
            waveform: 'waveform',
            status: 'status',
            screenshot: 'screenshot',
          } as Record<string, string>
        )[key];
        if (kind) {
          accept(kind, result);
          if (key === 'status') syncInputs(result as Status);
        } else {
          const timestamp = (result as { timestamp?: string }).timestamp;
          if (timestamp) {
            localControls.current.add(timestamp);
            if (localControls.current.size > 32)
              localControls.current.delete(localControls.current.values().next().value!);
          }
          setNotice(t('设置已生效，已回读实际参数。'));
          const status = await invoke<Status>(manifest.id, bindings.status);
          accept('status', status);
          syncInputs(status);
          if (status.channels.find((c) => c.channel === channel)?.enabled)
            accept(
              'waveform',
              await invoke<Waveform>(manifest.id, bindings.waveform, {
                channel,
              }),
            );
          else setLive(false);
        }
      });
    } catch (error) {
      onError((error as Error).message);
    } finally {
      busyRef.current = false;
      setBusy('');
    }
  }
  return {
    data,
    busy,
    notice,
    live,
    setLive,
    interval,
    setIntervalMs,
    visible,
    fps,
    run,
    settingsStatus,
  };
}

export type InstrumentSession = ReturnType<typeof useInstrumentSession>;
