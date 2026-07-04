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

    console.log('Step 3: Looking for 报价管理 menu item...');
    const quoteMenu = page.locator('text=报价管理').first();
    if (await quoteMenu.count() > 0) {
      await quoteMenu.click();
      console.log('✓ Clicked 报价管理');
      await page.waitForTimeout(2000);
    } else {
      console.log('✗ 报价管理 menu not found');
    }

    console.log('Step 4: Looking for 新建报价 button...');
    const createButton = page.locator('button:has-text("新建报价")').first();
    const buttonCount = await createButton.count();
    console.log(`Found ${buttonCount} 新建报价 button(s)`);

    if (buttonCount > 0) {
      console.log('✓ 新建报价 button exists!');
      await createButton.click();
      await page.waitForTimeout(1500);

      console.log('Step 5: Checking if dialog opened...');
      const dialogTitle = page.locator('.el-dialog__header:has-text("新建报价")');
      if (await dialogTitle.count() > 0) {
        console.log('✓ Dialog opened successfully!');
        await page.screenshot({ path: 'quote-dialog-opened.png' });

        console.log('Step 6: Testing parts dropdown search...');
        // Element Plus select renders as a custom component
        const partSelect = page.locator('.el-form-item label:has-text("零件")').locator('..').locator('.el-select input').first();
        if (await partSelect.count() > 0) {
          console.log('✓ Parts search input found');
          await partSelect.click();
          await page.waitForTimeout(500);
          await partSelect.fill('test');
          await page.waitForTimeout(2000);

          const dropdown = page.locator('.el-select-dropdown:visible');
          if (await dropdown.count() > 0) {
            const options = await dropdown.locator('.el-select-dropdown__item').count();
            console.log(`✓ Parts search returned ${options} options`);
            await page.screenshot({ path: 'parts-dropdown.png' });
          } else {
            console.log('⚠ Dropdown not visible (might be loading or no results)');
            await page.screenshot({ path: 'parts-dropdown.png' });
          }
        } else {
          console.log('✗ Parts search input not found');
          // Try alternative selector
          const altSelect = page.locator('input[placeholder="搜索零件名称/编号"]').first();
          if (await altSelect.count() > 0) {
            console.log('✓ Found with alternative selector');
            await altSelect.click();
            await altSelect.fill('test');
            await page.waitForTimeout(2000);
            await page.screenshot({ path: 'parts-dropdown.png' });
          }
        }

        console.log('Step 7: Checking for "客户件号" label...');
        const customerPartLabel = page.locator('label:has-text("客户件号")');
        if (await customerPartLabel.count() > 0) {
          console.log('✓ "客户件号" label found (correct!)');
        } else {
          const oldLabel = page.locator('label:has-text("客户品号")');
          if (await oldLabel.count() > 0) {
            console.log('✗ Still showing "客户品号" (incorrect)');
          } else {
            console.log('? Label not found');
          }
        }

        await page.screenshot({ path: 'quote-dialog-full.png' });

      } else {
        console.log('✗ Dialog did not open');
      }

    } else {
      console.log('✗ 新建报价 button NOT found!');
      console.log('This might be due to:');
      console.log('  - User role is not manager');
      console.log('  - Button is hidden by permissions');
    }

    console.log('\nStep 8: Checking table for "客户件号" column...');
    const tableColumn = page.locator('.el-table__header th:has-text("客户件号")');
    if (await tableColumn.count() > 0) {
      console.log('✓ Table column "客户件号" found (correct!)');
    } else {
      const oldColumn = page.locator('.el-table__header th:has-text("客户品号")');
      if (await oldColumn.count() > 0) {
        console.log('✗ Table still showing "客户品号" (incorrect)');
      }
    }

    await page.screenshot({ path: 'quote-list-page.png' });

    console.log('\n=== Test Summary ===');
    console.log('Screenshots saved:');
    console.log('  - quote-dialog-opened.png');
    console.log('  - parts-dropdown.png');
    console.log('  - quote-dialog-full.png');
    console.log('  - quote-list-page.png');

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
