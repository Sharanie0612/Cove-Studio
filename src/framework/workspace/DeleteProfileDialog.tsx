import { t } from '../../core/i18n.ts';
import { LoaderCircle } from 'lucide-react';
import Dialog from '../../components/Dialog';
import { isExternalProfile, profileSourceLabel } from '../profiles';
import type { WorkspaceConfiguration } from './useWorkspaceConfiguration';

export default function DeleteProfileDialog({
  configuration,
}: {
  configuration: WorkspaceConfiguration;
}) {
  const { deleteTarget, setDeleteTarget, deleting, deleteError, removeProfile } = configuration;
  if (!deleteTarget) return null;
  return (
    <Dialog labelId="delete-profile-title" onClose={() => setDeleteTarget(null)} busy={deleting}>
      <h2 id="delete-profile-title">{t('删除这个连接？')}</h2>
      <p>
        {isExternalProfile(deleteTarget)
          ? t('将由插件从 {p0} 移除“{p1}”。', {
              p0: profileSourceLabel(deleteTarget),
              p1: deleteTarget.name,
            })
          : t('将移除“{p0}”的工作台配置。', { p0: deleteTarget.name })}
      </p>
      {deleteError && (
        <div className="error-note" role="alert">
          {deleteError}
        </div>
      )}
      <div className="modal-actions">
        <button className="button" disabled={deleting} onClick={() => setDeleteTarget(null)}>
          {t('取消')}
        </button>
        <button className="button danger" disabled={deleting} onClick={() => void removeProfile()}>
          {deleting && <LoaderCircle size={14} className="spin" />}
          {t('删除连接')}
        </button>
      </div>
    </Dialog>
  );
}
