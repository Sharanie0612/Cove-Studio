import { useSyncExternalStore } from 'react';
import { getLocale, subscribeLocale } from './i18n.ts';

export function useLocale() {
  return useSyncExternalStore(subscribeLocale, getLocale, getLocale);
}
