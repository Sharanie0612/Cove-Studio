import { t } from '../../core/i18n.ts';
import { useEffect, useRef, useState } from 'react';
import { CommandError, invoke, subscribe } from '../../core/bridge';
import type { Manifest } from '../../core/types';
import { visible } from '../../components/SchemaFields';
import type { WorkspaceConfiguration } from './useWorkspaceConfiguration';
import type { WorkspaceOperation } from './useWorkspaceOperation';

export function useWorkspaceSession({
  manifest,
  runtime,
  configuration,
  operation,
  onConnection,
  toast,
}: {
  manifest: Manifest;
  runtime?: Manifest['runtime'];
  configuration: WorkspaceConfiguration;
  operation: WorkspaceOperation;
  onConnection: (id: string, connected: boolean) => void;
  toast: (message: string) => void;
}) {
  const [connected, setConnected] = useState(Boolean(manifest.runtime?.connected));
  const [sessionLabel, setSessionLabel] = useState(runtime?.message || '');
  const [bytes, setBytes] = useState(0);
  const [result, setResult] = useState<unknown>(undefined);
  const [clearToken, setClearToken] = useState(0);
  const [trust, setTrust] = useState<CommandError | null>(null);
  const [pendingCommand, setPendingCommand] = useState('');
  const confirmation = manifest.ui.confirmations?.find((item) => item.code === trust?.code);
  const onConnectionRef = useRef(onConnection);
  onConnectionRef.current = onConnection;

  useEffect(() => {
    if (runtime) {
      setConnected(runtime.connected);
      if (runtime.message) setSessionLabel(runtime.message);
    }
  }, [runtime?.connected, runtime?.message]);

  useEffect(
    () =>
      subscribe((event) => {
        if (event.pluginId !== manifest.id) return;
        if (event.event === 'result') setResult(event.data.result);
        if (event.event === 'status') {
          setConnected(Boolean(event.data.connected));
          onConnectionRef.current(manifest.id, Boolean(event.data.connected));
          if (event.data.connected) setSessionLabel(event.data.message || '');
        }
        if (event.event === manifest.ui.terminal?.dataEvent)
          setBytes((total) => total + Number(event.data.size || 0));
      }),
    [manifest.id, manifest.ui.terminal?.dataEvent],
  );

  async function run(command: string, extra: Record<string, unknown> = {}) {
    await operation.runExclusive(async () => {
      configuration.setError('');
      try {
        const disconnect = command === manifest.ui.connection?.disconnect;
        const payload: Record<string, unknown> = disconnect
          ? {}
          : Object.fromEntries(
              manifest.ui.fields
                .filter((field) => visible(field, configuration.values))
                .map((field) => [field.id, configuration.values[field.id]]),
            );
        if (!disconnect && configuration.selected && manifest.ui.profiles)
          payload.profile_id = configuration.selected;
        const response = await invoke<{ connected?: boolean; label?: string }>(
          manifest.id,
          command,
          { ...payload, ...extra },
        );
        if (manifest.ui.connection && response && typeof response.connected === 'boolean') {
          setConnected(response.connected);
          onConnectionRef.current(manifest.id, response.connected);
          if (response.connected) {
            setBytes(0);
            setSessionLabel(response.label || '');
            try {
              localStorage.setItem(
                `toolbench:${manifest.id}:last`,
                JSON.stringify(configuration.safeValues()),
              );
            } catch {
              /* Ephemeral mode. */
            }
            configuration.closeConfig();
            toast(t('已连接'));
          }
        } else {
          setResult(response);
          configuration.setConfigOpen(false);
        }
        setTrust(null);
      } catch (caught) {
        const failure = caught instanceof CommandError ? caught : new CommandError(String(caught));
        if (manifest.ui.confirmations?.some((item) => item.code === failure.code)) {
          setTrust(failure);
          setPendingCommand(command);
        } else {
          configuration.setError(failure.message);
          setTrust(null);
        }
      }
    });
  }

  function confirm() {
    if (!trust || !confirmation) return;
    void run(
      pendingCommand,
      Object.fromEntries(
        Object.entries(confirmation.payload).map(([key, source]) => [
          key,
          trust.details[source.fromDetail],
        ]),
      ),
    );
  }

  function clear() {
    setClearToken((value) => value + 1);
    setResult(undefined);
  }

  return {
    connected,
    sessionLabel,
    bytes,
    result,
    clearToken,
    trust,
    confirmation,
    cancelConfirmation: () => setTrust(null),
    confirm,
    run,
    clear,
  };
}

export type WorkspaceSession = ReturnType<typeof useWorkspaceSession>;
