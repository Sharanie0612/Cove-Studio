import { t } from '../core/i18n.ts';
import type { Profile } from '../core/types';

export function isExternalProfile(profile: Profile): boolean {
  return Boolean(profile.source && profile.source !== 'workbench');
}
export function profileSourceLabel(profile: Profile): string {
  if (profile.sourceLabel) return profile.sourceLabel;

  return isExternalProfile(profile) ? t('外部配置') : t('工作台');
}
