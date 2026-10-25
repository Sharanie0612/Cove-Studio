import { useState } from 'react';
export function readLocal<T>(key: string, fallback: T): T {
  try {
    const value = localStorage.getItem(`toolbench:${key}`);
    return value === null ? fallback : JSON.parse(value);
  } catch {
    return fallback;
  }
}
export function useLocal<T>(key: string, initial: T) {
  const [value, set] = useState<T>(() => readLocal(key, initial));
  function update(next: T) {
    set(next);
    try {
      localStorage.setItem(`toolbench:${key}`, JSON.stringify(next));
    } catch {
      /* Ephemeral mode remains usable. */
    }
  }
  return [value, update] as const;
}
