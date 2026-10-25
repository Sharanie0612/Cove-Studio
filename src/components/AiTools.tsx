import { t, hostMessage } from '../core/i18n.ts';
import { useState } from 'react';
import { Check, LoaderCircle, Package, ShieldCheck, ArrowUpRight, Eye, Save } from 'lucide-react';
import { hostCall } from '../core/bridge';
import { useAssistantState } from '../core/useAssistantState';
import type { Catalog } from '../core/types';
import { ToolIcon } from './ToolIcon';

export default function AiTools({
  catalog,
  native,
  active,
  toast,
  onPlugins,
  onMcp,
}: {
  catalog: Catalog;
  native: boolean;
  active: boolean;
  toast: (text: string) => void;
  onPlugins: () => void;
  onMcp: () => void;
}) {
  const { state, refresh, error: loadError, loaded } = useAssistantState(native, active);
  const [draft, setDraft] = useState<string[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const selection = draft ?? state.selected;
  const tools = catalog.tools.filter((tool) => tool.ai?.tools.length);
  const dirty =
    draft !== null && [...selection].sort().join('\n') !== [...state.selected].sort().join('\n');
  async function save() {
    setBusy(true);
    setError('');
    try {
      await hostCall('assistant_allow', selection);
      await refresh();
      setDraft(null);
      toast(t('授权已保存'));
    } catch (failure) {
      setError((failure as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="page-body ai-tools-page">
      <div className="page-heading">
        <div>
          <h1>{t('智能体工具')}</h1>
          <p>{t('选择智能体可以使用的工具。写操作仍需你逐次确认。')}</p>
        </div>
        <div className="page-actions">
          <button className="button" onClick={onMcp}>
            {t('连接客户端')}
            <ArrowUpRight size={14} />
          </button>
          <button
            className="button primary"
            disabled={!native || !dirty || busy || !loaded}
            onClick={() => void save()}
          >
            {busy ? <LoaderCircle className="spin" size={15} /> : <Save size={15} />}
            {t('保存授权')}
          </button>
        </div>
      </div>
      <div className="authorization-toolbar">
        <span>
          {selection.length}
          {t('个已选择')}
        </span>
        {dirty && (
          <>
            <span className="unsaved-mark">{t('未保存')}</span>
            <button className="text-button" disabled={busy} onClick={() => setDraft(null)}>
              {t('撤销更改')}
            </button>
          </>
        )}
      </div>
      {state.enabled === false && <p className="permission-explanation">{t('MCP 已停用。')}</p>}
      {(error || loadError) && (
        <div className="error-note" role="alert">
          {hostMessage(error || loadError)}
        </div>
      )}
      <div className="ai-tool-grid">
        {tools.map((tool) => {
          const declarations = tool.ai!.tools,
            selected = selection.includes(tool.id);
          return (
            <label
              className={`ai-tool-card ${selected ? 'is-selected' : ''}`}
              key={tool.id}
              title={tool.description}
            >
              <input
                type="checkbox"
                checked={selected}
                disabled={!native || !loaded || busy}
                onChange={(event) =>
                  setDraft(
                    event.target.checked
                      ? [...selection, tool.id]
                      : selection.filter((id) => id !== tool.id),
                  )
                }
              />
              <ToolIcon tool={tool} />
              <span className="ai-tool-description">
                <b>{tool.name}</b>
                <small className="tool-permissions">
                  {tool.enabled === false ? (
                    t('已停用')
                  ) : (
                    <>
                      <span>
                        <Eye size={13} />
                        {declarations.filter((item) => item.readOnly).length}
                        {t('个只读')}
                      </span>
                      <span>
                        <ShieldCheck size={13} />
                        {declarations.filter((item) => !item.readOnly).length}
                        {t('个需确认')}
                      </span>
                    </>
                  )}
                </small>
              </span>
              <span className="ai-tool-check">{selected && <Check size={15} />}</span>
            </label>
          );
        })}
      </div>
      {!tools.length && (
        <div className="list-empty">
          <Package size={30} />
          <b>{t('还没有可共享的插件')}</b>

          <button className="button" onClick={onPlugins}>
            {t('管理插件')}
          </button>
        </div>
      )}
      <details className="help-disclosure">
        <summary>
          <ShieldCheck size={14} />
          {t('授权规则')}
        </summary>
        <p>{t('只读工具直接返回结果，写操作逐次确认。取消授权会撤销尚未执行的请求。')}</p>
      </details>
    </div>
  );
}
