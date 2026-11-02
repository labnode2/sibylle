import { defineConfig, devices } from '@playwright/test';

// The API runs with the simulated clock; tests move time with `sibylle clock …` and run the
// worker's jobs on demand with `sibylle jobs run …`, so no worker process is started here.
const backend = '../backend';
// SIBYLLE_WEB_PORT moves the interface when 5173 is taken by another project.
const webPort = process.env.SIBYLLE_WEB_PORT ?? '5173';
const web = `http://localhost:${webPort}`;

export default defineConfig({
  testDir: 'tests/e2e',
  fullyParallel: false,
  workers: 1,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: web,
    locale: 'fr-FR',
    timezoneId: 'Europe/Paris',
    trace: 'retain-on-failure',
  },
  projects: [
    { name: 'mobile', use: { ...devices['Pixel 7'] } },
    {
      name: 'desktop',
      use: { ...devices['Desktop Chrome'], viewport: { width: 1280, height: 800 } },
    },
  ],
  webServer: [
    {
      command: `uv run --directory ${backend} uvicorn sibylle.main:create_app --factory --port 8000`,
      url: 'http://localhost:8000/api/health',
      env: { SIBYLLE_CLOCK: 'fake', ENVIRONMENT: 'test', PUBLIC_ORIGIN: web },
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
    {
      command: `npm run dev -- --port ${webPort} --strictPort`,
      url: web,
      reuseExistingServer: !process.env.CI,
    },
  ],
});
