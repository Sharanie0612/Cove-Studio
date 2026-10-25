import { getLocale } from '../../core/i18n.ts';
import type { ResultField } from '../contracts';

export function resultValue(value: unknown, key: string): unknown {
  return value !== null && typeof value === 'object' && Object.hasOwn(value, key)
    ? (value as Record<string, unknown>)[key]
    : undefined;
}

export function resultText(value: unknown, field?: ResultField): string {
  if (value === undefined || value === null) return '—';
  if (field?.format === 'number') {
    return typeof value === 'number' && Number.isFinite(value)
      ? new Intl.NumberFormat(getLocale(), { maximumFractionDigits: 8 }).format(value)
      : '—';
  }
  if (typeof value === 'object') return JSON.stringify(value, null, 2);
  return String(value);
}

export const RESULT_PAGE_SIZE = 50;
