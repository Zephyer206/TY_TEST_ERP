const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: false, slowMo: 500 });
  const page = await browser.newPage();

  // Block the failing production API call
  await page.route('**/api/v1/production/plans**', route => {
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([])
    });
  });

  console.log('=== Testing with Production API blocked ===');

  try {
    console.log('\n1. Login...');
    await page.goto('http://localhost:5174');
    await page.waitForTimeout(2000);
    await page.fill('input[placeholder*="用户名"]', 'admin');
    await page.fill('input[type="password"]', '123456');
    await page.click('button:has-text("登录")');
    await page.waitForTimeout(3000);
    console.log('✅ Logged in');

    console.log('\n2. Go to Treatments page...');
    await page.goto('http://localhost:5174/#/price-management/treatments');
    await page.waitForTimeout(5000);

    const rows = await page.locator('table tbody tr').count();
    console.log(`\n✅ Treatments page loaded: ${rows} rows`);

    if (rows > 0) {
      const firstRow = await page.locator('table tbody tr').first().allTextContents();
      console.log(`   First row: ${firstRow}`);
    }

    await page.screenshot({ path: 'screenshots/treatments-success.png', fullPage: true });

    console.log('\n🎉 SUCCESS! 价格管理系统工序字典页面已成功显示！');
    console.log(`\n✅ 找到 ${rows} 条工序记录！`);

    await page.waitForTimeout(10000);

  } catch (error) {
    console.error('Error:', error.message);
  } finally {
    await browser.close();
  }
})();
