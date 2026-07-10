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

let logsOutput = "2026-07-08 10:00:00 [reclip-api] Server started successfully\n2026-07-08 10:00:01 [cobalt-api] Cobalt listening on port 3000\n2026-07-08 10:00:02 [cloudflare-tunnel] Tunnel established at https://random-tunnel.trycloudflare.com";

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
  
  logsOutput = "2026-07-08 10:00:00 [reclip-api] Server started successfully\n2026-07-08 10:00:01 [cobalt-api] Cobalt listening on port 3000\n2026-07-08 10:00:02 [cloudflare-tunnel] Tunnel established at https://random-tunnel.trycloudflare.com";

  // Mock /api/control/status
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

  // Mock /api/control/stats
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

  // Mock /api/control/usage-stats
  await page.route('**/api/control/usage-stats', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(usageStats)
    });
  });

  // Mock /api/control/cookie-status
  await page.route('**/api/control/cookie-status', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(cookieStatus)
    });
  });

  // Mock /api/control/logs
  await page.route('**/api/control/logs**', async (route) => {
    const url = route.request().url();
    let responseLogs = logsOutput;
    if (url.includes('service=reclip-api')) {
      responseLogs = "[reclip-api] Service specific log entry";
    } else if (url.includes('service=cobalt-api')) {
      responseLogs = "[cobalt-api] Service specific log entry";
    } else if (url.includes('service=cloudflare-tunnel')) {
      responseLogs = "[cloudflare-tunnel] Service specific log entry";
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ logs: responseLogs })
    });
  });

  // Mock /api/control/action
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

  // Mock /api/control/cookies
  await page.route('**/api/control/cookies', async (route) => {
    if (route.request().method() === 'POST') {
      const payload = JSON.parse(route.request().postData() || '{}');
      cookieStatus[`${payload.service}_COOKIES`] = true;
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ status: 'success' })
      });
    }
  });

  // Mock /api/control/cookies/*
  await page.route(/\/api\/control\/cookies\/([A-Z_]+)/, async (route) => {
    if (route.request().method() === 'DELETE') {
      const match = route.request().url().match(/\/api\/control\/cookies\/([A-Z_]+)/);
      if (match) {
        cookieStatus[`${match[1]}_COOKIES`] = false;
      }
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ status: 'success' })
      });
    }
  });
});

// ── TIER 1: Feature Coverage (tests 1-20) ────────────────────────────────────

test('1. Loads utilization tab by default', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('.topbar-title')).toContainText('Utilization');
});

test('2. Switches to settings tab', async ({ page }) => {
  await page.goto('/');
  await page.locator('button.nav-item', { hasText: 'Settings' }).click();
  await expect(page.locator('.topbar-title')).toContainText('Settings');
});

test('3. Switches to console logs tab', async ({ page }) => {
  await page.goto('/');
  await page.locator('button.nav-item', { hasText: 'Console Logs' }).click();
  await expect(page.locator('.topbar-title')).toContainText('Console Logs');
});

test('4. Switches to api docs tab', async ({ page }) => {
  await page.goto('/');
  await page.locator('button.nav-item', { hasText: 'API Docs' }).click();
  await expect(page.locator('.topbar-title')).toContainText('API Docs');
});

test('5. Version check in footer', async ({ page }) => {
  await page.goto('/');
  const footer = page.locator('.sidebar-footer');
  await expect(footer).toContainText('v11.7.1');
});

test('6. Start button triggers API', async ({ page }) => {
  let triggered = false;
  await page.route('**/api/control/action', async (route) => {
    const payload = JSON.parse(route.request().postData() || '{}');
    if (payload.action === 'start') {
      triggered = true;
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ status: 'success' })
    });
  });
  await page.goto('/');
  await page.locator('.btn-start', { hasText: 'Start' }).click();
  expect(triggered).toBe(true);
});

test('7. Stop button triggers API', async ({ page }) => {
  let triggered = false;
  await page.route('**/api/control/action', async (route) => {
    const payload = JSON.parse(route.request().postData() || '{}');
    if (payload.action === 'stop') {
      triggered = true;
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ status: 'success' })
    });
  });
  await page.goto('/');
  await page.locator('.btn-stop').click();
  expect(triggered).toBe(true);
});

