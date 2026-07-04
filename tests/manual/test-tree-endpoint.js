const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext();
  const page = await context.newPage();

  try {
    console.log('1. Login...');
    await page.goto('http://localhost:5175/login');
    await page.waitForTimeout(1500);
    await page.fill('input[type="text"]', 'admin');
    await page.fill('input[type="password"]', '123456');
    await page.click('button:has-text("登录")');
    await page.waitForTimeout(3000);

    console.log('\n2. Test /tree endpoint...');
    const treeData = await page.evaluate(async () => {
      const token = localStorage.getItem('token');
      const response = await fetch('http://localhost:5175/api/v1/part-names/tree', {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      return await response.json();
    });

    console.log('Tree data:', JSON.stringify(treeData, null, 2));

  } catch (error) {
    console.error('Error:', error.message);
  } finally {
    await page.waitForTimeout(5000);
    await browser.close();
  }
})();
