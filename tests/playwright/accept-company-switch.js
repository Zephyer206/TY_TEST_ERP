const { chromium } = require('playwright')

async function chooseCompany(page, selector, label) {
  await page.locator(selector).first().click()
  await page.locator('.el-select-dropdown__item:visible').filter({ hasText: label }).first().click()
  await page.waitForTimeout(500)
}

(async () => {
  console.log('acceptance-start')
  const browser = await chromium.launch({ headless: true })
  const context = await browser.newContext({ viewport: { width: 390, height: 844 } })
  const page = await context.newPage()
  const consoleErrors = []
  const pageErrors = []
  page.on('console', (message) => { if (message.type() === 'error') consoleErrors.push(message.text()) })
  page.on('pageerror', (error) => pageErrors.push(error.message))

  console.log('browser-started')
  await page.goto('http://127.0.0.1:5173/login', { waitUntil: 'domcontentloaded', timeout: 10000 })
  console.log('login-loaded')
  await page.locator('input[placeholder*="用户名"], input[type="text"]').first().fill('admin')
  await page.locator('input[type="password"]').fill('123456')
  await page.locator('button:has-text("登录")').first().click()
  console.log('login-submitted')
  await page.waitForURL(/dashboard|parts/, { timeout: 10000 })
  console.log('login-complete')

  const pages = []
  await page.goto('http://127.0.0.1:5173/parts', { waitUntil: 'domcontentloaded', timeout: 10000 })
  await page.waitForTimeout(700)
  pages.push({ route: 'parts-tianyue', url: page.url(), company: await page.locator('.brand-name').innerText() })
  await page.locator('.brand-lockup').click()
  await page.waitForURL('**/after-sales')
  pages.push({ route: 'header-gaibo-switch', url: page.url(), company: await page.locator('.brand-name').innerText(), storage: await page.evaluate(() => localStorage.getItem('zephyr-company')) })

  await page.goto('http://127.0.0.1:5173/after-sales', { waitUntil: 'domcontentloaded', timeout: 10000 })
  await page.waitForTimeout(700)
  pages.push({ route: 'after-sales-gaibo', url: page.url(), company: await page.locator('.company-navigation .el-select').first().innerText(), types: await page.locator('.company-navigation .el-segmented *').allInnerTexts() })
  const recordLink = page.locator('.record-link').first()
  if (await recordLink.count()) {
    await recordLink.click()
    await page.waitForTimeout(500)
    await page.locator('button:has-text("编辑档案")').click()
    pages.push({ route: 'detail-editing', sectionTitleInputs: await page.locator('[aria-label="核心字段区块标题"]').count(), fieldTitleInputs: await page.locator('[aria-label$="标题"]').count() })
  }
  await page.locator('[aria-label="打开视图设置"]').click()
  pages.push({ route: 'header-edit-settings', titleInputs: await page.locator('.view-settings-drawer input[aria-label$="显示名称"]').count() })
  await page.locator('.view-settings-drawer .el-button').filter({ hasText: '取消' }).click()
  await page.locator('.brand-lockup').click()
  await page.waitForURL('**/parts')
  pages.push({ route: 'header-tianyue-switch', url: page.url(), company: await page.locator('.brand-name').innerText(), storage: await page.evaluate(() => localStorage.getItem('zephyr-company')) })

  await page.goto('http://127.0.0.1:5173/tooling', { waitUntil: 'domcontentloaded', timeout: 10000 })
  await page.waitForTimeout(700)
  const metrics = async () => ({ company: await page.locator('.filter-controls .el-select').first().innerText(), rows: await page.locator('.el-table__body-wrapper tbody tr').count(), scrollWidth: await page.evaluate(() => document.documentElement.scrollWidth), clientWidth: await page.evaluate(() => document.documentElement.clientWidth) })
  pages.push({ route: 'tooling-tianyue', ...(await metrics()) })
  await chooseCompany(page, '.filter-controls .el-select', '盖博')
  pages.push({ route: 'tooling-gaibo', ...(await metrics()) })

  console.log(JSON.stringify({ pages, consoleErrors, pageErrors }, null, 2))
  await browser.close()
  if (consoleErrors.length || pageErrors.length || pages.some((item) => item.scrollWidth > item.clientWidth)) process.exit(1)
})().catch((error) => { console.error(error); process.exit(1) })