test('8. Rebuild button triggers API', async ({ page }) => {
  let triggered = false;
  await page.route('**/api/control/action', async (route) => {
    const payload = JSON.parse(route.request().postData() || '{}');
    if (payload.action === 'rebuild') {
      triggered = true;
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ status: 'success' })
    });
  });
  await page.goto('/');
  await page.locator('.btn-rebuild').click();
  expect(triggered).toBe(true);
});

test('9. Action loading disables buttons', async ({ page }) => {
  await page.route('**/api/control/action', async (route) => {
    // Keep it pending
  });
  await page.goto('/');
  await page.locator('.btn-start', { hasText: 'Start' }).click();
  await expect(page.locator('.btn-start', { hasText: 'Start' })).toBeDisabled();
  await expect(page.locator('.btn-stop')).toBeDisabled();
  await expect(page.locator('.btn-rebuild')).toBeDisabled();
});

test('10. Shows offline banner if server status is offline', async ({ page }) => {
  serverStatus = 'offline';
  await page.goto('/');
  await expect(page.locator('text=Server is Offline')).toBeVisible();
});

test('11. Setup youtube cookie', async ({ page }) => {
  cookieStatus.YOUTUBE_COOKIES = false;
  let postPayload = null;
  await page.route('**/api/control/cookies', async (route) => {
    postPayload = JSON.parse(route.request().postData() || '{}');
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ status: 'success' })
    });
  });
  await page.goto('/');
  await page.locator('button.nav-item', { hasText: 'Settings' }).click();
  const row = page.locator('div', { has: page.locator('span', { hasText: 'YOUTUBE' }) });
  await row.locator('button', { hasText: 'Setup' }).click();
  await row.locator('textarea').fill('youtube_cookie_data');
  await row.locator('button', { hasText: 'Save' }).click();
  expect(postPayload).toEqual({ service: 'YOUTUBE', cookies: 'youtube_cookie_data' });
});

test('12. Clear youtube cookie', async ({ page }) => {
  cookieStatus.YOUTUBE_COOKIES = true;
  let deleteCalled = false;
  await page.route('**/api/control/cookies/YOUTUBE', async (route) => {
    if (route.request().method() === 'DELETE') {
      deleteCalled = true;
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ status: 'success' })
      });
    }
  });
  page.on('dialog', async (dialog) => {
    await dialog.accept();
  });
  await page.goto('/');
  await page.locator('button.nav-item', { hasText: 'Settings' }).click();
  const row = page.locator('div', { has: page.locator('span', { hasText: 'YOUTUBE' }) });
  await row.locator('button', { hasText: 'Clear' }).click();
  expect(deleteCalled).toBe(true);
});

test('13. Verify status badges for configured', async ({ page }) => {
  cookieStatus.YOUTUBE_COOKIES = true;
  await page.goto('/');
  await page.locator('button.nav-item', { hasText: 'Settings' }).click();
  const row = page.locator('div', { has: page.locator('span', { hasText: 'YOUTUBE' }) });
  await expect(row.locator('text=✓ Configured')).toBeVisible();
});

test('14. Verify status badges for not set', async ({ page }) => {
  cookieStatus.INSTAGRAM_COOKIES = false;
  await page.goto('/');
  await page.locator('button.nav-item', { hasText: 'Settings' }).click();
  const row = page.locator('div', { has: page.locator('span', { hasText: 'INSTAGRAM' }) });
  await expect(row.locator('text=Not Set')).toBeVisible();
});

test('15. Setup dialog textarea placeholder check', async ({ page }) => {
  cookieStatus.INSTAGRAM_COOKIES = false;
  await page.goto('/');
  await page.locator('button.nav-item', { hasText: 'Settings' }).click();
  const row = page.locator('div', { has: page.locator('span', { hasText: 'INSTAGRAM' }) });
  await row.locator('button', { hasText: 'Setup' }).click();
  const placeholder = await row.locator('textarea').getAttribute('placeholder');
  expect(placeholder).toBe('Paste raw HTTP Cookie header or Netscape cookies for INSTAGRAM...');
});

