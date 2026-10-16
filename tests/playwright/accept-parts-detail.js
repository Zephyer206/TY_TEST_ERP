const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  const errors = [];
  const responses = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('response', response => {
    if (response.url().includes('/api/v1/parts')) responses.push({ url: response.url(), status: response.status() });
  });
  await page.goto('http://127.0.0.1:5173/login');
  await page.locator('input[placeholder*="用户名"], input[type="text"]').first().fill('admin');
  await page.locator('input[type="password"]').fill('123456');
  await page.locator('button:has-text("登录")').click();
  await page.waitForURL(/dashboard|parts/, { timeout: 10000 });
  await page.goto('http://127.0.0.1:5173/parts');
  await page.waitForTimeout(5000);
  const rows = page.locator('.el-table__row');
  const rowCount = await rows.count();
  if (rowCount) {
    await rows.first().click();
    await page.waitForTimeout(3000);
  }
  const body = await page.locator('body').innerText();
  console.log(JSON.stringify({ url: page.url(), rowCount, body: body.slice(0, 5000), responses, errors }, null, 2));
  await browser.close();
  if (!rowCount || errors.length || responses.some(item => item.status >= 500)) process.exit(1);
})();
