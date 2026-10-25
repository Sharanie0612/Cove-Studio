import { t } from '../../core/i18n.ts';
import { Check, Copy, Fingerprint, LoaderCircle } from 'lucide-react';
import type { CommandError } from '../../core/bridge';
import type { Manifest } from '../../core/types';
import Dialog from '../../components/Dialog';

export default function CommandConfirmation({
  trust,
  confirmation,
  busy,
  onCancel,
  onConfirm,
  toast,
}: {
  trust: CommandError;
  confirmation: NonNullable<Manifest['ui']['confirmations']>[number];
  busy: boolean;
  onCancel: () => void;
  onConfirm: () => void;
  toast: (message: string) => void;
}) {
  return (
    <Dialog labelId="trust-title" onClose={onCancel} busy={busy}>
      <div className="modal-icon">
        <Fingerprint size={25} />
      </div>
      <h2 id="trust-title">{confirmation.title}</h2>
      <p>{confirmation.description}</p>
      <div className="fingerprint">
        {confirmation.details.map((detail) => (
          <div className="confirmation-detail" key={detail.key}>
            <small>{detail.label}</small>
            <code>{trust.details[detail.key] || '—'}</code>
          </div>
        ))}
        <button
          className="icon-button"
          title={t('复制确认详情')}
          onClick={() =>
            void navigator.clipboard
              .writeText(
                confirmation.details
                  .map((detail) => `${detail.label}: ${trust.details[detail.key] || ''}`)
                  .join('\n'),
              )
              .then(() => toast(t('已复制')))
              .catch(() => toast(t('请手动复制')))
          }
        >
          <Copy size={14} />
        </button>
      </div>
      <div className="modal-actions">
        <button className="button" disabled={busy} onClick={onCancel}>
          {t('取消')}
        </button>
        <button className="button primary" disabled={busy} onClick={onConfirm}>
          {busy ? <LoaderCircle size={14} className="spin" /> : <Check size={14} />}{' '}
          {confirmation.confirmLabel}
        </button>
      </div>
    </Dialog>
  );
}
