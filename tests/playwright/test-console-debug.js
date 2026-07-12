const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: false, slowMo: 300 });
  const page = await browser.newPage();

  // Capture ALL console messages
  page.on('console', msg => {
    const type = msg.type();
    const text = msg.text();
    console.log(`[CONSOLE-${type}] ${text}`);
  });

  page.on('pageerror', err => {
    console.error(`[PAGE ERROR] ${err.message}`);
  });

  // Monitor API calls
  page.on('request', req => {
    if (req.url().includes('/api/')) {
      console.log(`[NET] ${req.method()} ${req.url()}`);
    }
  });

  // Block production API
  await page.route('**/api/v1/production/**', route => {
    route.fulfill({ status: 200, body: '[]', contentType: 'application/json' });
  });

  try {
    console.log('=== Starting test ===\n');

    console.log('1. Login...');
    await page.goto('http://localhost:5174');
    await page.waitForTimeout(2000);
    await page.fill('input[placeholder*="用户名"]', 'admin');
    await page.fill('input[type="password"]', '123456');
    await page.click('button:has-text("登录")');
    await page.waitForTimeout(3000);

    console.log('\n2. Go to treatments page...');
    await page.goto('http://localhost:5174/#/price-management/treatments');
    await page.waitForTimeout(10000);  // Wait longer

    console.log('\n3. Page analysis...');
    const pageText = await page.textContent('body');
    console.log(`   Body contains "Treatment": ${pageText.includes('Treatment')}`);
    console.log(`   Body contains "Add": ${pageText.includes('Add')}`);

    const rows = await page.locator('table tbody tr').count();
    console.log(`   Rows: ${rows}`);

    await page.screenshot({ path: 'screenshots/console-debug.png', fullPage: true });

    await page.waitForTimeout(10000);

  } catch (error) {
    console.error('Error:', error);
  } finally {
    await browser.close();
  }
})();
