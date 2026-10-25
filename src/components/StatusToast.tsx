import { t, hostMessage } from '../core/i18n.ts';
import { useRef } from 'react';
import { Check, X } from 'lucide-react';
export default function StatusToast({
  message,
  onClose,
}: {
  message: string;
  onClose: () => void;
}) {
  const last = useRef(message);
  if (message) last.current = message;
  return (
    <div
      className={`toast status-toast ${message ? 'is-visible' : ''}`}
      role="status"
      aria-hidden={!message}
      inert={!message}
    >
      <Check size={16} />
      <span>{hostMessage(last.current)}</span>
      <button className="icon-button" aria-label={t('关闭提示')} onClick={onClose}>
        <X size={14} />
      </button>
    </div>
  );
}
