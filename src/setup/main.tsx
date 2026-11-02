import { createRoot } from 'react-dom/client';
import { normalizeAppearance, themeTokens } from '../core/appearance';
import '../styles/typography.css';
import '../styles/foundation.css';
import '../styles/shell.css';
import '../styles/motion.css';
import './setup.css';
import SetupApp from './SetupApp';
const root = document.documentElement;
const systemTheme = matchMedia('(prefers-color-scheme: dark)');
function applyTheme() {
  const mode = systemTheme.matches ? 'dark' : 'light';
  root.dataset.theme = mode;
  root.dataset.scheme = 'cove';
  for (const [key, value] of Object.entries(
    themeTokens(normalizeAppearance({ scheme: 'cove' }), mode),
  ))
    root.style.setProperty('--' + key, value);
}
applyTheme();
systemTheme.addEventListener('change', applyTheme);
createRoot(document.getElementById('root')!).render(<SetupApp />);