test('16. Logs tab shows default all logs', async ({ page }) => {
  await page.goto('/');
  await page.locator('button.nav-item', { hasText: 'Console Logs' }).click();
  const logsText = await page.locator('.terminal-output').textContent();
  expect(logsText).toContain('Server started successfully');
});

test('17. Log filter reclip-api triggers service API', async ({ page }) => {
  let serviceParam = null;
  await page.route('**/api/control/logs**', async (route) => {
    const url = route.request().url();
    const urlObj = new URL(url);
    serviceParam = urlObj.searchParams.get('service');
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ logs: `[reclip-api] logs` })
    });
  });
  await page.goto('/');
  await page.locator('button.nav-item', { hasText: 'Console Logs' }).click();
  await page.locator('.log-filter-btn', { hasText: 'reclip-api' }).click();
  expect(serviceParam).toBe('reclip-api');
});

test('18. Log filter cobalt-api triggers service API', async ({ page }) => {
  let serviceParam = null;
  await page.route('**/api/control/logs**', async (route) => {
    const url = route.request().url();
    const urlObj = new URL(url);
    serviceParam = urlObj.searchParams.get('service');
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ logs: `[cobalt-api] logs` })
    });
  });
  await page.goto('/');
  await page.locator('button.nav-item', { hasText: 'Console Logs' }).click();
  await page.locator('.log-filter-btn', { hasText: 'cobalt-api' }).click();
  expect(serviceParam).toBe('cobalt-api');
});

test('19. Log filter cloudflare-tunnel triggers service API', async ({ page }) => {
  let serviceParam = null;
  await page.route('**/api/control/logs**', async (route) => {
    const url = route.request().url();
    const urlObj = new URL(url);
    serviceParam = urlObj.searchParams.get('service');
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ logs: `[cloudflare-tunnel] logs` })
    });
  });
  await page.goto('/');
  await page.locator('button.nav-item', { hasText: 'Console Logs' }).click();
  await page.locator('.log-filter-btn', { hasText: 'cloudflare-tunnel' }).click();
  expect(serviceParam).toBe('cloudflare-tunnel');
});

test('20. API Docs renders /api/download, /api/cobalt, and /api/cookie-files', async ({ page }) => {
  await page.goto('/');
  await page.locator('button.nav-item', { hasText: 'API Docs' }).click();
  await expect(page.locator('text=/api/download')).toBeVisible();
  await expect(page.locator('text=/api/cobalt')).toBeVisible();
  await expect(page.locator('text=/api/cookie-files')).toBeVisible();
});

// ── TIER 2: Boundary & Corner Cases (tests 21-40) ────────────────────────────

test('21. Missing docker installation hides main dashboard and shows docker required panel', async ({ page }) => {
  dockerInstalled = false;
  await page.goto('/');
  await expect(page.locator('text=Docker Desktop Required')).toBeVisible();
  await expect(page.locator('.topbar-actions button')).toBeDisabled();
});

test('22. API Docs code block null check', async ({ page }) => {
  await page.goto('/');
  await page.locator('button.nav-item', { hasText: 'API Docs' }).click();
  const section = page.locator('div', { has: page.locator('span', { hasText: '/api/cookie-files' }) });
  await expect(section.locator('.api-code')).toHaveCount(0);
  const dlSection = page.locator('div', { has: page.locator('span', { hasText: '/api/download' }) });
  await expect(dlSection.locator('.api-code')).toHaveCount(1);
});

test("23. Long labels in navigation doesn't break style", async ({ page }) => {
  await page.goto('/');
  const navItem = page.locator('button.nav-item').first();
  const display = await navItem.evaluate((el) => window.getComputedStyle(el).display);
  expect(display).toBe('flex');
});

test('24. Resizing handles page styling correctly', async ({ page }) => {
  await page.goto('/');
  await page.setViewportSize({ width: 375, height: 667 });
  const bodyWidth = await page.evaluate(() => document.body.clientWidth);
  expect(bodyWidth).toBe(375);
});

test("25. Double click active tab doesn't change active view", async ({ page }) => {
  await page.goto('/');
  const topbar = page.locator('.topbar-title');
  await expect(topbar).toContainText('Utilization');
  const navUtil = page.locator('button.nav-item', { hasText: 'Utilization' });
  await navUtil.dblclick();
  await expect(topbar).toContainText('Utilization');
});

