const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext();
  const page = await context.newPage();

  // 监听所有请求
  page.on('request', request => {
    if (request.url().includes('part-names')) {
      console.log('\n>>> 请求:', request.method(), request.url());
      console.log('>>> 请求头:', JSON.stringify(request.headers(), null, 2));
      if (request.postData()) {
        console.log('>>> 请求体:', request.postData());
      }
    }
  });

  // 监听所有响应
  page.on('response', async response => {
    if (response.url().includes('part-names')) {
      console.log('\n<<< 响应:', response.status(), response.url());
      console.log('<<< 响应头:', JSON.stringify(response.headers(), null, 2));
      try {
        const body = await response.text();
        console.log('<<< 响应体:', body);
      } catch (e) {
        console.log('<<< 无法读取响应体');
      }
    }
  });

  try {
    console.log('1. 访问登录页面...');
    await page.goto('http://localhost:5175/login');
    await page.waitForTimeout(2000);

    console.log('2. 登录系统...');
    await page.fill('input[type="text"]', 'admin');
    await page.fill('input[type="password"]', '123456');
    await page.click('button:has-text("登录")');
    await page.waitForTimeout(3000);

    console.log('3. 进入报价管理页面...');
    await page.goto('http://localhost:5175/quotes');
    await page.waitForTimeout(2000);

    console.log('4. 点击新建报价...');
    await page.click('button:has-text("新建报价")');
    await page.waitForTimeout(1500);

    console.log('5. 点击快捷新增零件名称...');
    const quickAddBtn = page.locator('.el-form-item').filter({
      has: page.locator('label:has-text("零件名称")')
    }).locator('button').first();
    await quickAddBtn.click();
    await page.waitForTimeout(1500);

    console.log('6. 填写表单...');
    const dialog = page.locator('.el-dialog').filter({ hasText: '快捷新增零件名称' });

    // 填写一级分类
    const primaryInput = dialog.locator('.el-form-item').filter({
      has: page.locator('label:has-text("一级分类")')
    }).locator('input').first();
    await primaryInput.fill('测试分类');

    // 填写二级分类
    const secondaryInput = dialog.locator('.el-form-item').filter({
      has: page.locator('label:has-text("二级分类")')
    }).locator('input').first();
    await secondaryInput.fill('测试二级');

    // 填写客户零件名称
    const customerInput = dialog.locator('.el-form-item').filter({
      has: page.locator('label:has-text("客户零件名称")')
    }).locator('input').first();
    await customerInput.fill('测试客户件');

    // 填写备注
    const remarkInput = dialog.locator('.el-form-item').filter({
      has: page.locator('label:has-text("备注")')
    }).locator('textarea').first();
    await remarkInput.fill('测试备注');

    await page.waitForTimeout(500);

    console.log('\n7. 获取表单数据（点击保存前）...');
    const formData = await page.evaluate(() => {
      // 尝试从Vue组件中获取数据
      return {
        note: '无法直接从页面获取Vue reactive数据，将通过网络请求查看'
      };
    });
    console.log('表单数据:', formData);

    console.log('\n8. 点击保存按钮...');
    await dialog.locator('button:has-text("保存")').click();

    // 等待响应
    await page.waitForTimeout(3000);

    console.log('\n=== 测试完成 ===');
    console.log('请查看上面的请求和响应日志');

  } catch (error) {
    console.error('\n测试出错:', error.message);
  } finally {
    console.log('\n浏览器将保持打开30秒...');
    await page.waitForTimeout(30000);
    await browser.close();
  }
})();
