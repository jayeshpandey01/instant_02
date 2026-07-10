const { defineConfig, devices } = require('@playwright/test');
module.exports = defineConfig({
  testDir: './tests/e2e',
  timeout: 30000,
  expect: { timeout: 5000 },
  fullyParallel: false,
  workers: 1,
  reporter: 'list',
  use: {
    baseURL: 'http://localhost:8899',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: {
    command: 'venv\\Scripts\\python app.py',
    url: 'http://localhost:8899',
    reuseExistingServer: false,
    timeout: 15000,
  },
});
