const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: false, slowMo: 500 });
  const page = await browser.newPage();

  try {
    console.log('=== Testing Price Management Menu ===\n');

    console.log('1. Login...');
    await page.goto('http://localhost:5174');
    await page.waitForTimeout(2000);
    await page.fill('input[placeholder*="用户名"]', 'admin');
    await page.fill('input[type="password"]', '123456');
    await page.click('button:has-text("登录")');
    await page.waitForTimeout(5000);

    console.log('\n2. Looking for 价格管理 menu...');
    const priceMenu = await page.locator('text=价格管理').count();
    console.log(`   Found "价格管理" menu: ${priceMenu > 0 ? 'YES' : 'NO'}`);

    if (priceMenu > 0) {
      console.log('\n3. Clicking 价格管理 menu...');
      await page.click('text=价格管理');
      await page.waitForTimeout(2000);

      console.log('\n4. Looking for submenu items...');
      const dict = await page.locator('text=工序字典').count();
      const prices = await page.locator('text=客户价格').count();
      const adj = await page.locator('text=价格调整').count();
      
      console.log(`   工序字典: ${dict > 0 ? 'YES' : 'NO'}`);
      console.log(`   客户价格: ${prices > 0 ? 'YES' : 'NO'}`);
      console.log(`   价格调整: ${adj > 0 ? 'YES' : 'NO'}`);

      if (dict > 0) {
        console.log('\n5. Clicking 工序字典...');
        await page.click('text=工序字典');
        await page.waitForTimeout(5000);

        const h2 = await page.locator('h2').allTextContents();
        const rows = await page.locator('table tbody tr').count();
        
        console.log(`   H2: ${h2.join(', ')}`);
        console.log(`   Table rows: ${rows}`);

        if (rows > 0) {
          console.log('\n🎉🎉🎉 SUCCESS! 价格管理系统工作了！🎉🎉🎉');
          console.log(`找到 ${rows} 条工序记录！`);
        }

        await page.screenshot({ path: 'screenshots/success-final.png', fullPage: true });
      }
    }

    await page.waitForTimeout(10000);

  } catch (error) {
    console.error('Error:', error.message);
  } finally {
    await browser.close();
  }
})();
