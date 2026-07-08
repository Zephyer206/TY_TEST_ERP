const { chromium } = require('playwright');

(async () => {
  console.log('🚀 Starting login test...\n');

  const browser = await chromium.launch({
    headless: false,
    slowMo: 500  // Slow down by 500ms for visibility
  });

  const context = await browser.newContext();
  const page = await context.newPage();

  try {
    // Step 1: Navigate to frontend
    console.log('📂 Opening http://localhost:5174...');
    await page.goto('http://localhost:5174');
    await page.waitForTimeout(2000);
    await page.screenshot({ path: 'screenshots/01-homepage.png' });
    console.log('✅ Page loaded\n');

    // Step 2: Check if we're on login page
    console.log('🔍 Looking for login form...');
    const usernameInput = page.locator('input[placeholder*="用户名"], input[type="text"]').first();
    const passwordInput = page.locator('input[type="password"]').first();
    const loginButton = page.locator('button:has-text("登录")').first();

    const hasLoginForm = await usernameInput.count() > 0;
    if (!hasLoginForm) {
      console.log('❌ No login form found! Current URL:', page.url());
      await page.screenshot({ path: 'screenshots/error-no-login-form.png' });
      throw new Error('Login form not found');
    }
    console.log('✅ Login form found\n');

    // Step 3: Fill in credentials
    console.log('📝 Filling credentials (admin/123456)...');
    await usernameInput.fill('admin');
    await passwordInput.fill('123456');
    await page.screenshot({ path: 'screenshots/02-credentials-filled.png' });
    console.log('✅ Credentials filled\n');

    // Step 4: Submit login
    console.log('🔐 Clicking login button...');
    await loginButton.click();

    // Wait for navigation or error message
    await page.waitForTimeout(3000);
    await page.screenshot({ path: 'screenshots/03-after-login-click.png' });

    // Step 5: Check if login was successful
    const currentUrl = page.url();
    console.log('📍 Current URL:', currentUrl);

    // Check for error messages
    const errorMessages = await page.locator('.el-message--error, .error, [class*="error"]').allTextContents();
    if (errorMessages.length > 0) {
      console.log('❌ Error messages found:', errorMessages);
      await page.screenshot({ path: 'screenshots/error-login-failed.png' });
      throw new Error('Login failed with error: ' + errorMessages.join(', '));
    }

    // Check if redirected to dashboard
    if (currentUrl.includes('/dashboard') || currentUrl.includes('/home')) {
      console.log('✅ Login successful! Redirected to:', currentUrl);
      await page.screenshot({ path: 'screenshots/04-dashboard.png' });
    } else if (currentUrl.includes('/login')) {
      console.log('⚠️  Still on login page. Checking console errors...');

      // Capture console errors
      page.on('console', msg => {
        if (msg.type() === 'error') {
          console.log('Console error:', msg.text());
        }
      });

      // Check network tab for failed requests
      const failedRequests = [];
      page.on('requestfailed', request => {
        failedRequests.push({
          url: request.url(),
          failure: request.failure()
        });
      });

      await page.waitForTimeout(2000);

      if (failedRequests.length > 0) {
        console.log('❌ Failed network requests:');
        failedRequests.forEach(req => {
          console.log(`  - ${req.url}: ${req.failure}`);
        });
      }

      throw new Error('Login did not redirect - still on login page');
    } else {
      console.log('⚠️  Redirected to unexpected page:', currentUrl);
      await page.screenshot({ path: 'screenshots/04-unexpected-page.png' });
    }

    // Step 6: Check for main navigation elements
    console.log('\n🔍 Checking for navigation elements...');
    const navElements = await page.locator('nav, .el-menu, .sidebar, [class*="menu"]').count();
    console.log('Navigation elements found:', navElements);

    if (navElements > 0) {
      console.log('✅ Navigation found - user is logged in\n');
    } else {
      console.log('⚠️  No navigation found - may not be fully logged in\n');
    }

    // Step 7: Keep browser open for manual inspection
    console.log('✅ Test completed successfully!');
    console.log('\n📸 Screenshots saved to screenshots/ folder');
    console.log('🌐 Browser will stay open for 60 seconds for manual inspection...');
    console.log('   Press Ctrl+C to close immediately\n');

    await page.waitForTimeout(60000);

  } catch (error) {
    console.error('\n❌ Test failed:', error.message);
    await page.screenshot({ path: 'screenshots/error-final.png' });
    console.log('📸 Error screenshot saved: screenshots/error-final.png\n');

    // Keep browser open to inspect the error
    console.log('🌐 Browser will stay open for 60 seconds to inspect error...');
    await page.waitForTimeout(60000);
  } finally {
    await browser.close();
    console.log('✅ Browser closed');
  }
})();
