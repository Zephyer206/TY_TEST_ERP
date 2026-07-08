const { chromium } = require('playwright');

(async () => {
  console.log('🚀 Final Integration Test - Login + Dashboard Navigation\n');

  const browser = await chromium.launch({
    headless: false,
    slowMo: 300
  });

  const context = await browser.newContext();
  const page = await context.newPage();

  let testsPassed = 0;
  let testsFailed = 0;

  const test = (name, passed) => {
    if (passed) {
      console.log(`✅ ${name}`);
      testsPassed++;
    } else {
      console.log(`❌ ${name}`);
      testsFailed++;
    }
  };

  try {
    // Test 1: Load homepage
    console.log('📂 Test 1: Loading frontend...');
    await page.goto('http://localhost:5174');
    await page.waitForTimeout(1500);
    test('Homepage loads', page.url().includes('localhost:5174'));

    // Test 2: Login form present
    console.log('\n🔍 Test 2: Checking login form...');
    const hasUsername = await page.locator('input[placeholder*="用户名"]').count() > 0;
    const hasPassword = await page.locator('input[type="password"]').count() > 0;
    const hasButton = await page.locator('button:has-text("登录")').count() > 0;
    test('Login form present', hasUsername && hasPassword && hasButton);

    // Test 3: Fill and submit login
    console.log('\n🔐 Test 3: Logging in...');
    await page.fill('input[placeholder*="用户名"]', 'admin');
    await page.fill('input[type="password"]', '123456');
    await page.click('button:has-text("登录")');
    await page.waitForTimeout(3000);

    const token = await page.evaluate(() => localStorage.getItem('token'));
    test('Login successful (token stored)', !!token);

    const url = page.url();
    test('Redirected to dashboard', url.includes('/dashboard'));

    // Test 4: Dashboard loads without errors
    console.log('\n📊 Test 4: Checking dashboard...');
    await page.waitForTimeout(2000);

    const hasNav = await page.locator('nav, .el-menu, [class*="menu"], aside').count() > 0;
    test('Navigation menu present', hasNav);

    // Test 5: Check for critical errors
    console.log('\n🔍 Test 5: Checking for errors...');
    const errors = await page.locator('.el-message--error').count();
    test('No error messages', errors === 0);

    // Test 6: Try navigation (if menu exists)
    if (hasNav) {
      console.log('\n🧭 Test 6: Testing navigation...');
      const menuItems = await page.locator('.el-menu-item, [class*="menu-item"]').count();
      test('Menu items available', menuItems > 0);
    }

    await page.screenshot({ path: 'screenshots/final-test-dashboard.png' });

    // Summary
    console.log('\n' + '='.repeat(60));
    console.log('📊 Test Summary:');
    console.log(`   ✅ Passed: ${testsPassed}`);
    console.log(`   ❌ Failed: ${testsFailed}`);
    console.log(`   📈 Success Rate: ${Math.round(testsPassed / (testsPassed + testsFailed) * 100)}%`);
    console.log('='.repeat(60));

    if (testsFailed === 0) {
      console.log('\n🎉 All tests passed! Login and dashboard are working correctly.');
    } else {
      console.log(`\n⚠️  ${testsFailed} test(s) failed. Check the issues above.`);
    }

    console.log('\n🌐 Browser will stay open for 30 seconds for manual inspection...');
    await page.waitForTimeout(30000);

  } catch (error) {
    console.error('\n❌ Test suite failed:', error.message);
    await page.screenshot({ path: 'screenshots/final-test-error.png' });
    testsFailed++;
  } finally {
    await browser.close();
    console.log('\n✅ Test completed');
    process.exit(testsFailed > 0 ? 1 : 0);
  }
})();
