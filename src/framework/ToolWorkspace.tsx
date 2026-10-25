import { t, hostMessage } from '../core/i18n.ts';
import { X } from 'lucide-react';
import type { Manifest } from '../core/types';
import { DialogPresence } from '../components/Dialog';
import PluginSurface from './PluginSurface';
import CommandConfirmation from './workspace/CommandConfirmation';
import ConfigurationDialog from './workspace/ConfigurationDialog';
import DeleteProfileDialog from './workspace/DeleteProfileDialog';
import ProfileFeedback from './workspace/ProfileFeedback';
import ProfileManager from './workspace/ProfileManager';
import WorkspaceHeader from './workspace/WorkspaceHeader';
import WorkspaceStatus from './workspace/WorkspaceStatus';
import { useWorkspaceConfiguration } from './workspace/useWorkspaceConfiguration';
import { useWorkspaceFocus } from './workspace/useWorkspaceFocus';
import { useWorkspaceOperation } from './workspace/useWorkspaceOperation';
import { useWorkspaceSession } from './workspace/useWorkspaceSession';

export default function ToolWorkspace({
  manifest,
  active,
  native,
  runtime,
  fontSize,
  onConnection,
  onFocusChange,
  toast,
}: {
  manifest: Manifest;
  active: boolean;
  native: boolean;
  runtime?: Manifest['runtime'];
  fontSize: number;
  onConnection: (id: string, connected: boolean) => void;
  onFocusChange: (id: string, focused: boolean) => void;
  toast: (message: string) => void;
}) {
  const operation = useWorkspaceOperation();
  const configuration = useWorkspaceConfiguration(manifest, native, operation, toast);
  const session = useWorkspaceSession({
    manifest,
    runtime,
    configuration,
    operation,
    onConnection,
    toast,
  });
  const { focused, toggleFocus } = useWorkspaceFocus({
    id: manifest.id,
    active,
    configuration,
    operation,
    confirming: Boolean(session.trust),
    onFocusChange,
  });
  const { busy } = operation;
  const { error, configOpen, managerOpen, setError, configure } = configuration;

  return (
    <div className={`tool-workspace ${focused ? 'is-focused' : ''}`}>
      {error && !configOpen && (
        <div className="error-note" role="alert">
          {hostMessage(error)}
          <button className="icon-button" aria-label={t('关闭提示')} onClick={() => setError('')}>
            <X size={13} />
          </button>
        </div>
      )}
      {!configOpen && !managerOpen && <ProfileFeedback configuration={configuration} busy={busy} />}
      <section className="terminal-panel minimal-terminal">
        <WorkspaceHeader
          manifest={manifest}
          native={native}
          runtime={runtime}
          configuration={configuration}
          session={session}
          busy={busy}
          focused={focused}
          onToggleFocus={toggleFocus}
          toast={toast}
        />
        <PluginSurface
          manifest={manifest}
          runtime={runtime}
          result={session.result}
          connected={session.connected}
          active={active}
          clearToken={session.clearToken}
          fontSize={fontSize}
          onError={setError}
          onConfigure={() => configure()}
        />
        <WorkspaceStatus manifest={manifest} connected={session.connected} bytes={session.bytes} />
      </section>
      <DialogPresence>
        {configOpen && (
          <ConfigurationDialog
            manifest={manifest}
            configuration={configuration}
            session={session}
            busy={busy}
          />
        )}
      </DialogPresence>
      <DialogPresence>
        {managerOpen && (
          <ProfileManager
            manifest={manifest}
            configuration={configuration}
            connected={session.connected}
            busy={busy}
            toast={toast}
          />
        )}
      </DialogPresence>
      <DialogPresence>
        {configuration.deleteTarget && <DeleteProfileDialog configuration={configuration} />}
      </DialogPresence>
      <DialogPresence>
        {session.trust && session.confirmation && (
          <CommandConfirmation
            trust={session.trust}
            confirmation={session.confirmation}
            busy={busy}
            onCancel={session.cancelConfirmation}
            onConfirm={session.confirm}
            toast={toast}
          />
        )}
      </DialogPresence>
    </div>
  );
}
