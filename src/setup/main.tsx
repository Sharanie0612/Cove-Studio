import { createRoot } from 'react-dom/client';
import { normalizeAppearance, themeTokens } from '../core/appearance';
import '../styles/typography.css';
import '../styles/foundation.css';
import '../styles/shell.css';
import '../styles/motion.css';
import './setup.css';
import SetupApp from './SetupApp';
const root = document.documentElement;
root.dataset.theme = 'light';
root.dataset.scheme = 'cove';
for (const [key, value] of Object.entries(
  themeTokens(normalizeAppearance({ scheme: 'cove' }), 'light'),
))
  root.style.setProperty('--' + key, value);
createRoot(document.getElementById('root')!).render(<SetupApp />);
