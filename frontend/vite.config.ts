import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';
import { VitePWA } from 'vite-plugin-pwa';

export default defineConfig({
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
