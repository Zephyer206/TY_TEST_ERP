// Read-only acceptance for the Windows cloud launcher. No business writes.
const assert = require('node:assert/strict')
const { chromium } = require('playwright')

async function main() {
  const baseURL = process.env.ZEPHYR_TEST_URL || 'http://127.0.0.1:8080'
  const browser = await chromium.launch({ headless: true })
  try {
    const context = await browser.newContext({ baseURL })
    const page = await context.newPage()
    const errors = []
    const foreignRequests = []
    page.on('pageerror', error => errors.push(error.name))
    page.on('request', request => {
      const url = new URL(request.url())
      if (url.protocol.startsWith('http') && url.origin !== new URL(baseURL).origin) {
        foreignRequests.push(url.origin)
      }
    })
    const waitForParts = () => page.waitForResponse(response => {
      const path = new URL(response.url()).pathname
      return path.startsWith('/api/v1/parts') && response.request().method() === 'GET'
    }, { timeout: 60000 })
    const partsResponse = waitForParts()
    const navigation = await page.goto('/parts', { waitUntil: 'domcontentloaded' })
    assert.equal(navigation.status(), 200, 'Direct Vue route returns HTML')
    const response = await partsResponse
    assert.equal(response.status(), 200, 'Parts API works through the same port')
    assert.match(response.headers()['content-type'], /application\/json/)
    const data = await response.json()
    assert.ok(Array.isArray(data.items), 'Parts response has items')
    await page.locator('.el-table__body-wrapper tbody tr').first().waitFor({ timeout: 30000 })
    const refreshedParts = waitForParts()
    await page.reload({ waitUntil: 'domcontentloaded' })
    assert.equal((await refreshedParts).status(), 200, 'Refresh preserves SPA routing and API access')
    const root = await context.request.get('/')
    assert.match(root.headers()['content-type'], /text\/html/)
    const asset = await page.locator('script[type="module"][src]').first().getAttribute('src')
    assert.equal((await context.request.get(asset)).status(), 200, 'Built JS asset is served')
    for (const path of ['/api/v1/__cloud_missing__', '/uploads/__cloud_missing__.txt', '/assets/__cloud_missing__.js']) {
      const missing = await context.request.get(path, { headers: { Accept: 'text/html' } })
      assert.equal(missing.status(), 404, 'Missing API/file must not return SPA HTML')
    }
    assert.deepEqual(foreignRequests, [], 'Frontend must not contact development ports or foreign hosts')
    assert.deepEqual(errors, [], 'No browser runtime errors')
    console.log(JSON.stringify({
      result: 'PASS', browser: 'Playwright Chromium ' + browser.version(),
      checks: ['direct-route', 'parts-data', 'page-refresh', 'root-html', 'built-js', 'missing-api-and-files', 'same-origin', 'no-runtime-errors'],
    }))
  } finally { await browser.close() }
}

main().catch(error => { console.error(error.message); process.exitCode = 1 })
