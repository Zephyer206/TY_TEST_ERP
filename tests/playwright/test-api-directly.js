const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: false, slowMo: 500 });
  const page = await browser.newPage();

  console.log('=== Testing Treatments API directly ===');

  // Enable detailed console logging
  page.on('console', msg => {
    const type = msg.type();
    const text = msg.text();
    console.log(`[${type}] ${text}`);
  });

  page.on('pageerror', err => console.error('[PAGE ERROR]', err.message));
  page.on('requestfailed', req => console.error('[REQUEST FAILED]', req.url(), req.failure().errorText));

  try {
    // Test API directly
    console.log('\n1. Testing API endpoint directly...');
    const apiResponse = await page.request.get('http://localhost:8000/api/v1/treatments');
    console.log(`   Status: ${apiResponse.status()}`);

    if (apiResponse.ok()) {
      const data = await apiResponse.json();
      console.log(`   Data count: ${data.length}`);
      console.log(`   First item: ${JSON.stringify(data[0], null, 2)}`);
    }

    // Login
    console.log('\n2. Logging in...');
    await page.goto('http://localhost:5174');
    await page.waitForTimeout(2000);
    await page.fill('input[placeholder*="用户名"]', 'admin');
    await page.fill('input[type="password"]', '123456');
    await page.click('button:has-text("登录")');
    await page.waitForTimeout(3000);

    // Go to treatments page
    console.log('\n3. Navigating to treatments page...');
    await page.goto('http://localhost:5174/#/price-management/treatments');
    await page.waitForTimeout(5000);

    // Check API call
    console.log('\n4. Checking page state...');
    const h2 = await page.locator('h2').count();
    const table = await page.locator('table').count();
    const rows = await page.locator('table tbody tr').count();

    console.log(`   H2 elements: ${h2}`);
    console.log(`   Tables: ${table}`);
    console.log(`   Table rows: ${rows}`);

    // Check for API errors
    const errorCount = await page.locator('.el-message--error').count();
    console.log(`   Error messages: ${errorCount}`);

    await page.screenshot({ path: 'screenshots/test-api-directly.png', fullPage: true });

    console.log('\n✅ Test complete. Browser will stay open for 15 seconds...');
    await page.waitForTimeout(15000);

  } catch (error) {
    console.error('\n❌ Error:', error);
  } finally {
    await browser.close();
  }
})();
