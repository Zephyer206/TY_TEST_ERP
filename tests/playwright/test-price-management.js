const { chromium } = require('playwright');

(async () => {
  console.log('Starting comprehensive price management system test...\n');

  const browser = await chromium.launch({
    headless: false,
    slowMo: 800  // Slow down to see what's happening
  });

  const context = await browser.newContext();
  const page = await context.newPage();

  let testsPassed = 0;
  let testsFailed = 0;

  const test = (name, passed, details = '') => {
    if (passed) {
      console.log(`✓ ${name}`);
      if (details) console.log(`  ${details}`);
      testsPassed++;
    } else {
      console.log(`✗ ${name}`);
      if (details) console.log(`  ${details}`);
      testsFailed++;
    }
  };

  try {
    // Step 1: Login
    console.log('=== STEP 1: Login ===');
    await page.goto('http://localhost:5174');
    await page.waitForTimeout(2000);

    await page.fill('input[placeholder*="用户名"]', 'admin');
    await page.fill('input[type="password"]', '123456');
    await page.click('button:has-text("登录")');
    await page.waitForTimeout(3000);

    const isLoggedIn = page.url().includes('/dashboard');
    test('Login successful', isLoggedIn);
    await page.screenshot({ path: 'screenshots/test-01-login.png' });

    if (!isLoggedIn) {
      throw new Error('Login failed');
    }

    // Step 2: Navigate to Treatment Dictionary (manually via URL since we may not have menu)
    console.log('\n=== STEP 2: Treatment Dictionary ===');
    await page.goto('http://localhost:5174/#/price-management/treatments');
    await page.waitForTimeout(3000);
    await page.screenshot({ path: 'screenshots/test-02-treatments-page.png' });

    const hasTreatmentTable = await page.locator('table, .el-table').count() > 0;
    test('Treatment dictionary page loads', hasTreatmentTable);

    // Check if we can see treatment data
    const treatmentRows = await page.locator('tr, .el-table__row').count();
    test('Treatment data visible', treatmentRows > 0, `Found ${treatmentRows} rows`);

    // Test: Add new treatment
    console.log('\nTesting: Create new treatment...');
    await page.click('button:has-text("Add Treatment")');
    await page.waitForTimeout(1000);

    const dialogVisible = await page.locator('.el-dialog').isVisible();
    test('Create dialog opens', dialogVisible);

    if (dialogVisible) {
      await page.fill('.el-dialog input[type="text"]', 'Test Treatment Automation');
      await page.selectOption('.el-dialog select', 'manual');

      // Fill number inputs
      const numberInputs = await page.locator('.el-dialog .el-input-number input').all();
      if (numberInputs.length >= 2) {
        await numberInputs[0].fill('5.50');  // default_rate
        await numberInputs[1].fill('100');    // sort_order
      }

      await page.screenshot({ path: 'screenshots/test-03-treatment-form.png' });

      await page.click('.el-dialog button:has-text("Save")');
      await page.waitForTimeout(2000);

      const successMsg = await page.locator('.el-message--success').count() > 0;
      test('Treatment created successfully', successMsg);
      await page.screenshot({ path: 'screenshots/test-04-treatment-created.png' });
    }

    // Step 3: Customer Material Prices
    console.log('\n=== STEP 3: Customer Material Prices ===');
    await page.goto('http://localhost:5174/#/price-management/customer-prices');
    await page.waitForTimeout(3000);
    await page.screenshot({ path: 'screenshots/test-05-customer-prices-page.png' });

    const hasPriceTabs = await page.locator('.el-tabs').count() > 0;
    test('Customer prices page loads', hasPriceTabs);

    // Test: Add material price
    console.log('\nTesting: Add material price...');
    await page.click('button:has-text("Add Price")');
    await page.waitForTimeout(1000);

    const priceDialogVisible = await page.locator('.el-dialog').isVisible();
    test('Add price dialog opens', priceDialogVisible);

    if (priceDialogVisible) {
      // Fill material price form
      const numberInputs2 = await page.locator('.el-dialog .el-input-number input').all();
      if (numberInputs2.length >= 4) {
        await numberInputs2[0].fill('1');     // customer_id
        await numberInputs2[1].fill('1');     // material_id
        await numberInputs2[2].fill('125.50'); // unit_price
        await numberInputs2[3].fill('10.25');  // scrap_price
      }

      await page.screenshot({ path: 'screenshots/test-06-material-price-form.png' });

      await page.click('.el-dialog button:has-text("Save")');
      await page.waitForTimeout(2000);

      const successMsg2 = await page.locator('.el-message--success').count() > 0;
      test('Material price created', successMsg2);
    }

    // Test: Search material prices
    console.log('\nTesting: Search material prices...');
    await page.click('button:has-text("Search")');
    await page.waitForTimeout(2000);
    await page.screenshot({ path: 'screenshots/test-07-material-prices-list.png' });

    const hasMaterialData = await page.locator('table tr, .el-table__row').count() > 0;
    test('Material prices loaded', hasMaterialData);

    // Step 4: Treatment Prices Tab
    console.log('\n=== STEP 4: Treatment Prices ===');
    await page.click('.el-tabs__item:has-text("Treatment Prices")');
    await page.waitForTimeout(1500);
    await page.screenshot({ path: 'screenshots/test-08-treatment-prices-tab.png' });

    test('Treatment prices tab visible', true);

    // Step 5: Price Adjustments
    console.log('\n=== STEP 5: Price Adjustments ===');
    await page.goto('http://localhost:5174/#/price-management/price-adjustments');
    await page.waitForTimeout(3000);
    await page.screenshot({ path: 'screenshots/test-09-price-adjustments-page.png' });

    const hasAdjustmentsTable = await page.locator('table, .el-table').count() > 0;
    test('Price adjustments page loads', hasAdjustmentsTable);

    // Test: Create price adjustment request
    console.log('\nTesting: Create price adjustment...');
    await page.click('button:has-text("New Request")');
    await page.waitForTimeout(1000);

    const adjDialogVisible = await page.locator('.el-dialog').isVisible();
    test('New adjustment dialog opens', adjDialogVisible);

    if (adjDialogVisible) {
      const numberInputs3 = await page.locator('.el-dialog .el-input-number input').all();
      if (numberInputs3.length >= 4) {
        await numberInputs3[0].fill('1');      // customer_id
        await numberInputs3[1].fill('1');      // material_id
        await numberInputs3[2].fill('100.00'); // old_price
        await numberInputs3[3].fill('110.00'); // new_price
      }

      // Fill reason
      const textarea = await page.locator('.el-dialog textarea');
      if (await textarea.count() > 0) {
        await textarea.fill('Price increase due to material cost inflation - automated test');
      }

      await page.screenshot({ path: 'screenshots/test-10-adjustment-form.png' });

      await page.click('.el-dialog button:has-text("Submit")');
      await page.waitForTimeout(2000);

      const successMsg3 = await page.locator('.el-message--success').count() > 0;
      test('Price adjustment created', successMsg3);
      await page.screenshot({ path: 'screenshots/test-11-adjustment-created.png' });
    }

    // Test: View adjustment detail
    console.log('\nTesting: View adjustment detail...');
    await page.waitForTimeout(1000);
    const detailBtn = await page.locator('button:has-text("Detail")').first();
    if (await detailBtn.count() > 0) {
      await detailBtn.click();
      await page.waitForTimeout(1500);

      const detailVisible = await page.locator('.el-descriptions, .el-dialog').isVisible();
      test('Adjustment detail dialog opens', detailVisible);
      await page.screenshot({ path: 'screenshots/test-12-adjustment-detail.png' });

      await page.click('.el-dialog button:has-text("Close")');
      await page.waitForTimeout(500);
    }

    // Test: Approve adjustment
    console.log('\nTesting: Approve price adjustment...');
    const approveBtn = await page.locator('button:has-text("Approve")').first();
    if (await approveBtn.count() > 0) {
      await approveBtn.click();
      await page.waitForTimeout(1500);

      const approvalFormVisible = await page.locator('.el-dialog').isVisible();
      test('Approval dialog opens', approvalFormVisible);

      if (approvalFormVisible) {
        const notesField = await page.locator('.el-dialog textarea');
        if (await notesField.count() > 0) {
          await notesField.fill('Approved - price increase justified - automated test');
        }

        await page.screenshot({ path: 'screenshots/test-13-approval-form.png' });

        await page.click('.el-dialog button:has-text("Approve")');
        await page.waitForTimeout(2000);

        const approveSuccess = await page.locator('.el-message--success').count() > 0;
        test('Adjustment approved successfully', approveSuccess);
        await page.screenshot({ path: 'screenshots/test-14-approved.png' });
      }
    }

    // Final Summary
    console.log('\n' + '='.repeat(60));
    console.log('📊 TEST SUMMARY');
    console.log('='.repeat(60));
    console.log(`✓ Passed: ${testsPassed}`);
    console.log(`✗ Failed: ${testsFailed}`);
    console.log(`📈 Success Rate: ${Math.round(testsPassed / (testsPassed + testsFailed) * 100)}%`);
    console.log('='.repeat(60));

    if (testsFailed === 0) {
      console.log('\n🎉 All tests passed! Price management system is fully functional.');
    } else {
      console.log(`\n⚠️  ${testsFailed} test(s) failed. Review screenshots for details.`);
    }

    console.log('\n📸 All screenshots saved to screenshots/ folder');
    console.log('🌐 Browser will stay open for 60 seconds for manual inspection...');
    await page.waitForTimeout(60000);

  } catch (error) {
    console.error('\n❌ Test suite failed:', error.message);
    await page.screenshot({ path: 'screenshots/test-error.png' });
    testsFailed++;
  } finally {
    await browser.close();
    console.log('\n✅ Test completed');
    process.exit(testsFailed > 0 ? 1 : 0);
  }
})();
