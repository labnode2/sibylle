import { defineConfig, devices } from '@playwright/test';

// The API runs with the simulated clock; tests move time with `sibylle clock …` and run the
// worker's jobs on demand with `sibylle jobs run …`, so no worker process is started here.
const backend = '../backend';
// The tests get their own ports, so that they never run against a `make dev` left open (its
// real clock, its rate limits): the API on 8001, the interface on 5180. SIBYLLE_API_PORT and
// SIBYLLE_WEB_PORT move them.
const apiPort = process.env.SIBYLLE_API_PORT ?? '8001';
const webPort = process.env.SIBYLLE_WEB_PORT ?? '5180';
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
      command: `uv run --directory ${backend} uvicorn sibylle.main:create_app --factory --port ${apiPort}`,
      url: `http://localhost:${apiPort}/api/health`,
      env: { SIBYLLE_CLOCK: 'fake', ENVIRONMENT: 'test', PUBLIC_ORIGIN: web },
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
    {
      command: `npm run dev -- --port ${webPort} --strictPort`,
      url: web,
      env: { SIBYLLE_API_PORT: apiPort },
      reuseExistingServer: !process.env.CI,
    },
  ],
});
