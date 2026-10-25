import { t, hostMessage } from '../core/i18n.ts';
import { useState } from 'react';
import { Check, ShieldCheck, X } from 'lucide-react';
import { hostCall } from '../core/bridge';
import { useAssistantState } from '../core/useAssistantState';
import Dialog, { DialogPresence } from './Dialog';

export default function ToolApprovals({ enabled }: { enabled: boolean }) {
  const { state, dismissApproval } = useAssistantState(enabled);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const current = enabled ? state.pending[0] : undefined;
  async function decide(approved: boolean) {
    if (!current || busy) return;
    setBusy(true);
    setError('');
    try {
      await hostCall('assistant_decide', current.id, approved);
      dismissApproval(current.id);
    } catch (failure) {
      setError((failure as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <DialogPresence>
      {current && (
        <Dialog
          labelId="tool-approval"
          busy={busy}
          onClose={() => void decide(false)}
          className="tool-approval"
        >
          <div className="dialog-heading">
            <div>
              <h2 id="tool-approval">
                <ShieldCheck size={20} />
                {t('确认本次工具操作')}
              </h2>
              <p>
                {t('{p0} 请求使用 {p1}', {
                  p0: current.owner === 'mcp' ? t('MCP 客户端') : t('插件调用方'),
                  p1: current.pluginName,
                })}
              </p>
            </div>
          </div>
          <p>{current.description}</p>
          <pre className="bridge-config" role="region" aria-label={t('工具操作参数')} tabIndex={0}>
            {JSON.stringify(current.arguments, null, 2)}
          </pre>
          {(current.redactedCount ?? 0) > 0 && (
            <p className="assistant-settings-note" role="note">
              {t(
                '已遮盖 {p0} 个敏感字段，标记为 [redacted]。执行时仍使用原始值；无法核对来源时请选择拒绝。',
                { p0: current.redactedCount || 0 },
              )}
            </p>
          )}
          <p className="assistant-settings-note">
            {t('全部非敏感参数均已列出，可滚动查看。允许后才会执行，拒绝、关闭或超时都不会执行。')}
          </p>
          {error && (
            <div className="error-note" role="alert">
              {hostMessage(error)}
            </div>
          )}
          <div className="modal-actions">
            <button className="button" disabled={busy} onClick={() => void decide(false)}>
              <X size={14} />
              {t('拒绝')}
            </button>
            <button className="button primary" disabled={busy} onClick={() => void decide(true)}>
              <Check size={14} />
              {t('允许本次')}
            </button>
          </div>
        </Dialog>
      )}
    </DialogPresence>
  );
}
