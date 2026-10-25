import { t } from '../core/i18n.ts';
import { CircleCheck, CircleAlert } from 'lucide-react';
import type { Catalog } from '../core/types';

export default function WorkbenchStatus({
  catalog,
  native,
  error,
  onPlugins,
}: {
  catalog: Catalog;
  native: boolean;
  error: boolean;
  onPlugins: () => void;
}) {
  const connected = catalog.tools.filter((tool) => tool.runtime?.connected).length;
  const active = catalog.tools.filter((tool) => tool.runtime?.activity?.background).length;
  return (
    <footer className="workbench-status" aria-label={t('工作台状态')}>
      <span className={`host-state ${error ? 'has-error' : ''}`}>
        {error ? <CircleAlert size={12} /> : <CircleCheck size={12} />}
        {error ? t('连接异常') : native ? t('就绪') : t('预览')}
      </span>
      {catalog.issues.length > 0 && (
        <button className="has-error" onClick={onPlugins}>
          {catalog.issues.length}
          {t('个插件问题')}
        </button>
      )}
      <span className="status-spacer" />
      {active > 0 && (
        <span>
          {active}
          {t('个任务运行中')}
        </span>
      )}
      {connected > 0 && (
        <span>
          {connected}
          {t('个连接')}
        </span>
      )}
    </footer>
  );
}
