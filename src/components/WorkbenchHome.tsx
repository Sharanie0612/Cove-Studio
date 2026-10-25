import { t, getLocale } from '../core/i18n.ts';
import { useState } from 'react';
import {
  ArrowRight,
  Clock3,
  Grid2X2,
  List,
  LoaderCircle,
  Plus,
  Search,
  Star,
  BrushCleaning,
  X,
} from 'lucide-react';
import type { Catalog, Manifest } from '../core/types';
import { useLocal } from '../core/storage';
import { categoryKey, filterTools, toolStatus } from '../core/pluginPresentation';
import { ToolIcon } from './ToolIcon';

type Collection = 'all' | 'favorites' | 'running';

export default function WorkbenchHome({
  catalog,
  native,
  opening,
  recentIds,
  onOpen,
  onPlugins,
  onStop,
  onRelease,
}: {
  catalog: Catalog;
  native: boolean;
  opening: string;
  recentIds: string[];
  onOpen: (tool: Manifest) => void;
  onPlugins: () => void;
  onStop: (tool: Manifest) => void;
  onRelease: () => void;
}) {
  const [query, setQuery] = useState('');
  const [category, setCategory] = useState('');
  const [collection, setCollection] = useState<Collection>('all');
  const [savedFavorites, setFavorites] = useLocal<string[]>('favorite-tools', []);
  const [savedLayout, setLayout] = useLocal('tool-layout', 'grid');
  const layout = savedLayout === 'list' ? 'list' : 'grid';
  const favorites = Array.isArray(savedFavorites)
    ? savedFavorites.filter((id) => typeof id === 'string')
    : [];
  const enabled = catalog.tools.filter((tool) => tool.enabled !== false);
  const running = enabled.filter((tool) => tool.runtime?.running);
  const source = collection === 'running' ? running : enabled;
  const filtered = filterTools(source, query, category, favorites, collection === 'favorites');
  const categories = [
    ...new Map(enabled.map((tool) => [categoryKey(tool), tool.category])).entries(),
  ]
    .filter(([key]) => Boolean(key))
    .sort(([, a], [, b]) => a.localeCompare(b, getLocale()));
  const recent = [...new Set(recentIds)]
    .map((id) => enabled.find((tool) => tool.id === id))
    .filter((tool): tool is Manifest => Boolean(tool))
    .slice(0, 5);
  function favorite(id: string) {
    setFavorites(
      favorites.includes(id) ? favorites.filter((item) => item !== id) : [...favorites, id],
    );
  }
  function reset() {
    setQuery('');
    setCategory('');
    setCollection('all');
  }
  return (
    <div className="page-body dashboard">
      <div className="page-heading">
        <div>
          <h1>{t('工作台')}</h1>
        </div>
        <div className="page-actions">
          <button
            className="icon-button"
            title={t('释放空闲进程')}
            aria-label={t('释放空闲进程')}
            disabled={!native || !running.length}
            onClick={onRelease}
          >
            <BrushCleaning size={18} />
          </button>
          <button className="button primary" onClick={onPlugins}>
            <Plus size={16} />
            {t('添加工具')}
          </button>
        </div>
      </div>
      {recent.length > 0 && !query && (
        <section className="recent-tools" aria-label={t('最近使用')}>
          <h2>
            <Clock3 size={14} />
            {t('最近使用')}
          </h2>
          <div>
            {recent.map((tool) => (
              <button key={tool.id} onClick={() => onOpen(tool)}>
                <ToolIcon tool={tool} />
                <span>{tool.name}</span>
                <ArrowRight size={13} />
              </button>
            ))}
          </div>
        </section>
      )}
      <section className="tool-library" aria-label={t('工具库')}>
        <div className="library-controls">
          <div className="collection-tabs" aria-label={t('工具筛选')}>
            {(
              [
                ['all', t('全部'), enabled.length],
                [
                  'favorites',
                  t('收藏'),
                  enabled.filter((tool) => favorites.includes(tool.id)).length,
                ],
                ['running', t('运行中'), running.length],
              ] as const
            ).map(([value, label, count]) => (
              <button
                key={value}
                aria-pressed={collection === value}
                onClick={() => setCollection(value)}
              >
                {label}
                <span>{count}</span>
              </button>
            ))}
          </div>
          <label className="search-field">
            <Search size={16} />
            <input
              aria-label={t('搜索工作台工具')}
              placeholder={t('搜索工具')}
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
            {query && (
              <button
                className="icon-button"
                aria-label={t('清除搜索')}
                onClick={() => setQuery('')}
              >
                <X size={13} />
              </button>
            )}
          </label>
          {categories.length > 1 && (
            <select
              className="category-select"
              aria-label={t('工具分类')}
              value={category}
              onChange={(event) => setCategory(event.target.value)}
            >
              <option value="">{t('所有分类')}</option>
              {categories.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          )}
          <div className="layout-switch" aria-label={t('显示方式')}>
            <button
              aria-label={t('卡片视图')}
              title={t('卡片视图')}
              aria-pressed={layout === 'grid'}
              onClick={() => setLayout('grid')}
            >
              <Grid2X2 size={16} />
            </button>
            <button
              aria-label={t('列表视图')}
              title={t('列表视图')}
              aria-pressed={layout === 'list'}
              onClick={() => setLayout('list')}
            >
              <List size={17} />
            </button>
          </div>
        </div>
        <div className={`tool-collection is-${layout}`}>
          {filtered.map((tool) => (
            <article className="tool-tile" key={tool.id}>
              <button
                className="tool-launch"
                aria-label={`${tool.category} ${tool.name} ${toolStatus(tool)}`}
                title={tool.description}
                disabled={!!opening || tool.compatibilityStatus?.supported === false}
                onClick={() => onOpen(tool)}
              >
                <ToolIcon tool={tool} />
                <span className="tile-name">{tool.name}</span>
                <span className="tile-description">{tool.subtitle || tool.category}</span>
                {(tool.runtime?.running ||
                  tool.ui.surface === 'mcp' ||
                  tool.compatibilityStatus?.supported === false) && (
                  <span
                    className={`tile-status ${tool.runtime?.connected || tool.runtime?.activity?.background ? 'is-live' : ''}`}
                  >
                    <i
                      className={`status-dot ${tool.runtime?.connected || tool.runtime?.activity?.background ? 'green' : ''}`}
                    />
                    {toolStatus(tool)}
                  </span>
                )}
                {opening === tool.id && <LoaderCircle size={16} className="tile-opening spin" />}
              </button>
              <div className="tile-actions">
                <button
                  className={`icon-button ${favorites.includes(tool.id) ? 'is-pinned' : ''}`}
                  aria-label={`${favorites.includes(tool.id) ? t('取消收藏') : t('收藏')} ${tool.name}`}
                  aria-pressed={favorites.includes(tool.id)}
                  onClick={() => favorite(tool.id)}
                >
                  <Star size={15} />
                </button>
                {collection === 'running' && tool.ui.surface !== 'mcp' && (
                  <button
                    className="icon-button"
                    aria-label={t('停止 {p0}', { p0: tool.name })}
                    title={t('停止进程')}
                    onClick={() => onStop(tool)}
                  >
                    <X size={15} />
                  </button>
                )}
              </div>
            </article>
          ))}
        </div>
        {!filtered.length && (
          <div className="list-empty">
            <Search size={26} />
            <b>{enabled.length ? t('没有匹配的工具') : t('还没有工具')}</b>
            <button className="button" onClick={enabled.length ? reset : onPlugins}>
              {enabled.length ? t('清除筛选') : t('添加工具')}
            </button>
          </div>
        )}
      </section>
    </div>
  );
}
