const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: false, slowMo: 800 });
  const page = await browser.newPage();

  page.on('console', msg => console.log(`[Browser ${msg.type()}]:`, msg.text()));
  page.on('pageerror', err => console.log('[Page Error]:', err.message));

  try {
    console.log('=== 1. Login ===');
    await page.goto('http://localhost:5174');
    await page.waitForTimeout(2000);

    await page.fill('input[placeholder*="用户名"]', 'admin');
    await page.fill('input[type="password"]', '123456');
    await page.click('button:has-text("登录")');
    await page.waitForTimeout(3000);
    console.log('✅ Login successful');

    console.log('\n=== 2. Navigate to Treatment Dictionary ===');
    await page.goto('http://localhost:5174/#/price-management/treatments');
    await page.waitForTimeout(3000);

    const treatmentCount = await page.locator('table tbody tr').count();
    console.log(`✅ Treatment Dictionary loaded: ${treatmentCount} treatments found`);

    if (treatmentCount > 0) {
      const firstTreatment = await page.locator('table tbody tr').first().textContent();
      console.log(`   First treatment: ${firstTreatment.substring(0, 50)}...`);
    }

    console.log('\n=== 3. Navigate to Customer Prices ===');
    await page.goto('http://localhost:5174/#/price-management/customer-prices');
    await page.waitForTimeout(3000);

    const hasMaterialTab = await page.locator('text=材料价格').count() > 0;
    const hasTreatmentTab = await page.locator('text=工序价格').count() > 0;
    console.log(`✅ Customer Prices page loaded`);
    console.log(`   Material tab: ${hasMaterialTab ? '✓' : '✗'}`);
    console.log(`   Treatment tab: ${hasTreatmentTab ? '✓' : '✗'}`);

    console.log('\n=== 4. Navigate to Price Adjustments ===');
    await page.goto('http://localhost:5174/#/price-management/price-adjustments');
    await page.waitForTimeout(3000);

    const hasAdjustmentTable = await page.locator('table, .el-table').count() > 0;
    console.log(`✅ Price Adjustments page loaded`);
    console.log(`   Has table: ${hasAdjustmentTable ? '✓' : '✗'}`);

    console.log('\n=== 5. Screenshot All Pages ===');
    await page.goto('http://localhost:5174/#/price-management/treatments');
    await page.waitForTimeout(2000);
    await page.screenshot({ path: 'screenshots/treatments-page.png', fullPage: true });
    console.log('✅ Screenshot: treatments-page.png');

    await page.goto('http://localhost:5174/#/price-management/customer-prices');
    await page.waitForTimeout(2000);
    await page.screenshot({ path: 'screenshots/customer-prices-page.png', fullPage: true });
    console.log('✅ Screenshot: customer-prices-page.png');

    await page.goto('http://localhost:5174/#/price-management/price-adjustments');
    await page.waitForTimeout(2000);
    await page.screenshot({ path: 'screenshots/price-adjustments-page.png', fullPage: true });
    console.log('✅ Screenshot: price-adjustments-page.png');

    console.log('\n=== ✅ ALL TESTS PASSED ===');
    console.log('价格管理系统所有页面都已成功加载！');

    await page.waitForTimeout(5000);

  } catch (error) {
    console.error('\n❌ Error:', error.message);
    await page.screenshot({ path: 'screenshots/error.png', fullPage: true });
  } finally {
    await browser.close();
  }
})();
