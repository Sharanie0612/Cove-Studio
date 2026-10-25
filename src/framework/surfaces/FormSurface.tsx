import { t } from '../../core/i18n.ts';
import { useEffect, useState } from 'react';
import { ChevronLeft, ChevronRight, SquareTerminal } from 'lucide-react';
import type { PluginSurfaceProps, ResultField } from '../contracts';
import { RESULT_PAGE_SIZE, resultText, resultValue } from './resultData';
import './result.css';

function Value({ value, field }: { value: unknown; field: ResultField }) {
  return (
    <>
      {field.format === 'json' ? <pre>{resultText(value, field)}</pre> : resultText(value, field)}
      {field.unit && typeof value === 'number' && Number.isFinite(value) && (
        <small className="result-unit">{field.unit}</small>
      )}
    </>
  );
}

export default function FormSurface({ manifest, result, onConfigure }: PluginSurfaceProps) {
  const [page, setPage] = useState(0);
  useEffect(() => setPage(0), [result]);
  const layout = manifest.ui.result;
  if (result === undefined)
    return (
      <div className="generic-output">
        <div className="generic-empty">
          <SquareTerminal size={30} />
          <h2>{manifest.ui.empty?.title || t('准备运行')}</h2>
          <p>{manifest.ui.empty?.description || t('运行后在这里查看结果')}</p>
          <button className="button primary" onClick={onConfigure}>
            {manifest.ui.actions[0].label}
          </button>
        </div>
      </div>
    );
  if (!layout)
    return (
      <div className="generic-output">
        <pre>{typeof result === 'string' ? result : JSON.stringify(result, null, 2)}</pre>
      </div>
    );
  const table = layout.table;
  const rows = table ? resultValue(result, table.key) : undefined;
  const entries = Array.isArray(rows) ? rows : [];
  const pages = Math.max(1, Math.ceil(entries.length / RESULT_PAGE_SIZE));
  const current = Math.min(page, pages - 1);
  return (
    <section className="result-surface" aria-label={layout.title || t('运行结果')}>
      <header className="result-heading">
        <h2>{layout.title || t('运行结果')}</h2>
        <button className="button" onClick={onConfigure}>
          {t('再次运行')}
        </button>
      </header>
      {!!layout.fields?.length && (
        <dl className="result-fields">
          {layout.fields.map((field) => {
            const value = resultValue(result, field.key);
            const wide = field.format === 'json' || resultText(value, field).length > 160;
            return (
              <div key={field.key} className={wide ? 'result-wide' : ''}>
                <dt>{field.label}</dt>
                <dd tabIndex={wide ? 0 : undefined}>
                  <Value field={field} value={value} />
                </dd>
              </div>
            );
          })}
        </dl>
      )}
      {table && (
        <div className="result-table-section">
          {!Array.isArray(rows) && rows !== undefined && rows !== null ? (
            <p className="error-note" role="alert">
              {t('结果中的表格数据格式不正确，需要对象数组。')}
            </p>
          ) : !entries.length ? (
            <p className="list-empty compact">{table.emptyText || t('暂无记录')}</p>
          ) : (
            <>
              <div
                className="result-table-scroll"
                tabIndex={0}
                role="region"
                aria-label={t('结果表格')}
              >
                <table>
                  <thead>
                    <tr>
                      {table.columns.map((field) => (
                        <th scope="col" key={field.key}>
                          {field.label}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {entries
                      .slice(current * RESULT_PAGE_SIZE, (current + 1) * RESULT_PAGE_SIZE)
                      .map((row, index) => (
                        <tr key={current * RESULT_PAGE_SIZE + index}>
                          {table.columns.map((field) => (
                            <td key={field.key}>
                              <Value field={field} value={resultValue(row, field.key)} />
                            </td>
                          ))}
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
              <nav className="result-pagination" aria-label={t('结果分页')}>
                <span>
                  {t('当前有 {p0} 条记录 · 第 {p1} / {p2} 页', {
                    p0: entries.length,
                    p1: current + 1,
                    p2: pages,
                  })}
                </span>
                <button
                  className="icon-button"
                  aria-label={t('上一页结果')}
                  disabled={current === 0}
                  onClick={() => setPage(current - 1)}
                >
                  <ChevronLeft size={16} />
                </button>
                <button
                  className="icon-button"
                  aria-label={t('下一页结果')}
                  disabled={current + 1 >= pages}
                  onClick={() => setPage(current + 1)}
                >
                  <ChevronRight size={16} />
                </button>
              </nav>
            </>
          )}
        </div>
      )}
    </section>
  );
}