test('26. Server action API error handles gracefully', async ({ page }) => {
  await page.route('**/api/control/action', async (route) => {
    await route.fulfill({
      status: 500,
      contentType: 'application/json',
      body: JSON.stringify({ error: 'Docker failed' })
    });
  });
  let alertMsg = '';
  page.on('dialog', async (dialog) => {
    alertMsg = dialog.message();
    await dialog.accept();
  });
  await page.goto('/');
  await page.locator('.btn-start', { hasText: 'Start' }).click();
  expect(alertMsg).toContain('Action failed: Error: Server error: 500');
});

test('27. Start action timeout disables buttons for timeout period', async ({ page }) => {
  await page.goto('/');
  await page.locator('.btn-start', { hasText: 'Start' }).click();
  await expect(page.locator('.btn-start', { hasText: 'Start' })).toBeDisabled();
});

test('28. Stop action timeout resets after 5s', async ({ page }) => {
  await page.goto('/');
  await page.locator('.btn-stop').click();
  await expect(page.locator('.btn-stop')).toBeDisabled();
  await page.waitForTimeout(6000);
  await expect(page.locator('.btn-stop')).toBeEnabled();
});

test('29. Partially running container statuses show correct badge styles', async ({ page }) => {
  containers = [
    { name: 'reclip-api', service: 'reclip-api', status: 'Running' },
    { name: 'cobalt-api', service: 'cobalt-api', status: 'Exited (1)' }
  ];
  await page.goto('/');
  const rowUp = page.locator('div', { has: page.locator('span', { hasText: 'reclip-api' }) });
  await expect(rowUp.locator('.badge-up')).toBeVisible();
  const rowDown = page.locator('div', { has: page.locator('span', { hasText: 'cobalt-api' }) });
  await expect(rowDown.locator('.badge-down')).toBeVisible();
});

test('30. Rebuild action shows spinner', async ({ page }) => {
  await page.route('**/api/control/action', async (route) => {
    // delay
  });
  await page.goto('/');
  await page.locator('.btn-rebuild').click();
  await expect(page.locator('.btn-rebuild svg')).toHaveClass(/spin/);
});

test('31. Empty cookie submit button disabled', async ({ page }) => {
  cookieStatus.YOUTUBE_COOKIES = false;
  await page.goto('/');
  await page.locator('button.nav-item', { hasText: 'Settings' }).click();
  const row = page.locator('div', { has: page.locator('span', { hasText: 'YOUTUBE' }) });
  await row.locator('button', { hasText: 'Setup' }).click();
  await expect(row.locator('button', { hasText: 'Save' })).toBeDisabled();
});

test('32. Save cookie API error shows alert', async ({ page }) => {
  cookieStatus.YOUTUBE_COOKIES = false;
  await page.route('**/api/control/cookies', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ status: 'error', error: 'Failed to write cookies' })
    });
  });
  let alertMsg = '';
  page.on('dialog', async (dialog) => {
    alertMsg = dialog.message();
    await dialog.accept();
  });
  await page.goto('/');
  await page.locator('button.nav-item', { hasText: 'Settings' }).click();
  const row = page.locator('div', { has: page.locator('span', { hasText: 'YOUTUBE' }) });
  await row.locator('button', { hasText: 'Setup' }).click();
  await row.locator('textarea').fill('test');
  await row.locator('button', { hasText: 'Save' }).click();
  expect(alertMsg).toBe('Failed to write cookies');
});

test('33. Delete cookie API error shows alert', async ({ page }) => {
  cookieStatus.YOUTUBE_COOKIES = true;
  await page.route('**/api/control/cookies/YOUTUBE', async (route) => {
    await route.fulfill({
      status: 500,
      body: 'Error deleting'
    });
  });
  let alertMsg = '';
  page.on('dialog', async (dialog) => {
    if (dialog.type() === 'confirm') {
      await dialog.accept();
    } else if (dialog.type() === 'alert') {
      alertMsg = dialog.message();
      await dialog.accept();
    }
  });
  await page.goto('/');
  await page.locator('button.nav-item', { hasText: 'Settings' }).click();
  const row = page.locator('div', { has: page.locator('span', { hasText: 'YOUTUBE' }) });
  await row.locator('button', { hasText: 'Clear' }).click();
  expect(alertMsg).toContain('Error:');
});

