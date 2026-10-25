import { t } from '../../core/i18n.ts';
import type { Manifest } from '../../core/types';

export default function WorkspaceStatus({
  manifest,
  connected,
  bytes,
}: {
  manifest: Manifest;
  connected: boolean;
  bytes: number;
}) {
  return (
    <div className="terminal-status">
      <span>
        {connected
          ? manifest.ui.terminal
            ? t('{p0} KB 已接收', { p0: (bytes / 1024).toFixed(1) })
            : t('已连接')
          : t('就绪')}
      </span>
      {manifest.ui.surface === 'terminal' && <span>UTF-8</span>}
    </div>
  );
}
