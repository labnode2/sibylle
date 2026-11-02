// Fonts are served by Sibylle itself (no third party), Latin character sets only.
import '@fontsource/jacquard-12/latin.css';
import '@fontsource/jacquard-12/latin-ext.css';
import '@fontsource-variable/bricolage-grotesque';
import '@fontsource/geist-mono/latin-400.css';
import '@fontsource/geist-mono/latin-500.css';
import '@fontsource/geist-mono/latin-600.css';
import '@fontsource/geist-mono/latin-700.css';
import '@fontsource/geist-mono/latin-ext-400.css';
import '@fontsource/geist-mono/latin-ext-700.css';
import './styles/tokens.css';
import './styles/gazette.css';
import './styles/backgrounds.css';
import './i18n';

import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { RouterProvider } from 'react-router/dom';

import { Providers } from './app/providers';
import { router } from './app/router';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Providers>
      <RouterProvider router={router} />
    </Providers>
  </StrictMode>,
);

if (import.meta.env.PROD) {
  void import('virtual:pwa-register').then(({ registerSW }) => registerSW({ immediate: true }));
}