test('34. Try to setup another cookie closes active setup', async ({ page }) => {
  cookieStatus.YOUTUBE_COOKIES = false;
  cookieStatus.INSTAGRAM_COOKIES = false;
  await page.goto('/');
  await page.locator('button.nav-item', { hasText: 'Settings' }).click();
  const rowYT = page.locator('div', { has: page.locator('span', { hasText: 'YOUTUBE' }) });
  const rowIG = page.locator('div', { has: page.locator('span', { hasText: 'INSTAGRAM' }) });
  await rowYT.locator('button', { hasText: 'Setup' }).click();
  await expect(rowYT.locator('textarea')).toBeVisible();
  await rowIG.locator('button', { hasText: 'Setup' }).click();
  await expect(rowYT.locator('textarea')).toHaveCount(0);
  await expect(rowIG.locator('textarea')).toBeVisible();
});

test('35. Click cancel hides setup area', async ({ page }) => {
  cookieStatus.YOUTUBE_COOKIES = false;
  await page.goto('/');
  await page.locator('button.nav-item', { hasText: 'Settings' }).click();
  const row = page.locator('div', { has: page.locator('span', { hasText: 'YOUTUBE' }) });
  await row.locator('button', { hasText: 'Setup' }).click();
  await expect(row.locator('textarea')).toBeVisible();
  await row.locator('button', { hasText: 'Cancel' }).click();
  await expect(row.locator('textarea')).toHaveCount(0);
});

test('36. Logs API error shows failure message', async ({ page }) => {
  await page.route('**/api/control/logs', async (route) => {
    await route.fulfill({ status: 500 });
  });
  await page.goto('/');
  await page.locator('button.nav-item', { hasText: 'Console Logs' }).click();
  await expect(page.locator('.terminal-output')).toContainText('Failed to fetch logs:');
});

test('37. Logs API empty response handles correctly', async ({ page }) => {
  logsOutput = '';
  await page.goto('/');
  await page.locator('button.nav-item', { hasText: 'Console Logs' }).click();
  const text = await page.locator('.terminal-output').textContent();
  expect(text).toBe('');
});

test('38. Rapidly click logs filters handles last request correctly', async ({ page }) => {
  await page.goto('/');
  await page.locator('button.nav-item', { hasText: 'Console Logs' }).click();
  await page.locator('.log-filter-btn', { hasText: 'reclip-api' }).click();
  await page.locator('.log-filter-btn', { hasText: 'cobalt-api' }).click();
  await page.locator('.log-filter-btn', { hasText: 'cloudflare-tunnel' }).click();
  await expect(page.locator('.terminal-output')).toContainText('[cloudflare-tunnel] Service specific log entry');
});

test('39. Extremely large logs input rendering check', async ({ page }) => {
  logsOutput = "A".repeat(100000);
  await page.goto('/');
  await page.locator('button.nav-item', { hasText: 'Console Logs' }).click();
  const text = await page.locator('.terminal-output').textContent();
  expect(text.length).toBe(100000);
});

test('40. Check that logs poll every 3 seconds', async ({ page }) => {
  let callCount = 0;
  await page.route('**/api/control/logs', async (route) => {
    callCount++;
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ logs: `Poll ${callCount}` })
    });
  });
  await page.goto('/');
  await page.locator('button.nav-item', { hasText: 'Console Logs' }).click();
  await page.waitForTimeout(3500);
  expect(callCount).toBeGreaterThan(1);
});

// ── TIER 3: Cross-Feature Combinations (tests 41-44) ─────────────────────────

test('41. Configure cookie while server is offline, then check utilization tab status', async ({ page }) => {
  serverStatus = 'offline';
  cookieStatus.YOUTUBE_COOKIES = false;
  await page.goto('/');
  await expect(page.locator('text=Server is Offline')).toBeVisible();
  
  await page.locator('button.nav-item', { hasText: 'Settings' }).click();
  const row = page.locator('div', { has: page.locator('span', { hasText: 'YOUTUBE' }) });
  await row.locator('button', { hasText: 'Setup' }).click();
  await row.locator('textarea').fill('offline_setup');
  await row.locator('button', { hasText: 'Save' }).click();
  
  await page.locator('button.nav-item', { hasText: 'Utilization' }).click();
  await expect(page.locator('text=Server is Offline')).toBeVisible();
  
  await page.locator('button.nav-item', { hasText: 'Settings' }).click();
  await expect(row.locator('text=✓ Configured')).toBeVisible();
});

