import { t } from '../../core/i18n.ts';
import { ArrowRight, ChevronDown, LoaderCircle, Save, ShieldCheck, X } from 'lucide-react';
import type { Manifest } from '../../core/types';
import SchemaFields from '../../components/SchemaFields';
import Dialog from '../../components/Dialog';
import { isExternalProfile } from '../profiles';
import ProfileFeedback from './ProfileFeedback';
import type { WorkspaceConfiguration } from './useWorkspaceConfiguration';
import type { WorkspaceSession } from './useWorkspaceSession';

export default function ConfigurationDialog({
  manifest,
  configuration,
  session,
  busy,
}: {
  manifest: Manifest;
  configuration: WorkspaceConfiguration;
  session: WorkspaceSession;
  busy: boolean;
}) {
  const {
    closeConfig,
    trigger,
    currentProfile,
    form,
    draftName,
    setDraftName,
    values,
    setValues,
    error,
    save,
  } = configuration;
  const { connected, run } = session;
  const hasConnection = Boolean(manifest.ui.connection);
  const primary = manifest.ui.actions[0];
  const profileFeedback = <ProfileFeedback configuration={configuration} busy={busy} />;
  return (
    <Dialog
      labelId="connection-title"
      onClose={closeConfig}
      busy={busy}
      className="connection-dialog"
      initialFocus=".schema-fields input:not(:disabled)"
      returnFocus={trigger}
    >
      <div className="dialog-heading">
        <div>
          <h2 id="connection-title">
            {currentProfile ? currentProfile.name : hasConnection ? t('新建连接') : manifest.name}
          </h2>
          {currentProfile && isExternalProfile(currentProfile) && (
            <p>
              {currentProfile.readOnly
                ? currentProfile.editIssue
                : t('保存将更新源配置条目并自动备份，不创建副本。')}
            </p>
          )}
        </div>
        <button
          className="icon-button"
          aria-label={hasConnection ? t('关闭连接配置') : t('关闭工具配置')}
          disabled={busy}
          onClick={closeConfig}
        >
          <X size={18} />
        </button>
      </div>
      <form
        ref={form}
        id={`configuration-${manifest.id}`}
        onSubmit={(event) => {
          event.preventDefault();
          if (!connected && primary) void run(primary.command);
        }}
      >
        <div className="connection-dialog-body">
          {profileFeedback}
          {manifest.ui.profiles && (
            <label className="field connection-name">
              <span>{t('连接名称')}</span>
              <input
                aria-label={t('连接名称')}
                placeholder={t('例如：实验室设备')}
                value={draftName}
                maxLength={80}
                onChange={(event) => setDraftName(event.target.value)}
                disabled={busy}
              />
            </label>
          )}
          <SchemaFields
            fields={manifest.ui.fields.filter((field) => !field.advanced)}
            values={values}
            onChange={setValues}
            disabled={busy || connected}
          />
          {manifest.ui.fields.some((field) => field.advanced) && (
            <details
              className="advanced-fields"
              onInvalidCapture={(event) => {
                event.currentTarget.open = true;
              }}
            >
              <summary>
                {t('高级选项')}
                <ChevronDown size={12} />
              </summary>
              <SchemaFields
                fields={manifest.ui.fields.filter((field) => field.advanced)}
                values={values}
                onChange={setValues}
                disabled={busy || connected}
              />
            </details>
          )}
          {(error || currentProfile?.blockedReason) && (
            <div className="error-note" role="alert">
              {error || currentProfile?.blockedReason}
            </div>
          )}
        </div>
        <div className="connection-dialog-footer">
          {manifest.ui.fields.some((field) => field.secret || field.type === 'password') && (
            <span className="secret-hint">
              <ShieldCheck size={12} />
              {t('秘密字段不会保存')}
            </span>
          )}
          <div className="spacer" />
          {manifest.ui.profiles && (
            <button
              className="button"
              disabled={busy || currentProfile?.readOnly}
              type="button"
              onClick={() => void save()}
            >
              <Save size={13} />
              {t('保存')}
            </button>
          )}
          <button
            className="button primary"
            type="submit"
            disabled={busy || connected || Boolean(currentProfile?.blockedReason)}
          >
            {busy ? <LoaderCircle size={14} className="spin" /> : <ArrowRight size={14} />}{' '}
            {primary?.label || t('运行')}
          </button>
        </div>
      </form>
    </Dialog>
  );
}
