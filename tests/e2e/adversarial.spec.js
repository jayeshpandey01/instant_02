const { test, expect } = require('@playwright/test');

let dockerInstalled = true;
let serverStatus = 'online';
let containers = [
  { name: 'reclip-api', service: 'reclip-api', status: 'Up 2 hours' },
  { name: 'cobalt-api', service: 'cobalt-api', status: 'Up 2 hours' },
  { name: 'cloudflare-tunnel', service: 'cloudflare-tunnel', status: 'Up 2 hours' }
];
let tunnelUrl = 'https://random-tunnel.trycloudflare.com';

let containerStats = [
  { name: 'reclip-api', cpu: '1.2%', memory_usage: '15MiB / 500MiB' },
  { name: 'cobalt-api', cpu: '0.5%', memory_usage: '45MiB / 1GiB' },
  { name: 'cloudflare-tunnel', cpu: '0.1%', memory_usage: '5MiB / 200MiB' }
];
let totalStats = { cpu: '1.8%', memory: '65MiB' };

let usageStats = {
  total_requests: 150,
  successful_requests: 140,
  failed_requests: 10,
  platforms: {
    youtube: 100,
    instagram: 30,
    tiktok: 10,
    twitter: 0
  }
};

let cookieStatus = {
  YOUTUBE_COOKIES: true,
  INSTAGRAM_COOKIES: false,
  TWITTER_COOKIES: false,
  TIKTOK_COOKIES: false
};

let logsOutput = "2026-07-08 10:00:00 [reclip-api] Server started successfully";

test.beforeEach(async ({ page }) => {
  // Reset default state for each test
  dockerInstalled = true;
  serverStatus = 'online';
  containers = [
    { name: 'reclip-api', service: 'reclip-api', status: 'Up 2 hours' },
    { name: 'cobalt-api', service: 'cobalt-api', status: 'Up 2 hours' },
    { name: 'cloudflare-tunnel', service: 'cloudflare-tunnel', status: 'Up 2 hours' }
  ];
  tunnelUrl = 'https://random-tunnel.trycloudflare.com';
  
  containerStats = [
    { name: 'reclip-api', cpu: '1.2%', memory_usage: '15MiB / 500MiB' },
    { name: 'cobalt-api', cpu: '0.5%', memory_usage: '45MiB / 1GiB' },
    { name: 'cloudflare-tunnel', cpu: '0.1%', memory_usage: '5MiB / 200MiB' }
  ];
  totalStats = { cpu: '1.8%', memory: '65MiB' };
  
  usageStats = {
    total_requests: 150,
    successful_requests: 140,
    failed_requests: 10,
    platforms: {
      youtube: 100,
      instagram: 30,
      tiktok: 10,
      twitter: 0
    }
  };
  
  cookieStatus = {
    YOUTUBE_COOKIES: true,
    INSTAGRAM_COOKIES: false,
    TWITTER_COOKIES: false,
    TIKTOK_COOKIES: false
  };
  
  logsOutput = "2026-07-08 10:00:00 [reclip-api] Server started successfully";

  // Default Mocking (Individual tests can override these)
  await page.route('**/api/control/status', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        docker_installed: dockerInstalled,
        status: serverStatus,
        containers: containers,
        tunnel_url: tunnelUrl
      })
    });
  });

  await page.route('**/api/control/stats', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        containers: containerStats,
        totals: totalStats
      })
    });
  });

  await page.route('**/api/control/usage-stats', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(usageStats)
    });
  });

  await page.route('**/api/control/cookie-status', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(cookieStatus)
    });
  });

  await page.route('**/api/control/logs**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ logs: logsOutput })
    });
  });

  await page.route('**/api/control/action', async (route) => {
    if (route.request().method() === 'POST') {
      const payload = JSON.parse(route.request().postData() || '{}');
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ status: 'success', action: payload.action })
      });
    }
  });

  await page.route('**/api/control/cookies', async (route) => {
    if (route.request().method() === 'POST') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ status: 'success' })
      });
    }
  });
});