test('42. Start server, verify tunnel banner, copy url, stop server, verify tunnel banner disappears', async ({ page }) => {
  serverStatus = 'offline';
  tunnelUrl = null;
  await page.goto('/');
  await expect(page.locator('text=Server is Offline')).toBeVisible();
  
  await page.route('**/api/control/action', async (route) => {
    const payload = JSON.parse(route.request().postData() || '{}');
    if (payload.action === 'start') {
      serverStatus = 'online';
      tunnelUrl = 'https://live-test.trycloudflare.com';
    } else if (payload.action === 'stop') {
      serverStatus = 'offline';
      tunnelUrl = null;
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ status: 'success' })
    });
  });

  await page.locator('.btn-start', { hasText: 'Set up & Start Server' }).click();
  await page.waitForTimeout(3500);
  await expect(page.locator('.tunnel-banner')).toBeVisible();
  await expect(page.locator('.tunnel-banner')).toContainText('https://live-test.trycloudflare.com');
  
  await page.locator('.tunnel-banner button:has-text("Copy URL")').click();
  await expect(page.locator('.tunnel-banner button')).toContainText('Copied!');

  await page.locator('.btn-stop').click();
  await page.waitForTimeout(3500);
  await expect(page.locator('.tunnel-banner')).toHaveCount(0);
  await expect(page.locator('text=Server is Offline')).toBeVisible();
});

test('43. Navigate to logs tab while start action is loading', async ({ page }) => {
  await page.route('**/api/control/action', async (route) => {
    // pending
  });
  await page.goto('/');
  await page.locator('.btn-start', { hasText: 'Start' }).click();
  await expect(page.locator('.btn-start', { hasText: 'Start' })).toBeDisabled();
  
  await page.locator('button.nav-item', { hasText: 'Console Logs' }).click();
  await expect(page.locator('.topbar-title')).toContainText('Console Logs');
  
  await page.locator('button.nav-item', { hasText: 'Utilization' }).click();
  await expect(page.locator('.btn-start', { hasText: 'Start' })).toBeDisabled();
});

test('44. Dynamic change of docker installed state from true to false triggers immediate redirect', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('text=Docker Desktop Required')).toHaveCount(0);
  
  dockerInstalled = false;
  await page.waitForTimeout(3500);
  await expect(page.locator('text=Docker Desktop Required')).toBeVisible();
});

// ── TIER 4: Real-World Scenarios (tests 45-49) ───────────────────────────────

test('45. Scenario 1: Initial Setup workflow (offline -> add cookie -> start server -> online with tunnel banner)', async ({ page }) => {
  serverStatus = 'offline';
  tunnelUrl = null;
  cookieStatus.YOUTUBE_COOKIES = false;

  await page.route('**/api/control/action', async (route) => {
    serverStatus = 'online';
    tunnelUrl = 'https://workflow-tunnel.trycloudflare.com';
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ status: 'success' })
    });
  });

  await page.goto('/');
  await expect(page.locator('text=Server is Offline')).toBeVisible();
  
  await page.locator('button.nav-item', { hasText: 'Settings' }).click();
  const row = page.locator('div', { has: page.locator('span', { hasText: 'YOUTUBE' }) });
  await row.locator('button', { hasText: 'Setup' }).click();
  await row.locator('textarea').fill('youtube_cookie_val');
  await row.locator('button', { hasText: 'Save' }).click();
  await expect(row.locator('text=✓ Configured')).toBeVisible();

  await page.locator('button.nav-item', { hasText: 'Utilization' }).click();
  await page.locator('.btn-start', { hasText: 'Set up & Start Server' }).click();
  
  await page.waitForTimeout(3500);
  await expect(page.locator('.tunnel-banner')).toBeVisible();
  await expect(page.locator('.tunnel-banner')).toContainText('https://workflow-tunnel.trycloudflare.com');
});

