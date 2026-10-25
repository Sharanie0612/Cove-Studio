import { useLayoutEffect, useState } from 'react';
import { readLocal } from './storage';
import { normalizeAppearance, resolvedMode, themeTokens, type Appearance } from './appearance';

function readAppearance() {
  return normalizeAppearance(readLocal('appearance-v1', null), readLocal('theme', 'light'));
}
function apply(appearance: Appearance, systemDark: boolean) {
  const mode = resolvedMode(appearance.mode, systemDark),
    root = document.documentElement;
  root.dataset.theme = mode;
  root.dataset.scheme = appearance.scheme;
  root.style.colorScheme = mode;
  for (const [key, value] of Object.entries(themeTokens(appearance, mode)))
    root.style.setProperty('--' + key, value);
  window.dispatchEvent(new Event('cove-appearance-change'));
}
export function initializeAppearance() {
  apply(readAppearance(), matchMedia('(prefers-color-scheme: dark)').matches);
}
export function useAppearance() {
  const [appearance, setState] = useState(readAppearance);
  const [systemDark, setSystemDark] = useState(
    () => matchMedia('(prefers-color-scheme: dark)').matches,
  );
  useLayoutEffect(() => {
    const media = matchMedia('(prefers-color-scheme: dark)');
    const changed = () => setSystemDark(media.matches);
    media.addEventListener('change', changed);
    changed();
    return () => media.removeEventListener('change', changed);
  }, []);
  useLayoutEffect(() => {
    apply(appearance, systemDark);
  }, [appearance, systemDark]);
  function setAppearance(next: Appearance) {
    const clean = normalizeAppearance(next);
    setState(clean);
    try {
      localStorage.setItem('toolbench:appearance-v1', JSON.stringify(clean));
    } catch {
      /* Keep live preview usable in ephemeral mode. */
    }
  }
  return {
    appearance,
    setAppearance,
    mode: resolvedMode(appearance.mode, systemDark),
  };
}
