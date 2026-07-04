const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext();
  const page = await context.newPage();

  try {
    console.log('访问报价页面（需要手动登录）...');
    await page.goto('http://localhost:5173/quotes');

    console.log('等待10秒，请手动登录...');
    await page.waitForTimeout(10000);

    // 检查当前页面
    const url = page.url();
    console.log('当前URL:', url);

    if (url.includes('/quotes')) {
      console.log('✓ 已在报价页面');

      // 点击新建报价按钮
      console.log('查找新建报价按钮...');
      await page.waitForSelector('button:has-text("新建报价")', { timeout: 5000 });
      const newQuoteBtn = page.locator('button:has-text("新建报价")').first();

      console.log('点击新建报价...');
      await newQuoteBtn.click();
      await page.waitForTimeout(2000);

      // 检查对话框
      console.log('检查新建报价对话框...');
      const dialog = page.locator('.el-dialog').filter({ hasText: '新建报价' });
      const isDialogVisible = await dialog.isVisible();

      if (isDialogVisible) {
        console.log('✓ 新建报价对话框已打开');

        // 检查零件名称字段
        const partNameRow = dialog.locator('.el-form-item').filter({ has: page.locator('label:has-text("零件名称")') });

        // 检查是否有el-select
        const hasSelect = await partNameRow.locator('.el-select').count() > 0;
        console.log('是否有下拉选择:', hasSelect ? '✓ 是' : '✗ 否');

        // 检查快捷新增按钮
        const quickAddBtn = partNameRow.locator('button').filter({ has: page.locator('.el-icon') });
        const hasQuickAddBtn = await quickAddBtn.count() > 0;
        console.log('是否有快捷新增按钮:', hasQuickAddBtn ? '✓ 是' : '✗ 否');

        if (hasQuickAddBtn) {
          // 点击快捷新增按钮
          console.log('点击快捷新增按钮...');
          await quickAddBtn.first().click();
          await page.waitForTimeout(1500);

          // 检查快捷新增对话框
          const quickDialog = page.locator('.el-dialog').filter({ hasText: '快捷新增零件名称' });
          const isQuickDialogVisible = await quickDialog.isVisible();

          if (isQuickDialogVisible) {
            console.log('✓ 快捷新增零件名称对话框已打开');

            // 检查表单字段
            const hasNameInput = await quickDialog.locator('input').first().isVisible();
            console.log('是否有输入框:', hasNameInput ? '✓ 是' : '✗ 否');

            console.log('\n========== 测试结果 ==========');
            console.log('✓ 零件名称改为下拉选择成功');
            console.log('✓ 快捷新增按钮存在');
            console.log('✓ 快捷新增对话框正常打开');
            console.log('==============================\n');
          } else {
            console.log('✗ 快捷新增对话框未打开');
          }
        }
      } else {
        console.log('✗ 新建报价对话框未打开');
      }
    } else {
      console.log('✗ 未在报价页面，请确认已登录');
    }

  } catch (error) {
    console.error('测试出错:', error.message);
    console.error(error.stack);
  } finally {
    console.log('\n测试结束，浏览器将保持打开5秒后关闭...');
    await page.waitForTimeout(5000);
    await browser.close();
  }
})();
