import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import { initializeAppearance } from './core/useAppearance';
import { initializeLocale } from './core/i18n.ts';
import './styles/typography.css';
import './styles/foundation.css';
import './styles/components.css';
import './styles/shell.css';
import './styles/views.css';
import './styles/appearance.css';
import './styles/motion.css';
import './styles/workbench.css';
initializeAppearance();
initializeLocale();
createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