// ── ADVERSARIAL TESTS ────────────────────────────────────────────────────────

test('Adversarial 1: Status API 500 error graceful degradation', async ({ page }) => {
  // Override status route to fail with 500
  await page.route('**/api/control/status', async (route) => {
    await route.fulfill({
      status: 500,
      contentType: 'application/json',
      body: JSON.stringify({ error: "Internal Database Error", type: "OperationalError" })
    });
  });

  await page.goto('/');
  // UI should load, and not crash. Wait to see if it still renders
  await expect(page.locator('.sidebar')).toBeVisible();
  // Since it failed, systemStatus status won't be online, it will default to 'offline'
  await expect(page.locator('text=Server is Offline')).toBeVisible();
});

test('Adversarial 2: Status API HTML/Invalid JSON response handling', async ({ page }) => {
  // Override status route to return malformed HTML instead of JSON
  await page.route('**/api/control/status', async (route) => {
    await route.fulfill({
      status: 502,
      contentType: 'text/html',
      body: '<html><body>502 Bad Gateway</body></html>'
    });
  });

  await page.goto('/');
  await expect(page.locator('.sidebar')).toBeVisible();
  await expect(page.locator('text=Server is Offline')).toBeVisible();
});

test('Adversarial 3: Rebuild button 5-minute stuck disable state when server remains online', async ({ page }) => {
  // Server is online and stays online
  serverStatus = 'online';
  
  await page.goto('/');
  
  // Verify rebuild button is initially enabled
  const rebuildBtn = page.locator('.btn-rebuild');
  await expect(rebuildBtn).toBeEnabled();
  
  // Click rebuild
  await rebuildBtn.click();
  
  // The action triggers a 5-minute timeout because status doesn't change from online
  await expect(rebuildBtn).toBeDisabled();
  
  // Wait a moment and check if it is still disabled
  await page.waitForTimeout(2000);
  await expect(rebuildBtn).toBeDisabled();
});

test('Adversarial 4: Cookie deletion API error silent failure', async ({ page }) => {
  cookieStatus.YOUTUBE_COOKIES = true;
  
  // Mock DELETE to return 500 with error
  await page.route('**/api/control/cookies/YOUTUBE', async (route) => {
    await route.fulfill({
      status: 500,
      contentType: 'application/json',
      body: JSON.stringify({ error: 'Permission denied deleting cookies' })
    });
  });

  let alertMessage = '';
  page.on('dialog', async (dialog) => {
    if (dialog.type() === 'confirm') {
      await dialog.accept();
    } else if (dialog.type() === 'alert') {
      alertMessage = dialog.message();
      await dialog.accept();
    }
  });

  await page.goto('/');
  await page.locator('button.nav-item', { hasText: 'Settings' }).click();
  
  const row = page.locator('div', { has: page.locator('span', { hasText: 'YOUTUBE' }) });
  await row.locator('button', { hasText: 'Clear' }).click();
  
  // Wait for request and manual refresh
  await page.waitForTimeout(1000);
  
  // BUG EXPOSED: Since handleClearCookie doesn't catch HTTP 500 errors, no alert is shown!
  // The alertMessage will be empty, failing the assertion that the user should be notified.
  expect(alertMessage).toContain('Permission denied');
});

test('Adversarial 5: Log API 500 Error with Flask JSON payload renders empty screen silently', async ({ page }) => {
  // Mock logs API to return 500 with a standard Flask Exception JSON
  await page.route('**/api/control/logs**', async (route) => {
    await route.fulfill({
      status: 500,
      contentType: 'application/json',
      body: JSON.stringify({ error: "Docker daemon down", type: "DockerException" })
    });
  });

  await page.goto('/');
  await page.locator('button.nav-item', { hasText: 'Console Logs' }).click();
  
  // Check the terminal output
  const output = page.locator('.terminal-output');
  await expect(output).toBeVisible();
  
  // BUG EXPOSED: The logs state becomes undefined, which renders nothing.
  // The user should see an error message, but it shows completely blank or default loading.
  const text = await output.textContent();
  expect(text).toContain('Docker daemon down');
});
