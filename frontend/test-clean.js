const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: false, slowMo: 300 });
  const page = await browser.newPage();

  // Capture console
  page.on('console', msg => {
    if (msg.type() === 'error' || msg.text().includes('Treatment') || msg.text().includes('Failed')) {
      console.log(`[${msg.type()}] ${msg.text()}`);
    }
  });

  // Block problematic APIs
  await page.route('**/api/v1/production/**', route => route.fulfill({ status: 200, body: '[]', contentType: 'application/json' }));
  await page.route('**/api/v1/quotes**', route => route.fulfill({ status: 200, body: '[]', contentType: 'application/json' }));
  await page.route('**/api/v1/quality/**', route => route.fulfill({ status: 200, body: '[]', contentType: 'application/json' }));
  await page.route('**/api/v1/warehouse/**', route => route.fulfill({ status: 200, body: '[]', contentType: 'application/json' }));

  try {
    console.log('=== Clean test with all APIs mocked ===\n');

    console.log('1. Login...');
    await page.goto('http://localhost:5174');
    await page.waitForTimeout(2000);
    await page.fill('input[placeholder*="用户名"]', 'admin');
    await page.fill('input[type="password"]', '123456');
    await page.click('button:has-text("登录")');
    await page.waitForTimeout(3000);
    console.log('✅ Login complete');

    console.log('\n2. Navigate to treatments...');
    await page.goto('http://localhost:5174/#/price-management/treatments');
    await page.waitForTimeout(8000);

    console.log('\n3. Check DOM...');

    // Check if we're on the right route
    const url = page.url();
    console.log(`   URL: ${url}`);

    // Check for any content
    const bodyText = await page.textContent('body');
    const hasContent = bodyText.length > 100;
    console.log(`   Body has content: ${hasContent} (${bodyText.length} chars)`);

    // Check for specific elements
    const elCard = await page.locator('.el-card').count();
    const h2Count = await page.locator('h2').count();
    const tableCount = await page.locator('.el-table, table').count();

    console.log(`   .el-card elements: ${elCard}`);
    console.log(`   h2 elements: ${h2Count}`);
    console.log(`   table elements: ${tableCount}`);

    if (h2Count > 0) {
      const h2Text = await page.locator('h2').first().textContent();
      console.log(`   H2 text: "${h2Text}"`);
    }

    // Take screenshot
    await page.screenshot({ path: 'screenshots/final-test.png', fullPage: true });
    console.log('\n✅ Screenshot: screenshots/final-test.png');

    // Check if component loaded
    if (elCard > 0 && h2Count > 0) {
      console.log('\n🎉 SUCCESS! Component loaded!');
    } else {
      console.log('\n❌ Component did NOT load');
      console.log(`First 200 chars of body: ${bodyText.substring(0, 200)}`);
    }

    await page.waitForTimeout(15000);

  } catch (error) {
    console.error('Error:', error.message);
  } finally {
    await browser.close();
  }
})();
