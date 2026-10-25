import type { Manifest } from '../core/types';

/** Host-owned layout; plugins supply data keys, never markup or component names. */
export interface ResultField {
  key: string;
  label: string;
  format?: 'text' | 'number' | 'json';
  unit?: string;
}

export interface ResultLayout {
  title?: string;
  fields?: ResultField[];
  table?: { key: string; columns: ResultField[]; emptyText?: string };
}

/** The stable boundary shared by every registered plugin surface. */
export interface PluginSurfaceProps {
  manifest: Manifest;
  runtime?: Manifest['runtime'];
  connected: boolean;
  active: boolean;
  clearToken: number;
  fontSize: number;
  result: unknown;
  onError: (message: string) => void;
  onConfigure: () => void;
}
