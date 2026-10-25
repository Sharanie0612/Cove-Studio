import { t } from '../../core/i18n.ts';
import { Check } from 'lucide-react';
import type { WorkspaceConfiguration } from './useWorkspaceConfiguration';

export default function ProfileFeedback({
  configuration,
  busy,
}: {
  configuration: WorkspaceConfiguration;
  busy: boolean;
}) {
  const { profileBackup, undoProfile, undoError } = configuration;
  if (!profileBackup) return null;
  return (
    <div className="connection-feedback">
      <Check size={15} />
      <span>{t('源配置文件已更新，备份已保留。')}</span>
      <button className="text-button" disabled={busy} onClick={() => void undoProfile()}>
        {t('撤销')}
      </button>
      {undoError && (
        <span role="alert" className="danger">
          {undoError}
        </span>
      )}
    </div>
  );
}