test('46. Scenario 2: Active Monitoring workflow (verify container table stats, usage stats platforms charts, log view, force refresh)', async ({ page }) => {
  let statsCalled = 0;
  await page.route('**/api/control/stats', async (route) => {
    statsCalled++;
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        containers: containerStats,
        totals: totalStats
      })
    });
  });

  await page.goto('/');
  const row = page.locator('div', { has: page.locator('span', { hasText: 'reclip-api' }) });
  await expect(row.locator('text=1.2%')).toBeVisible();
  await expect(row.locator('text=15MiB / 500MiB')).toBeVisible();

  await page.locator('.tab-btn', { hasText: 'Metrics' }).click();
  await expect(page.locator('text=youtube')).toBeVisible();

  await page.locator('button.nav-item', { hasText: 'Console Logs' }).click();
  await expect(page.locator('.terminal-output')).toContainText('Server started successfully');

  await page.locator('button.nav-item', { hasText: 'Utilization' }).click();
  const beforeClick = statsCalled;
  await page.locator('.updated button').click();
  await page.waitForTimeout(100);
  expect(statsCalled).toBeGreaterThan(beforeClick);
});

test('47. Scenario 3: Error Recovery workflow (failed start -> inspect logs -> go settings clear cookie -> restart)', async ({ page }) => {
  serverStatus = 'offline';
  let tryStart = 0;
  
  await page.route('**/api/control/action', async (route) => {
    const payload = JSON.parse(route.request().postData() || '{}');
    if (payload.action === 'start') {
      tryStart++;
      if (tryStart === 1) {
        await route.fulfill({
          status: 500,
          body: 'Failed to start containers'
        });
      } else {
        serverStatus = 'online';
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ status: 'success' })
        });
      }
    }
  });

  let alertMessage = '';
  page.on('dialog', async (dialog) => {
    if (dialog.type() === 'confirm') {
      await dialog.accept();
    } else {
      alertMessage = dialog.message();
      await dialog.accept();
    }
  });

  await page.goto('/');
  await page.locator('.btn-start', { hasText: 'Set up & Start Server' }).click();
  await page.waitForTimeout(100);
  expect(alertMessage).toContain('Action failed:');

  await page.locator('button.nav-item', { hasText: 'Console Logs' }).click();
  await expect(page.locator('.terminal-output')).toBeVisible();

  cookieStatus.YOUTUBE_COOKIES = true;
  await page.locator('button.nav-item', { hasText: 'Settings' }).click();
  const row = page.locator('div', { has: page.locator('span', { hasText: 'YOUTUBE' }) });
  await row.locator('button', { hasText: 'Clear' }).click();
  await expect(row.locator('text=Not Set')).toBeVisible();

  await page.locator('button.nav-item', { hasText: 'Utilization' }).click();
  await page.locator('.btn-start', { hasText: 'Set up & Start Server' }).click();
  await page.waitForTimeout(3500);
  await expect(page.locator('text=Server is Offline')).toHaveCount(0);
});

test('48. Scenario 4: Copy & External Access workflow (copy tunnel URL, check api docs parameters)', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('.tunnel-banner')).toBeVisible();
  await page.locator('.tunnel-banner button:has-text("Copy URL")').click();
  await expect(page.locator('.tunnel-banner button')).toContainText('Copied!');

  await page.locator('button.nav-item', { hasText: 'API Docs' }).click();
  const section = page.locator('div', { has: page.locator('span', { hasText: '/api/download' }) });
  await expect(section.locator('.api-code')).toContainText('?url=https://www.youtube.com/watch?v=...');
});

test('49. Scenario 5: Unlock Dashboard workflow (starts without docker -> shows required page -> docker service starts -> dashboard unlocks)', async ({ page }) => {
  dockerInstalled = false;
  await page.goto('/');
  await expect(page.locator('text=Docker Desktop Required')).toBeVisible();

  dockerInstalled = true;
  await page.waitForTimeout(3500);
  await expect(page.locator('text=Docker Desktop Required')).toHaveCount(0);
  await expect(page.locator('.topbar-actions button')).toBeEnabled();
});
