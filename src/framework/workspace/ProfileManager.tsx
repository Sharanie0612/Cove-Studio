import { t } from '../../core/i18n.ts';
import {
  FolderKey,
  Pencil,
  Plus,
  RefreshCw,
  Search,
  TerminalSquare,
  Trash2,
  X,
} from 'lucide-react';
import type { Manifest } from '../../core/types';
import Dialog from '../../components/Dialog';
import { isExternalProfile, profileSourceLabel } from '../profiles';
import ProfileFeedback from './ProfileFeedback';
import type { WorkspaceConfiguration } from './useWorkspaceConfiguration';

export default function ProfileManager({
  manifest,
  configuration,
  connected,
  busy,
  toast,
}: {
  manifest: Manifest;
  configuration: WorkspaceConfiguration;
  connected: boolean;
  busy: boolean;
  toast: (message: string) => void;
}) {
  const {
    setManagerOpen,
    query,
    setQuery,
    store,
    configure,
    filtered,
    setDeleteError,
    setDeleteTarget,
  } = configuration;
  const profileFeedback = <ProfileFeedback configuration={configuration} busy={busy} />;
  return (
    <Dialog
      labelId="profiles-title"
      onClose={() => setManagerOpen(false)}
      className="profiles-dialog"
    >
      <div className="dialog-heading">
        <div>
          <h2 id="profiles-title">{t('连接管理')}</h2>
          <p>{t('管理工作台和插件发现的连接配置；保存配置与实际连接相互独立。')}</p>
        </div>
        <button
          className="icon-button"
          aria-label={t('关闭连接管理')}
          onClick={() => setManagerOpen(false)}
        >
          <X size={18} />
        </button>
      </div>
      <div className="profiles-tools">
        <label className="search-field">
          <Search size={14} />
          <input
            aria-label={t('搜索连接')}
            placeholder={t('查找名称或配置内容')}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </label>
        <button
          className="button"
          disabled={store.loading}
          onClick={() =>
            void store
              .refresh(true)
              .then(() => toast(t('已刷新现有配置')))
              .catch((failure) => toast(String(failure.message)))
          }
        >
          <RefreshCw size={14} className={store.loading ? 'spin' : ''} />
          {t('重新扫描')}
        </button>
        <button className="button primary" onClick={() => configure()}>
          <Plus size={14} />
          {t('新建')}
        </button>
      </div>
      {profileFeedback}
      <div className="profiles-list">
        {filtered.map((profile) => (
          <article className="profile-row" key={profile.id}>
            <span className="profile-mark">
              <TerminalSquare size={18} />
            </span>
            <div>
              <b>
                {profile.name}
                <span className="small-tag">
                  {isExternalProfile(profile)
                    ? profile.readOnly
                      ? t('{p0} · 需手动编辑', { p0: profileSourceLabel(profile) })
                      : profileSourceLabel(profile)
                    : t('工作台')}
                </span>
              </b>
              <p>
                {manifest.ui.fields
                  .filter((field) => !field.secret && field.type !== 'password')
                  .slice(0, 3)
                  .map((field) => profile.values[field.id])
                  .filter(Boolean)
                  .join(' · ')}
              </p>
              {profile.blockedReason && (
                <small className="profile-warning">{profile.blockedReason}</small>
              )}
            </div>
            <button
              className="button"
              disabled={connected || profile.readOnly}
              title={profile.editIssue || undefined}
              onClick={() => configure(profile)}
            >
              <Pencil size={13} />
              {t('编辑')}
            </button>
            {!profile.readOnly && (
              <button
                className="icon-button"
                aria-label={t('删除连接 {p0}', { p0: profile.name })}
                onClick={() => {
                  setDeleteError('');
                  setDeleteTarget(profile);
                }}
              >
                <Trash2 size={14} />
              </button>
            )}
          </article>
        ))}
        {!filtered.length && (
          <div className="list-empty">
            <FolderKey size={28} />
            <b>{query ? t('没有匹配的连接') : t('还没有连接配置')}</b>
            <p>{t('新建连接，或重新扫描插件支持的现有配置。')}</p>
          </div>
        )}
      </div>
      {store.issues.length > 0 && (
        <div className="profile-issues">
          {store.issues.map((issue, index) => (
            <p key={index}>{issue}</p>
          ))}
        </div>
      )}
      <div className="profiles-footnote">
        {t('删除配置不会断开已建立的连接。外部条目由插件更新原配置；可撤销的修改会显示恢复入口。')}
      </div>
    </Dialog>
  );
}
