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

    // Test 1: Check Customers Management
    console.log('\n=== Testing Customers Management ===');
    const customersMenu = page.locator('text=客户管理').first();
    if (await customersMenu.count() > 0) {
      console.log('✓ Customers menu found');
      await customersMenu.click();
      await page.waitForTimeout(2000);

      const customerTable = page.locator('.el-table');
      if (await customerTable.count() > 0) {
        console.log('✓ Customers page loaded');
        await page.screenshot({ path: 'customers-page.png' });

        const addButton = page.locator('button:has-text("新增客户")');
        if (await addButton.count() > 0) {
          console.log('✓ Add customer button exists');
        }
      }
    } else {
      console.log('✗ Customers menu not found');
    }

    // Test 2: Check Quotes - "零件名称" label
    console.log('\n=== Testing Quotes Management ===');
    const quoteMenu = page.locator('text=报价管理').first();
    if (await quoteMenu.count() > 0) {
      await quoteMenu.click();
      console.log('✓ Clicked 报价管理');
      await page.waitForTimeout(2000);
    }

    const createButton = page.locator('button:has-text("新建报价")').first();
    if (await createButton.count() > 0) {
      console.log('✓ 新建报价 button exists');
      await createButton.click();
      await page.waitForTimeout(1500);

      const dialogTitle = page.locator('.el-dialog__header:has-text("新建报价")');
      if (await dialogTitle.count() > 0) {
        console.log('✓ Dialog opened');

        // Check for "零件名称" label
        const partNameLabel = page.locator('label:has-text("零件名称")').first();
        if (await partNameLabel.count() > 0) {
          console.log('✓ "零件名称" label found (correct!)');
        } else {
          const oldLabel = page.locator('label:has-text("零件")').first();
          if (await oldLabel.count() > 0) {
            console.log('✗ Still showing "零件" (incorrect)');
          }
        }

        // Check for required fields (look for asterisks or required class)
        const formLabels = await page.locator('.el-form-item__label').allTextContents();
        console.log('Form labels found:', formLabels.join(', '));

        await page.screenshot({ path: 'quote-dialog-updated.png' });

        // Close dialog
        await page.locator('button:has-text("取消")').click();
        await page.waitForTimeout(500);
      }
    }

    // Test 3: Check Parts - "零件名称" is optional
    console.log('\n=== Testing Parts Management ===');
    const partsMenu = page.locator('text=零件管理').first();
    if (await partsMenu.count() > 0) {
      await partsMenu.click();
      console.log('✓ Clicked 零件管理');
      await page.waitForTimeout(2000);

      const addPartButton = page.locator('button:has-text("新增零件")').first();
      if (await addPartButton.count() > 0) {
        await addPartButton.click();
        await page.waitForTimeout(1000);

        const partNameLabel = page.locator('label:has-text("零件名称")').first();
        if (await partNameLabel.count() > 0) {
          const partLabels = await page.locator('.el-dialog .el-form-item__label').allTextContents();
          console.log('Part form labels:', partLabels.join(', '));
        }

        await page.screenshot({ path: 'parts-dialog.png' });
        await page.locator('button:has-text("取消")').click();
        await page.waitForTimeout(500);
      }
    }

    console.log('\n=== Test Summary ===');
    console.log('Screenshots saved:');
    console.log('  - customers-page.png');
    console.log('  - quote-dialog-updated.png');
    console.log('  - parts-dialog.png');

    console.log('\nBrowser will stay open for 30 seconds for manual inspection...');
    await page.waitForTimeout(30000);

  } catch (error) {
    console.error('Error:', error.message);
    await page.screenshot({ path: 'error-screenshot.png' });
  } finally {
    await browser.close();
    console.log('Browser closed.');
  }
})();
