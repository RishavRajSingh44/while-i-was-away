import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e', timeout: 60_000, fullyParallel: false, workers: 1,
  use: { baseURL: process.env.AWAY_E2E_URL || 'http://127.0.0.1:8765', viewport: { width: 1440, height: 1050 }, trace: 'retain-on-failure', screenshot: 'only-on-failure', ...(process.env.AWAY_CHROMIUM_PATH ? { launchOptions: { executablePath: process.env.AWAY_CHROMIUM_PATH } } : {}) },
  reporter: [['list']],
});
