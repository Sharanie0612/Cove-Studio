import { t } from '../core/i18n.ts';
import { Plus, X } from 'lucide-react';
import { useEffect } from 'react';
import type { Catalog, Manifest } from '../core/types';
import { ToolIcon } from './ToolIcon';

export default function WorkspaceTabs({
  tabs,
  activeId,
  catalog,
  focused,
  onActivate,
  onClose,
  onAdd,
}: {
  tabs: Manifest[];
  activeId: string;
  catalog: Catalog;
  focused: boolean;
  onActivate: (id: string) => void;
  onClose: (tool: Manifest) => void;
  onAdd: () => void;
}) {
  useEffect(() => {
    document
      .getElementById(`tab-${activeId}`)
      ?.scrollIntoView({ block: 'nearest', inline: 'nearest' });
  }, [activeId]);
  if (!tabs.length) return null;
  return (
    <nav className="workspace-tabs" aria-label={t('已打开的工具')} inert={focused}>
      <div className="workspace-tab-list" role="tablist" aria-label={t('工具标签')}>
        {tabs.map((tool, index) => (
          <div
            className={`workspace-tab ${activeId === tool.id ? 'active' : ''}`}
            key={tool.id}
            role="presentation"
          >
            <button
              role="tab"
              title={tool.name}
              id={`tab-${tool.id}`}
              aria-controls={`panel-${tool.id}`}
              aria-selected={activeId === tool.id}
              tabIndex={activeId === tool.id || (!activeId && index === 0) ? 0 : -1}
              onClick={() => onActivate(tool.id)}
              onKeyDown={(event) => {
                const offset = event.key === 'ArrowRight' ? 1 : event.key === 'ArrowLeft' ? -1 : 0;
                const next =
                  event.key === 'Home'
                    ? 0
                    : event.key === 'End'
                      ? tabs.length - 1
                      : offset
                        ? (index + offset + tabs.length) % tabs.length
                        : -1;
                if (next < 0) return;
                event.preventDefault();
                onActivate(tabs[next].id);
                document.getElementById(`tab-${tabs[next].id}`)?.focus();
              }}
            >
              <ToolIcon tool={tool} />
              <span>{tool.name}</span>
              {catalog.tools.find((item) => item.id === tool.id)?.runtime?.connected && (
                <span className="status-dot green" />
              )}
            </button>
            <button
              className="tab-close"
              aria-label={t('关闭 {p0}', { p0: tool.name })}
              onClick={() => onClose(tool)}
            >
              <X size={13} />
            </button>
          </div>
        ))}
      </div>
      <button
        className="tab-add"
        aria-label={t('选择工具')}
        title={t('打开工具 · Ctrl K')}
        onClick={onAdd}
      >
        <Plus size={18} />
      </button>
    </nav>
  );
}
