const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext();
  const page = await context.newPage();

  try {
    console.log('访问登录页面...');
    await page.goto('http://localhost:5173/login');
    await page.waitForTimeout(2000);

    // 登录 (假设有测试账号)
    console.log('尝试登录...');
    await page.fill('input[type="text"]', 'admin');
    await page.fill('input[type="password"]', 'admin123');
    await page.click('button[type="submit"]');
    await page.waitForTimeout(3000);

    // 检查是否登录成功
    const url = page.url();
    console.log('当前URL:', url);

    if (url.includes('/dashboard') || url.includes('/quotes')) {
      console.log('✓ 登录成功');

      // 访问报价管理页面
      console.log('访问报价管理页面...');
      await page.goto('http://localhost:5173/quotes');
      await page.waitForTimeout(2000);

      // 点击新建报价按钮
      console.log('点击新建报价按钮...');
      const newQuoteBtn = await page.locator('button:has-text("新建报价")').first();
      if (await newQuoteBtn.isVisible()) {
        await newQuoteBtn.click();
        await page.waitForTimeout(1000);

        // 检查零件名称字段
        console.log('检查零件名称字段...');
        const partNameLabel = await page.locator('label:has-text("零件名称")').first();
        if (await partNameLabel.isVisible()) {
          console.log('✓ 找到零件名称字段');

          // 检查是否有下拉选择框
          const partNameSelect = await page.locator('label:has-text("零件名称")').locator('..').locator('.el-select').first();
          if (await partNameSelect.isVisible()) {
            console.log('✓ 零件名称已改为下拉选择');

            // 检查快捷新增按钮
            const quickAddBtn = await page.locator('label:has-text("零件名称")').locator('..').locator('button').first();
            if (await quickAddBtn.isVisible()) {
              console.log('✓ 找到快捷新增按钮');

              // 点击快捷新增按钮
              await quickAddBtn.click();
              await page.waitForTimeout(1000);

              // 检查是否弹出快捷新增对话框
              const quickAddDialog = await page.locator('.el-dialog:has-text("快捷新增零件名称")').first();
              if (await quickAddDialog.isVisible()) {
                console.log('✓ 快捷新增零件名称对话框已打开');

                // 测试填写表单
                await page.fill('.el-dialog:has-text("快捷新增零件名称") input[placeholder*="零件名称"]', '测试零件A');
                await page.fill('.el-dialog:has-text("快捷新增零件名称") input[placeholder*="弹簧片"]', '弹簧片');
                console.log('✓ 表单填写完成');

                // 关闭对话框
                await page.click('.el-dialog:has-text("快捷新增零件名称") button:has-text("取消")');
                await page.waitForTimeout(500);

                console.log('\n========== 测试结果 ==========');
                console.log('✓ 零件名称字段改造成功');
                console.log('✓ 快捷新增零件名称功能正常');
                console.log('==============================\n');
              } else {
                console.log('✗ 快捷新增对话框未打开');
              }
            } else {
              console.log('✗ 未找到快捷新增按钮');
            }
          } else {
            console.log('✗ 零件名称字段不是下拉选择');
          }
        } else {
          console.log('✗ 未找到零件名称字段');
        }
      } else {
        console.log('✗ 未找到新建报价按钮');
      }
    } else {
      console.log('✗ 登录失败或跳转异常');
    }

  } catch (error) {
    console.error('测试出错:', error.message);
  } finally {
    await page.waitForTimeout(2000);
    await browser.close();
  }
})();
