const { chromium } = require('playwright');

(async () => {
  console.log('🚀 Starting detailed login test...\n');

  const browser = await chromium.launch({
    headless: false,
    slowMo: 500
  });

  const context = await browser.newContext();
  const page = await context.newPage();

  // Capture console messages
  const consoleMessages = [];
  page.on('console', msg => {
    const text = msg.text();
    consoleMessages.push({ type: msg.type(), text });
    console.log(`[Browser ${msg.type()}]:`, text);
  });

  // Capture network requests
  const networkRequests = [];
  page.on('request', request => {
    networkRequests.push({
      method: request.method(),
      url: request.url(),
      postData: request.postData()
    });
  });

  page.on('response', async response => {
    const url = response.url();
    if (url.includes('/auth/login')) {
      console.log(`\n📡 Login API Response:`);
      console.log(`   Status: ${response.status()}`);
      console.log(`   URL: ${url}`);
      try {
        const body = await response.json();
        console.log(`   Body:`, JSON.stringify(body, null, 2));
      } catch (e) {
        console.log(`   Body: (not JSON)`);
      }
    }
  });

  try {
    // Navigate to frontend
    console.log('📂 Opening http://localhost:5174...\n');
    await page.goto('http://localhost:5174');
    await page.waitForTimeout(2000);
    await page.screenshot({ path: 'screenshots/detailed-01-homepage.png' });

    // Fill login form
    console.log('📝 Filling login form...');
    await page.fill('input[placeholder*="用户名"], input[type="text"]', 'admin');
    await page.fill('input[type="password"]', '123456');
    await page.screenshot({ path: 'screenshots/detailed-02-filled.png' });
    console.log('✅ Form filled\n');

    // Check localStorage before login
    const tokenBefore = await page.evaluate(() => localStorage.getItem('token'));
    console.log('🔐 Token before login:', tokenBefore || '(none)');

    // Click login
    console.log('\n🔐 Clicking login button...');
    await page.click('button:has-text("登录")');

    // Wait for network and DOM updates
    await page.waitForTimeout(3000);

    // Check localStorage after login
    const tokenAfter = await page.evaluate(() => localStorage.getItem('token'));
    const userInfo = await page.evaluate(() => localStorage.getItem('userInfo'));
    console.log('\n📦 LocalStorage after login:');
    console.log('   Token:', tokenAfter ? `${tokenAfter.substring(0, 50)}...` : '(none)');
    console.log('   UserInfo:', userInfo || '(none)');

    await page.screenshot({ path: 'screenshots/detailed-03-after-login.png' });

    // Check current URL
    const currentUrl = page.url();
    console.log('\n📍 Current URL:', currentUrl);

    // Check for error messages
    const errorElements = await page.locator('.el-message--error').count();
    const successElements = await page.locator('.el-message--success').count();
    console.log('❌ Error messages:', errorElements);
    console.log('✅ Success messages:', successElements);

    if (errorElements > 0) {
      const errorText = await page.locator('.el-message--error').allTextContents();
      console.log('   Error text:', errorText);
    }

    if (successElements > 0) {
      const successText = await page.locator('.el-message--success').allTextContents();
      console.log('   Success text:', successText);
    }

    // Wait a bit more for any delayed redirects
    console.log('\n⏳ Waiting 5 seconds for any delayed redirects...');
    await page.waitForTimeout(5000);

    const finalUrl = page.url();
    console.log('📍 Final URL:', finalUrl);
    await page.screenshot({ path: 'screenshots/detailed-04-final.png' });

    // Summary
    console.log('\n📊 Test Summary:');
    console.log('   Login API called:', networkRequests.some(r => r.url.includes('/auth/login')));
    console.log('   Token stored:', !!tokenAfter);
    console.log('   Redirected:', finalUrl !== 'http://localhost:5174/login');
    console.log('   Console errors:', consoleMessages.filter(m => m.type === 'error').length);

    if (consoleMessages.filter(m => m.type === 'error').length > 0) {
      console.log('\n❌ Console Errors:');
      consoleMessages.filter(m => m.type === 'error').forEach(m => {
        console.log(`   - ${m.text}`);
      });
    }

    console.log('\n🌐 Browser will stay open for 60 seconds...');
    await page.waitForTimeout(60000);

  } catch (error) {
    console.error('\n❌ Test failed:', error.message);
    await page.screenshot({ path: 'screenshots/detailed-error.png' });
    await page.waitForTimeout(60000);
  } finally {
    await browser.close();
  }
})();
