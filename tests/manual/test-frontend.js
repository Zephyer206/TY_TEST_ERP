const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext();
  const page = await context.newPage();

  console.log('Opening frontend...');
  await page.goto('http://localhost:5173');

  // Wait for page to load
  await page.waitForTimeout(2000);

  // Take screenshot
  await page.screenshot({ path: 'frontend-homepage.png' });
  console.log('Screenshot saved: frontend-homepage.png');

  // Check if login page is visible
  const hasLoginForm = await page.locator('input[type="text"], input[type="password"]').count() > 0;
  console.log('Has login form:', hasLoginForm);

  // Try to login with test credentials (if login page)
  if (hasLoginForm) {
    console.log('Attempting login with admin/123456...');
    try {
      await page.fill('input[type="text"]', 'admin');
      await page.fill('input[type="password"]', '123456');
      await page.click('button[type="submit"], button:has-text("登录"), button:has-text("Login")');
      await page.waitForTimeout(2000);
      console.log('Login attempted');
    } catch (e) {
      console.log('Login error:', e.message);
    }
  }

  // Check for navigation elements
  const navItems = await page.locator('nav, .el-menu, .sidebar').count();
  console.log('Navigation elements found:', navItems);

  console.log('\nBrowser opened. You can now manually test:');
  console.log('1. Login with admin credentials');
  console.log('2. Navigate to 报价管理 (Quotes)');
  console.log('3. Click 新建报价 button');
  console.log('4. Test the parts dropdown search');
  console.log('5. Verify "客户件号" label is correct');
  console.log('\nPress Ctrl+C to close browser and exit.');

  // Keep browser open for manual testing
  await page.waitForTimeout(300000); // 5 minutes

  await browser.close();
})();
