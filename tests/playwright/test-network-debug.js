const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: false, slowMo: 300 });
  const page = await browser.newPage();

  // Monitor all network requests
  const requests = [];
  page.on('request', req => {
    if (req.url().includes('treatments') || req.url().includes('production')) {
      requests.push({
        url: req.url(),
        method: req.method(),
        headers: req.headers()
      });
      console.log(`[REQUEST] ${req.method()} ${req.url()}`);
    }
  });

  page.on('response', async res => {
    if (res.url().includes('treatments')) {
      console.log(`[RESPONSE] ${res.status()} ${res.url()}`);
      try {
        const body = await res.text();
        console.log(`[BODY] ${body.substring(0, 200)}...`);
      } catch (e) {}
    }
  });

  // Block production API
  await page.route('**/api/v1/production/**', route => {
    route.fulfill({ status: 200, body: '[]', contentType: 'application/json' });
  });

  console.log('=== Network monitoring active ===\n');

  try {
    console.log('1. Login...');
    await page.goto('http://localhost:5174');
    await page.waitForTimeout(2000);
    await page.fill('input[placeholder*="用户名"]', 'admin');
    await page.fill('input[type="password"]', '123456');
    await page.click('button:has-text("登录")');
    await page.waitForTimeout(3000);

    console.log('\n2. Navigate to treatments...');
    await page.goto('http://localhost:5174/#/price-management/treatments');
    await page.waitForTimeout(7000);

    console.log('\n3. Check page state...');
    const rows = await page.locator('table tbody tr').count();
    console.log(`   Table rows: ${rows}`);

    const hasH2 = await page.locator('h2:has-text("Treatment")').count();
    console.log(`   Has H2: ${hasH2}`);

    console.log('\n4. All requests to treatments API:');
    requests.forEach(r => {
      if (r.url.includes('treatments')) {
        console.log(`   ${r.method} ${r.url}`);
        console.log(`   Auth: ${r.headers.authorization ? '✓' : '✗'}`);
      }
    });

    await page.screenshot({ path: 'screenshots/network-debug.png', fullPage: true });
    console.log('\n✅ Screenshot saved');

    await page.waitForTimeout(10000);

  } catch (error) {
    console.error('Error:', error.message);
  } finally {
    await browser.close();
  }
})();
