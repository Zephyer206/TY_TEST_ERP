const { chromium } = require('playwright');

(async () => {
  console.log('🚀 Starting parts page test...\n');

  const browser = await chromium.launch({
    headless: false,
    slowMo: 500
  });

  const context = await browser.newContext();
  const page = await context.newPage();

  try {
    // Step 1: Navigate to frontend
    console.log('📂 Opening http://localhost:5173...');
    await page.goto('http://localhost:5173');
    await page.waitForTimeout(2000);
    console.log('✅ Page loaded\n');

    // Step 2: Login
    console.log('🔐 Logging in...');
    const usernameInput = page.locator('input[placeholder*="用户名"], input[type="text"]').first();
    const passwordInput = page.locator('input[type="password"]').first();
    const loginButton = page.locator('button:has-text("登录")').first();

    await usernameInput.fill('admin');
    await passwordInput.fill('123456');
    await page.screenshot({ path: 'screenshots/parts-01-login-filled.png' });
    console.log('✅ Filled credentials\n');

    await loginButton.click();
    await page.waitForTimeout(3000);
    await page.screenshot({ path: 'screenshots/parts-02-after-login.png' });
    console.log('✅ Logged in\n');

    // Step 3: Navigate to parts page
    console.log('📋 Navigating to parts page...');
    await page.goto('http://localhost:5173/parts');
    await page.waitForTimeout(3000);
    await page.screenshot({ path: 'screenshots/parts-03-parts-page.png' });
    console.log('✅ Parts page loaded\n');

    // Step 4: Check if parts table is visible
    console.log('🔍 Checking parts table...');
    const table = page.locator('.el-table');
    const tableExists = await table.count() > 0;

    if (tableExists) {
      console.log('✅ Parts table found\n');

      // Check for data rows
      const rows = page.locator('.el-table__row');
      const rowCount = await rows.count();
      console.log(`📊 Found ${rowCount} rows in table\n`);

      // Check for search input
      const searchInput = page.locator('input[placeholder*="零件编号"], input[placeholder*="搜索"]').first();
      const hasSearch = await searchInput.count() > 0;
      console.log(hasSearch ? '✅ Search input found' : '❌ Search input not found');

      // Check for customer filter
      const customerSelect = page.locator('.el-select').first();
      const hasCustomerFilter = await customerSelect.count() > 0;
      console.log(hasCustomerFilter ? '✅ Customer filter found' : '❌ Customer filter not found');

      // Take final screenshot
      await page.screenshot({ path: 'screenshots/parts-04-final.png', fullPage: true });
      console.log('\n✅ Test completed successfully!');

    } else {
      console.log('❌ Parts table not found!\n');

      // Check for error messages
      const errorMsg = await page.textContent('body');
      console.log('Page content preview:', errorMsg.substring(0, 500));
    }

  } catch (error) {
    console.error('❌ Test failed:', error.message);
    await page.screenshot({ path: 'screenshots/parts-error.png' });
  } finally {
    console.log('\n🏁 Closing browser...');
    await browser.close();
  }
})();
