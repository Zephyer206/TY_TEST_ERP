const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: false, slowMo: 500 });
  const page = await browser.newPage();

  // Log everything
  page.on('console', msg => {
    if (!msg.text().includes('vite')) {
      console.log(`[Console] ${msg.text()}`);
    }
  });

  // Monitor network
  page.on('request', req => {
    if (req.url().includes('treatments')) {
      console.log(`[Request] ${req.method()} ${req.url()}`);
    }
  });

  page.on('response', async res => {
    if (res.url().includes('treatments')) {
      console.log(`[Response] ${res.status()} ${res.url()}`);
      if (res.ok()) {
        const text = await res.text();
        console.log(`[Data] ${text.substring(0, 100)}...`);
      }
    }
  });

  try {
    console.log('=== Testing Direct Access ===\n');

    // Login
    console.log('1. Logging in...');
    await page.goto('http://localhost:5174/');
    await page.waitForTimeout(2000);
    await page.fill('input[placeholder*="用户名"]', 'admin');
    await page.fill('input[type="password"]', '123456');
    await page.click('button:has-text("登录")');
    await page.waitForTimeout(5000);

    // Direct navigation
    console.log('\n2. Navigating directly to treatments...');
    await page.goto('http://localhost:5174/#/price-management/treatments');
    await page.waitForTimeout(10000);

    // Check what's rendered
    console.log('\n3. Checking rendered content...');
    const url = page.url();
    console.log(`   URL: ${url}`);

    const h2 = await page.locator('h2').allTextContents();
    console.log(`   H2 elements: ${h2.join(', ')}`);

    const buttons = await page.locator('button').count();
    console.log(`   Buttons: ${buttons}`);

    const tables = await page.locator('table').count();
    console.log(`   Tables: ${tables}`);

    const rows = await page.locator('table tbody tr').count();
    console.log(`   Table rows: ${rows}`);

    // Check if TreatmentDict component is mounted
    const cardHeader = await page.locator('.el-card .header').count();
    console.log(`   Card headers: ${cardHeader}`);

    await page.screenshot({ path: 'screenshots/direct-access-final.png', fullPage: true });
    console.log('\n✅ Screenshot saved');

    if (rows > 0) {
      console.log(`\n🎉 SUCCESS! Found ${rows} treatment records!`);
    } else {
      console.log('\n❌ No data displayed');
    }

    await page.waitForTimeout(15000);

  } catch (error) {
    console.error('Error:', error.message);
  } finally {
    await browser.close();
  }
})();
