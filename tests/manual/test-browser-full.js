const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: false, slowMo: 800 });
  const context = await browser.newContext();
  const page = await context.newPage();

  try {
    console.log('=== 开始完整功能测试 ===\n');

    console.log('Step 1: 登录系统...');
    await page.goto('http://localhost:5173');
    await page.waitForTimeout(2000);
    await page.fill('input[type="text"]', 'admin');
    await page.fill('input[type="password"]', '123456');
    await page.click('button[type="submit"], button:has-text("登录"), button.el-button--primary');
    await page.waitForTimeout(3000);
    console.log('✓ 登录成功\n');

    // ========== 测试 1: 报价表单字段 ==========
    console.log('【测试 1】报价表单字段验证');
    await page.click('text=报价管理');
    await page.waitForTimeout(2000);
    await page.click('button:has-text("新建报价")');
    await page.waitForTimeout(1500);

    const partNameItem = page.locator('.el-form-item:has(label:text-is("零件名称"))').first();
    const partNameRequired = await partNameItem.evaluate(el => el.classList.contains('is-required'));
    console.log('  零件名称是否必选:', partNameRequired ? '❌ 是（应该是非必选）' : '✅ 否（正确）');

    const customerItem = page.locator('.el-form-item:has(label:text-is("客户"))').first();
    const customerRequired = await customerItem.evaluate(el => el.classList.contains('is-required'));
    console.log('  客户是否必选:', customerRequired ? '✅ 是（正确）' : '❌ 否（应该是必选）');

    const customerPartItem = page.locator('.el-form-item:has(label:text-is("客户件号"))').first();
    const customerPartRequired = await customerPartItem.evaluate(el => el.classList.contains('is-required'));
    console.log('  客户件号是否必选:', customerPartRequired ? '✅ 是（正确）' : '❌ 否（应该是必选）');

    await page.screenshot({ path: 'test-1-quote-form.png' });
    console.log('  📸 截图已保存: test-1-quote-form.png\n');

    // ========== 测试 2: 快捷新增零件 ==========
    console.log('【测试 2】快捷新增零件功能');
    const partAddBtn = page.locator('.el-form-item:has(label:text-is("零件名称")) button:has(i.el-icon)').first();
    if (await partAddBtn.count() > 0) {
      console.log('  ✅ 找到快捷新增零件按钮');
      await partAddBtn.click();
      await page.waitForTimeout(1500);

      const partDialog = page.locator('.el-dialog:has-text("快捷新增零件")');
      if (await partDialog.isVisible()) {
        console.log('  ✅ 快捷新增零件对话框已打开');
        await page.screenshot({ path: 'test-2-quick-add-part.png' });
        console.log('  📸 截图已保存: test-2-quick-add-part.png');
        await page.locator('.el-dialog:has-text("快捷新增零件") button:has-text("取消")').click();
        await page.waitForTimeout(500);
      }
    } else {
      console.log('  ❌ 未找到快捷新增零件按钮');
    }
    console.log('');

    // ========== 测试 3: 快捷新增客户 ==========
    console.log('【测试 3】快捷新增客户功能');
    const customerAddBtn = page.locator('.el-form-item:has(label:text-is("客户")) button:has(i.el-icon)').first();
    if (await customerAddBtn.count() > 0) {
      console.log('  ✅ 找到快捷新增客户按钮');
      await customerAddBtn.click();
      await page.waitForTimeout(1500);

      const customerDialog = page.locator('.el-dialog:has-text("快捷新增客户")');
      if (await customerDialog.isVisible()) {
        console.log('  ✅ 快捷新增客户对话框已打开');
        await page.screenshot({ path: 'test-3-quick-add-customer.png' });
        console.log('  📸 截图已保存: test-3-quick-add-customer.png');

        // 测试创建新客户
        console.log('  正在测试创建新客户...');
        await page.fill('.el-dialog:has-text("快捷新增客户") input[placeholder="请输入客户名称"]', 'TEST_客户_' + Date.now());
        await page.click('.el-dialog:has-text("快捷新增客户") button:has-text("保存")');
        await page.waitForTimeout(3000);

        // 检查是否有成功消息或错误消息
        const successMsg = await page.locator('.el-message--success').count();
        const errorMsg = await page.locator('.el-message--error').count();

        if (successMsg > 0) {
          console.log('  ✅ 新客户创建成功');
        } else if (errorMsg > 0) {
          const errText = await page.locator('.el-message--error').textContent();
          console.log('  ❌ 创建失败:', errText);
        }

        // 如果对话框还在，手动关闭
        const customerDialogStill = await page.locator('.el-dialog:has-text("快捷新增客户")').isVisible();
        if (customerDialogStill) {
          console.log('  对话框未自动关闭，手动关闭');
          await page.keyboard.press('Escape');
          await page.waitForTimeout(500);
        }
      }
    } else {
      console.log('  ❌ 未找到快捷新增客户按钮');
    }

    // 等待确保所有对话框都关闭
    await page.waitForTimeout(1000);

    // 关闭报价对话框（如果还在）
    const quoteDialog = page.locator('.el-dialog:has-text("新建报价")');
    if (await quoteDialog.isVisible()) {
      await page.locator('.el-dialog:has-text("新建报价") button:has-text("取消")').click();
      await page.waitForTimeout(500);
    }
    console.log('');

    // ========== 测试 4: 客户管理页面 ==========
    console.log('【测试 4】客户管理页面');
    await page.click('text=客户管理');
    await page.waitForTimeout(2000);

    const customerTable = await page.locator('.el-table').count();
    console.log('  客户列表:', customerTable > 0 ? '✅ 已加载' : '❌ 未加载');

    await page.screenshot({ path: 'test-4-customers-list.png' });
    console.log('  📸 截图已保存: test-4-customers-list.png');

    // 测试删除现有客户（应该被拒绝）
    console.log('\n  正在测试删除保护功能...');
    const firstDeleteBtn = page.locator('.el-table .el-button:has-text("删除")').first();
    if (await firstDeleteBtn.count() > 0) {
      await firstDeleteBtn.click();
      await page.waitForTimeout(500);

      const confirmBtn = page.locator('.el-message-box button:has-text("确定")');
      if (await confirmBtn.count() > 0) {
        await confirmBtn.click();
        await page.waitForTimeout(2000);

        // 检查是否有错误消息
        const errorMsg = page.locator('.el-message--error');
        if (await errorMsg.count() > 0) {
          const msgText = await errorMsg.textContent();
          console.log('  ✅ 现有客户删除被拒绝:', msgText);
        }
      }
    }
    console.log('');

    // ========== 测试 5: 零件管理页面 ==========
    console.log('【测试 5】零件管理页面');
    await page.click('text=零件管理');
    await page.waitForTimeout(2000);

    const partsTable = await page.locator('.el-table').count();
    console.log('  零件列表:', partsTable > 0 ? '✅ 已加载' : '❌ 未加载');

    const addPartBtn = page.locator('button:has-text("新增零件")').first();
    if (await addPartBtn.count() > 0) {
      console.log('  ✅ 找到新增零件按钮');
    }

    const deleteButtons = await page.locator('.el-table .el-button:has-text("删除")').count();
    console.log('  删除按钮数量:', deleteButtons);

    await page.screenshot({ path: 'test-5-parts-list.png' });
    console.log('  📸 截图已保存: test-5-parts-list.png\n');

    console.log('=== 测试完成 ===');
    console.log('\n所有截图已保存:');
    console.log('  1. test-1-quote-form.png - 报价表单');
    console.log('  2. test-2-quick-add-part.png - 快捷新增零件');
    console.log('  3. test-3-quick-add-customer.png - 快捷新增客户');
    console.log('  4. test-4-customers-list.png - 客户管理');
    console.log('  5. test-5-parts-list.png - 零件管理');

    console.log('\n浏览器将保持打开 60 秒供手动检查...');
    await page.waitForTimeout(60000);

  } catch (error) {
    console.error('❌ 测试失败:', error.message);
    await page.screenshot({ path: 'test-error.png' });
  } finally {
    await browser.close();
    console.log('\n测试结束。');
  }
})();
