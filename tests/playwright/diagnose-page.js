const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: false, slowMo: 500 });
  const page = await browser.newPage();

  // Enable console logging
  page.on('console', msg => console.log(`[Browser ${msg.type()}]:`, msg.text()));
  page.on('pageerror', err => console.log('[Page Error]:', err.message));

  try {
    console.log('Logging in...');
    await page.goto('http://localhost:5174');
    await page.waitForTimeout(2000);

    await page.fill('input[placeholder*="用户名"]', 'admin');
    await page.fill('input[type="password"]', '123456');
    await page.click('button:has-text("登录")');
    await page.waitForTimeout(3000);

    console.log('\nNavigating to treatments page...');
    await page.goto('http://localhost:5174/#/price-management/treatments');
    await page.waitForTimeout(5000);

    // Check what's on the page
    console.log('\n=== Page Analysis ===');
    const pageText = await page.textContent('body');
    console.log('Page contains "Treatment":', pageText.includes('Treatment'));
    console.log('Page contains "Add":', pageText.includes('Add'));
    console.log('Page contains "Table":', pageText.includes('Table'));

    const h2Count = await page.locator('h2').count();
    console.log('H2 count:', h2Count);
    if (h2Count > 0) {
      const h2Text = await page.locator('h2').first().textContent();
      console.log('First H2:', h2Text);
    }

    const buttonCount = await page.locator('button').count();
    console.log('Button count:', buttonCount);

    const tableCount = await page.locator('table, .el-table').count();
    console.log('Table count:', tableCount);

    const errorMsg = await page.locator('.el-message--error').count();
    console.log('Error messages:', errorMsg);

    // Check network errors
    console.log('\n=== Checking API calls ===');
    await page.screenshot({ path: 'screenshots/diagnosis.png', fullPage: true });

    console.log('\nBrowser will stay open for 30 seconds for inspection...');
    await page.waitForTimeout(30000);

  } catch (error) {
    console.error('Error:', error.message);
    await page.screenshot({ path: 'screenshots/diagnosis-error.png', fullPage: true });
    await page.waitForTimeout(30000);
  } finally {
    await browser.close();
  }
})();
