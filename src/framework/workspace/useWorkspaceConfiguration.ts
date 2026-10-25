import { t } from '../../core/i18n.ts';
import { useRef, useState } from 'react';
import type { Manifest, Profile, Values } from '../../core/types';
import { readLocal } from '../../core/storage';
import { useProfiles } from '../../core/useProfiles';
import { isExternalProfile } from '../profiles';
import { clearSecrets, configurationValues, publicValues } from './configurationValues';
import type { WorkspaceOperation } from './useWorkspaceOperation';

export function useWorkspaceConfiguration(
  manifest: Manifest,
  native: boolean,
  operation: WorkspaceOperation,
  toast: (message: string) => void,
) {
  const store = useProfiles(manifest, native);
  const [values, setValues] = useState<Values>(() =>
    configurationValues(manifest.ui.fields, readLocal<Values>(`${manifest.id}:last`, {})),
  );
  const form = useRef<HTMLFormElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const [configOpen, setConfigOpen] = useState(false);
  const [managerOpen, setManagerOpen] = useState(false);
  const [error, setError] = useState('');
  const [selected, setSelected] = useState('');
  const [draftName, setDraftName] = useState('');
  const [query, setQuery] = useState('');
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState('');
  const [deleteTarget, setDeleteTarget] = useState<Profile | null>(null);
  const [profileBackup, setProfileBackup] = useState('');
  const [undoError, setUndoError] = useState('');
  const currentProfile = store.profiles.find((profile) => profile.id === selected);
  const filtered = store.profiles.filter((profile) =>
    `${profile.name} ${Object.values(profile.values).join(' ')}`
      .toLowerCase()
      .includes(query.toLowerCase()),
  );

  function closeConfig() {
    setConfigOpen(false);
    setValues((current) => clearSecrets(manifest.ui.fields, current));
  }

  function safeValues() {
    return publicValues(manifest.ui.fields, values);
  }

  function configure(profile?: Profile) {
    setError('');
    setSelected(profile?.id || '');
    setDraftName(profile?.name || '');
    if (profile || manifest.ui.connection)
      setValues(configurationValues(manifest.ui.fields, profile?.values));
    setManagerOpen(false);
    setConfigOpen(true);
  }

  async function save() {
    if (operation.busyRef.current || !form.current?.reportValidity()) return;
    if (!draftName.trim()) {
      setError(t('请填写连接名称，方便下次找到。'));
      return;
    }
    await operation.runExclusive(async () => {
      try {
        const saved = await store.save({
          ...currentProfile,
          id: currentProfile?.id || '',
          name: draftName.trim(),
          values: safeValues(),
        });
        setSelected(saved.id);
        if (saved.backupId) setProfileBackup(saved.backupId);
        setError('');
        toast(
          currentProfile && isExternalProfile(currentProfile)
            ? t('源配置条目已更新')
            : t('连接已保存'),
        );
      } catch (failure) {
        setError(String((failure as Error).message));
      }
    });
  }

  async function removeProfile() {
    if (!deleteTarget || deleting) return;
    setDeleting(true);
    setDeleteError('');
    try {
      const removed = await store.remove(deleteTarget);
      if (removed?.backupId) setProfileBackup(removed.backupId);
      setDeleteTarget(null);
      setSelected('');
      toast(t('连接已删除'));
    } catch (failure) {
      setDeleteError(String((failure as Error).message));
    } finally {
      setDeleting(false);
    }
  }

  async function undoProfile() {
    if (!profileBackup) return;
    await operation.runExclusive(async () => {
      setUndoError('');
      try {
        await store.restore(profileBackup);
        setProfileBackup('');
        closeConfig();
        setSelected('');
        setManagerOpen(true);
        toast(t('已恢复修改前的源配置'));
      } catch (failure) {
        setUndoError(String((failure as Error).message));
      }
    });
  }

  return {
    store,
    values,
    setValues,
    form,
    trigger,
    configOpen,
    setConfigOpen,
    managerOpen,
    setManagerOpen,
    error,
    setError,
    selected,
    draftName,
    setDraftName,
    query,
    setQuery,
    deleting,
    deleteError,
    setDeleteError,
    deleteTarget,
    setDeleteTarget,
    profileBackup,
    undoError,
    currentProfile,
    filtered,
    closeConfig,
    safeValues,
    configure,
    save,
    removeProfile,
    undoProfile,
  };
}

export type WorkspaceConfiguration = ReturnType<typeof useWorkspaceConfiguration>;
