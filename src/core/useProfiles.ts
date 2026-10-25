import { t } from './i18n.ts';
import { useCallback, useEffect, useState } from 'react';
import { invoke } from './bridge';
import { readLocal } from './storage';
import type { Manifest, Profile, ProfileList } from './types';

const migrations = new Map<string, Promise<void>>();

export function useProfiles(manifest: Manifest, native: boolean) {
  const key = `${manifest.id}:profiles`;
  const [profiles, setProfiles] = useState<Profile[]>(() => readLocal(key, []));
  const [issues, setIssues] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const id = manifest.id;
  const listCommand = manifest.ui.profiles?.list,
    scanCommand = manifest.ui.profiles?.scan,
    saveCommand = manifest.ui.profiles?.save;
  const refresh = useCallback(
    async (scan = false) => {
      if (!native || !listCommand || !scanCommand) return;
      setLoading(true);
      try {
        const result = await invoke<ProfileList>(id, scan ? scanCommand : listCommand);
        setProfiles(result.profiles);
        setIssues(result.issues);
      } finally {
        setLoading(false);
      }
    },
    [id, listCommand, scanCommand, native],
  );
  useEffect(() => {
    if (!native || !listCommand || !saveCommand) return;
    let alive = true;
    void (async () => {
      // Migrate only workbench-owned, non-secret profile values once.
      if (!migrations.has(key))
        migrations.set(
          key,
          (async () => {
            const old = readLocal<Profile[]>(key, []);
            if (readLocal(`${key}:migrated`, false) || !old.length) return;
            const existing = await invoke<ProfileList>(id, listCommand);
            for (const profile of old) {
              if (
                existing.profiles.some(
                  (item) =>
                    item.name === profile.name &&
                    Object.entries(profile.values).every(
                      ([field, value]) => item.values[field] === value,
                    ),
                )
              )
                continue;
              const saved = await invoke<Profile>(id, saveCommand, {
                profile: { ...profile, id: undefined },
              });
              existing.profiles.push(saved);
            }
            localStorage.setItem(`toolbench:${key}:migrated`, 'true');
          })().catch((error) => {
            migrations.delete(key);
            throw error;
          }),
        );
      await migrations.get(key);
      if (alive) await refresh();
    })().catch((error) => {
      if (alive) setIssues([String(error.message || error)]);
    });
    return () => {
      alive = false;
    };
  }, [key, id, listCommand, saveCommand, native, refresh]);
  async function save(profile: Profile) {
    if (native && manifest.ui.profiles) {
      const saved = await invoke<Profile>(manifest.id, manifest.ui.profiles.save, { profile });
      await refresh();
      return saved;
    }
    const current =
      profile.readOnly || !profiles.some((item) => item.id === profile.id)
        ? {
            ...profile,
            id: crypto.randomUUID(),
            readOnly: false,
            source: 'workbench',
          }
        : profile;
    const next = profiles.some((item) => item.id === current.id)
      ? profiles.map((item) => (item.id === current.id ? current : item))
      : [...profiles, current];
    setProfiles(next);
    localStorage.setItem(`toolbench:${key}`, JSON.stringify(next));
    return current;
  }
  async function remove(profile: Profile) {
    if (native && manifest.ui.profiles) {
      const result = await invoke<{ backupId?: string }>(manifest.id, manifest.ui.profiles.remove, {
        profile_id: profile.id,
        revision: profile.revision,
      });
      await refresh();
      return result;
    } else {
      const next = profiles.filter((item) => item.id !== profile.id);
      setProfiles(next);
      localStorage.setItem(`toolbench:${key}`, JSON.stringify(next));
    }
  }
  async function restore(ticket: string) {
    if (!native || !manifest.ui.profiles?.restore) throw new Error(t('此插件不支持撤销'));
    await invoke(manifest.id, manifest.ui.profiles.restore, { ticket });
    await refresh();
  }
  return { profiles, issues, loading, refresh, save, remove, restore };
}
