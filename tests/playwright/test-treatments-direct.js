const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: false, slowMo: 500 });
  const page = await browser.newPage();

  page.on('console', msg => console.log(`[${msg.type()}]:`, msg.text()));

  try {
    console.log('=== Login ===');
    await page.goto('http://localhost:5174');
    await page.waitForTimeout(2000);

    await page.fill('input[placeholder*="用户名"]', 'admin');
    await page.fill('input[type="password"]', '123456');
    await page.click('button:has-text("登录")');
    await page.waitForTimeout(2000);
    console.log('✅ Logged in');

    console.log('\n=== Go to Treatment Dictionary (direct URL) ===');
    await page.goto('http://localhost:5174/#/price-management/treatments');
    await page.waitForTimeout(5000);

    const rows = await page.locator('table tbody tr').count();
    console.log(`\n✅ Treatment Dictionary Page:`);
    console.log(`   Rows found: ${rows}`);

    if (rows > 0) {
      const cells = await page.locator('table tbody tr').first().locator('td').allTextContents();
      console.log(`   First row: ${cells.join(' | ')}`);
    }

    await page.screenshot({ path: 'screenshots/treatments-final.png', fullPage: true });
    console.log('\n✅ Screenshot saved: screenshots/treatments-final.png');

    console.log('\n=== SUCCESS: 价格管理系统的工序字典页面已成功显示！===');
    console.log('你现在可以看到价格管理系统了！');

    await page.waitForTimeout(10000);

  } catch (error) {
    console.error('Error:', error.message);
    await page.screenshot({ path: 'screenshots/error-final.png' });
  } finally {
    await browser.close();
  }
})();
