const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext();
  const page = await context.newPage();

  try {
    console.log('1. 登录...');
    await page.goto('http://localhost:5175/login');
    await page.waitForTimeout(1500);
    await page.fill('input[type="text"]', 'admin');
    await page.fill('input[type="password"]', '123456');
    await page.click('button:has-text("登录")');
    await page.waitForTimeout(3000);

    console.log('\n2. 测试API返回的字段...');
    const apiResponse = await page.evaluate(async () => {
      const token = localStorage.getItem('token');
      const response = await fetch('http://localhost:5175/api/v1/part-names?limit=1', {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      const data = await response.json();
      return data;
    });

    console.log('API响应数据:', JSON.stringify(apiResponse, null, 2));

    if (apiResponse && apiResponse.length > 0) {
      const firstItem = apiResponse[0];
      console.log('\n字段检查:');
      console.log('  ✓ primary_category:', firstItem.primary_category || '❌ 不存在');
      console.log('  ✓ secondary_category:', firstItem.secondary_category || '(null)');
      console.log('  ✓ customer_part_name:', firstItem.customer_part_name || '(null)');
      console.log('  ✓ remark:', firstItem.remark || '(null)');
      console.log('\n  旧字段:');
      console.log('  ✗ name:', firstItem.name || '不存在');
      console.log('  ✗ category:', firstItem.category || '不存在');
    }

    console.log('\n=== 测试完成 ===');

  } catch (error) {
    console.error('错误:', error.message);
  } finally {
    await page.waitForTimeout(5000);
    await browser.close();
  }
})();
