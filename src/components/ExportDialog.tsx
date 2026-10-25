import { t, hostMessage } from '../core/i18n.ts';
import { Check, FileArchive, FileCode2, LoaderCircle, X } from 'lucide-react';
import { useState } from 'react';
import { localizeTool } from '../core/pluginPresentation';
import type { ExportPreview } from '../core/types';
import { hostCall } from '../core/bridge';
import Dialog from './Dialog';

export default function ExportDialog({
  preview: sourcePreview,
  onClose,
  toast,
}: {
  preview: ExportPreview;
  onClose: () => void;
  toast: (text: string) => void;
}) {
  const preview = { ...sourcePreview, manifest: localizeTool(sourcePreview.manifest) };
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [savedPath, setSavedPath] = useState('');
  async function save() {
    setSaving(true);
    setError('');
    try {
      const result = await hostCall<{ path: string } | null>('save_plugin_export', preview.ticket);
      if (result) {
        setSavedPath(result.path);
        toast(t('插件包已保存，可在另一台 Cove 中导入'));
      }
    } catch (failure) {
      setError(String((failure as Error).message));
    } finally {
      setSaving(false);
    }
  }
  return (
    <Dialog labelId="export-title" onClose={onClose} busy={saving} className="export-dialog">
      <div className="dialog-heading">
        <div>
          <h2 id="export-title">{savedPath ? t('插件包已导出') : t('导出插件包')}</h2>
          <p>
            {preview.manifest.name} · v{preview.manifest.version}
          </p>
        </div>
        <button
          className="icon-button"
          aria-label={t('关闭导出')}
          disabled={saving}
          onClick={onClose}
        >
          <X size={18} />
        </button>
      </div>
      {savedPath ? (
        <div className="export-success">
          <span>
            <Check size={24} />
          </span>
          <h3>{t('可以分享了')}</h3>
          <p>{t('接收者在 Cove 的“插件 → 导入插件”中打开这个文件。')}</p>
          <code>{savedPath}</code>
          <button
            className="button"
            onClick={() =>
              void navigator.clipboard
                .writeText(savedPath)
                .then(() => toast(t('已复制保存路径')))
                .catch(() => setError(t('无法复制，请手动选择路径')))
            }
          >
            {t('复制文件路径')}
          </button>
        </div>
      ) : (
        <>
          <div className="export-summary">
            <FileArchive size={27} />
            <div>
              <b>{preview.fileName}</b>
              <p>
                {preview.fileCount}
                {t('个文件 · 压缩后')}
                {(preview.sizeBytes / 1024).toFixed(1)} KB
              </p>
            </div>
          </div>
          <p className="export-explanation">
            {t('仅导出插件代码和资源。连接配置、用户数据和独立 Python 环境不会打入包内。')}
          </p>
          <div className="export-files" aria-label={t('导出文件清单')}>
            {preview.files.map((file) => (
              <div key={file}>
                <FileCode2 size={13} />
                <code>{file}</code>
              </div>
            ))}
          </div>
          {preview.excluded.length > 0 && (
            <details className="export-excluded">
              <summary>
                {t('已排除')}
                {preview.excluded.length}
                {t('项开发或本地文件')}
              </summary>
              <pre>{preview.excluded.join('\n')}</pre>
            </details>
          )}
          <p className="export-caption">
            {t(
              '资源、vendor 依赖与 requirements.txt 会一同导出。接收者仍需满足依赖与系统兼容要求。',
            )}
          </p>
        </>
      )}
      {error && (
        <div className="error-note" role="alert">
          {hostMessage(error)}
        </div>
      )}
      <div className="modal-actions">
        {savedPath ? (
          <button className="button primary" onClick={onClose}>
            {t('完成')}
          </button>
        ) : (
          <>
            <button className="button" disabled={saving} onClick={onClose}>
              {t('取消')}
            </button>
            <button className="button primary" disabled={saving} onClick={() => void save()}>
              {saving ? <LoaderCircle size={14} className="spin" /> : <FileArchive size={14} />}
              {t('选择位置并保存')}
            </button>
          </>
        )}
      </div>
    </Dialog>
  );
}
