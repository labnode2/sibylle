import { execFileSync } from 'node:child_process';

import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';
import { VitePWA } from 'vite-plugin-pwa';

import { version } from './package.json';

/** The short commit the interface is built from: given by the web image's build, which has no
 *  .git (deploy/nginx/Dockerfile), else read from git; none outside a clone. */
function commit(): string {
  try {
    const sha =
      process.env.SIBYLLE_COMMIT ||
      execFileSync('git', ['rev-parse', 'HEAD'], {
        encoding: 'utf8',
        stdio: ['ignore', 'pipe', 'ignore'],
      });
    return sha.trim().slice(0, 7);
  } catch {
    return '';
  }
}

export default defineConfig({
  define: {
    // « 0.1.0 · aa15cc4 », at the bottom of the sign-in page and of the settings (AppVersion).
    'import.meta.env.SIBYLLE_VERSION': JSON.stringify(
      [version, commit()].filter(Boolean).join(' · '),
    ),
  },
  plugins: [
    react(),
    VitePWA({
      strategies: 'injectManifest',
      srcDir: 'src',
      filename: 'sw.ts',
      injectRegister: false,
      manifest: {
        name: 'Sibylle',
        short_name: 'Sibylle',
        description: 'Le jeu de pronostics des rédactions',
        lang: 'fr',
        start_url: '/',
        display: 'standalone',
        background_color: '#f3f4fa',
        theme_color: '#15162d',
        icons: [
          { src: '/icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: '/icon-512.png', sizes: '512x512', type: 'image/png' },
        ],
      },
      injectManifest: {
        globPatterns: ['**/*.{js,css,html,png,svg,ico,woff2}'],
      },
    }),
  ],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        // `make dev` runs the API on 8000; the end-to-end tests on their own port.
        target: `http://localhost:${process.env.SIBYLLE_API_PORT ?? '8000'}`,
        changeOrigin: false,
        ws: true,
      },
    },
  },
});
