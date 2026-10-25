import { t } from '../core/i18n.ts';
import type { Manifest, RuntimeDiagnostic } from '../core/types';
import Dialog from './Dialog';

export default function RuntimeDiagnostics({
  tool,
  report,
  onClose,
}: {
  tool: Manifest;
  report: RuntimeDiagnostic | null;
  onClose: () => void;
}) {
  return (
    <Dialog labelId="runtime-diagnostic-title" onClose={onClose}>
      <h2 id="runtime-diagnostic-title">
        {tool.name}
        {t('· 运行诊断')}
      </h2>
      <p>
        {t(
          '仅保留异常类型、模块名、文件名和行号。命令参数、源代码、原始错误消息和 stderr 均不会写入报告。',
        )}
      </p>
      {report ? (
        <pre className="diagnostic-report">{JSON.stringify(report, null, 2)}</pre>
      ) : (
        <p>{t('尚无诊断记录。检查所选 Python 是否可用，或重新启动后查看。')}</p>
      )}
      <div className="modal-actions">
        <button className="button primary" onClick={onClose}>
          {t('完成')}
        </button>
      </div>
    </Dialog>
  );
}
