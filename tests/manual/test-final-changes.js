const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: false, slowMo: 500 });
  const context = await browser.newContext();
  const page = await context.newPage();

  try {
    console.log('Step 1: Opening frontend...');
    await page.goto('http://localhost:5173');
    await page.waitForTimeout(2000);

    console.log('Step 2: Logging in with admin/123456...');
    await page.fill('input[type="text"]', 'admin');
    await page.fill('input[type="password"]', '123456');
    await page.click('button[type="submit"], button:has-text("登录")');
    await page.waitForTimeout(3000);

    console.log('\n=== Test 1: Quote Form - Part Name Optional ===');
    const quoteMenu = page.locator('text=报价管理').first();
    await quoteMenu.click();
    await page.waitForTimeout(2000);

    const createButton = page.locator('button:has-text("新建报价")').first();
    await createButton.click();
    await page.waitForTimeout(1500);

    // Check if "零件名称" has no red asterisk (not required)
    const partNameLabel = page.locator('.el-form-item:has(label:text-is("零件名称"))').first();
    const hasRequiredClass = await partNameLabel.evaluate(el => el.classList.contains('is-required'));
    console.log('零件名称 required:', hasRequiredClass ? '✗ Yes (should be optional!)' : '✓ No (correct)');

    // Check if "客户" has red asterisk (required)
    const customerLabel = page.locator('.el-form-item:has(label:text-is("客户"))').first();
    const customerRequired = await customerLabel.evaluate(el => el.classList.contains('is-required'));
    console.log('客户 required:', customerRequired ? '✓ Yes (correct)' : '✗ No (should be required!)');

    // Check if "客户件号" has red asterisk (required)
    const customerPartLabel = page.locator('.el-form-item:has(label:text-is("客户件号"))').first();
    const customerPartRequired = await customerPartLabel.evaluate(el => el.classList.contains('is-required'));
    console.log('客户件号 required:', customerPartRequired ? '✓ Yes (correct)' : '✗ No (should be required!)');

    // Check for quick add buttons
    const partAddButton = page.locator('.el-form-item:has(label:text-is("零件名称")) button').first();
    const partAddExists = await partAddButton.count() > 0;
    console.log('零件名称 quick add button:', partAddExists ? '✓ Exists' : '✗ Missing');

    const customerAddButton = page.locator('.el-form-item:has(label:text-is("客户")) button').first();
    const customerAddExists = await customerAddButton.count() > 0;
    console.log('客户 quick add button:', customerAddExists ? '✓ Exists' : '✗ Missing');

    await page.screenshot({ path: 'quote-form-final.png' });

    // Test quick add part button
    if (partAddExists) {
      console.log('\n=== Test 2: Quick Add Part ===');
      await partAddButton.click();
      await page.waitForTimeout(1000);

      const quickPartDialog = page.locator('.el-dialog:has-text("快捷新增零件")');
      if (await quickPartDialog.count() > 0) {
        console.log('✓ Quick add part dialog opened');
        await page.screenshot({ path: 'quick-add-part.png' });
        await page.locator('button:has-text("取消")').last().click();
        await page.waitForTimeout(500);
      }
    }

    // Test quick add customer button
    if (customerAddExists) {
      console.log('\n=== Test 3: Quick Add Customer ===');
      await customerAddButton.click();
      await page.waitForTimeout(1000);

      const quickCustomerDialog = page.locator('.el-dialog:has-text("快捷新增客户")');
      if (await quickCustomerDialog.count() > 0) {
        console.log('✓ Quick add customer dialog opened');
        await page.screenshot({ path: 'quick-add-customer.png' });
        await page.locator('button:has-text("取消")').last().click();
        await page.waitForTimeout(500);
      }
    }

    // Close quote dialog
    await page.locator('.el-dialog:has-text("新建报价") button:has-text("取消")').click();
    await page.waitForTimeout(500);

    console.log('\n=== Test 4: Customers Management Page ===');
    const customersMenu = page.locator('text=客户管理').first();
    await customersMenu.click();
    await page.waitForTimeout(2000);

    const customerTable = page.locator('.el-table');
    const hasTable = await customerTable.count() > 0;
    console.log('Customer management page:', hasTable ? '✓ Loaded' : '✗ Not found');

    const addCustomerBtn = page.locator('button:has-text("新增客户")').first();
    const hasAddBtn = await addCustomerBtn.count() > 0;
    console.log('Add customer button:', hasAddBtn ? '✓ Exists' : '✗ Missing');

    await page.screenshot({ path: 'customers-management.png' });

    console.log('\n=== Test Summary ===');
    console.log('Screenshots saved:');
    console.log('  - quote-form-final.png');
    console.log('  - quick-add-part.png');
    console.log('  - quick-add-customer.png');
    console.log('  - customers-management.png');

    console.log('\nBrowser will stay open for 30 seconds...');
    await page.waitForTimeout(30000);

  } catch (error) {
    console.error('Error:', error.message);
    await page.screenshot({ path: 'test-error.png' });
  } finally {
    await browser.close();
    console.log('Test completed.');
  }
})();
