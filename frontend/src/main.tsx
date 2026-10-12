import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import { App } from '@/app/App';
import '@/i18n';
import { registerServiceWorker } from '@/lib/pwa';
import '@/styles/index.css';

const root = document.getElementById('root');
if (!root) throw new Error('Root element #root not found');

registerServiceWorker();

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
