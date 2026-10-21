/** Read-only acceptance of source-date completion against the deployed database-backed service. */
import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import path from 'node:path'
import { createRequire } from 'node:module'
const require = createRequire(import.meta.url)
const { chromium } = require(process.argv[2] || 'playwright')
const base = process.env.ZEPHYR_TEST_URL || 'http://127.0.0.1:8080'
const output = path.resolve('runtime/acceptance/nonconforming-completion')
await fs.mkdir(output, { recursive: true })
const browser = await chromium.launch({ headless: true, args: ['--disable-gpu', '--renderer-process-limit=2'], ...(process.argv[3] ? { executablePath: process.argv[3] } : {}) })
const context = await browser.newContext({ viewport: { width: 1440, height: 1050 }, locale: 'zh-CN', timezoneId: 'Asia/Shanghai' })
const page = await context.newPage()
page.setDefaultTimeout(15000)
const errors = [], passed = []
page.on('pageerror', error => errors.push(error.message))
const log = message => { passed.push(message); console.log(`PASS ${message}`) }
const detail = () => page.locator('.quality-drawer:visible')
async function closeDetail() { await detail().getByRole('button', { name: '关闭详情', exact: true }).click(); await detail().waitFor({ state: 'hidden' }); await page.mouse.move(100, 150); await page.keyboard.press('Escape') }
try {
  const response = await context.request.get(`${base}/api/v1/nonconforming?company=tianyue`)
  assert.equal(response.status(), 200)
  const data = await response.json()
  const closed = data.records.filter(row => row.status === 'closed')
  const pending = data.records.filter(row => row.status === 'pending_confirmation')
  assert.equal(data.records.length, 105); assert.equal(closed.length, 37); assert.equal(pending.length, 68)
  assert.ok(closed.every(row => row.actualDate === row.importInfo.originalActual && row.historicalCompletion?.basis === 'source_actual_date' && row.acceptedQty === 0 && row.scrappedQty === 0 && row.otherQty === 0 && row.history[0].action === '按原表完成日期结案'))
  assert.ok(pending.every(row => !row.actualDate && !row.historicalCompletion))
  assert.equal(data.records.filter(row => !row.quantityVerified).length, 6)
  assert.equal(data.records.filter(row => row.quantityVerified).reduce((sum, row) => sum + row.quantity, 0), 747197)
  log('数据库105条中37条已按原表实际完成日期结案，68条保留待确认；数量及既有历史未改写')
  await page.goto(`${base}/nonconforming?scope=imported&company=tianyue`)
  await page.getByText('Excel 数据已入库', { exact: true }).waitFor()
  assert.match(await page.locator('.quality-import-summary').innerText(), /37 条已按实际完成日期结案/)
  await page.getByRole('button', { name: /^已关闭\s*37$/ }).click()
  assert.match(await page.locator('.quality-toolbar-total').innerText(), /共 37 条/)
  assert.equal(await page.locator('.quality-ledger .el-table__body tr').count(), 20)
  assert.match(await page.locator('.quality-ledger .el-table__body tr').first().innerText(), /已关闭[\s\S]*实际 2026-09-12/)
  await page.getByRole('button', { name: closed[0].partNo, exact: true }).first().click()
  await detail().getByText('已按原表实际完成日期结案（历史记录）', { exact: true }).waitFor()
  assert.match(await detail().innerText(), /不再计入待处理数量/)
  assert.match(await detail().innerText(), /历史方案参考，执行明细未补录/)
  assert.equal(await detail().locator('.quality-flow').count(), 0)
  for (const name of ['退回待确认', '编辑与讨论', '确认方案', '开始处理', '提交品质验收', '品质验收']) {
    assert.equal(await detail().getByRole('button', { name, exact: true }).count(), 0)
  }
  await page.screenshot({ path: path.join(output, 'historical-completed-detail.png'), animations: 'disabled' })
  await closeDetail()
  log('已关闭筛选显示37条；详情显示原完成日期及结案依据，不再要求执行或品质验收')
  await page.getByRole('button', { name: /^待确认\s*68$/ }).click()
  await page.getByRole('textbox', { name: '搜索不良记录', exact: true }).fill('APG098A')
  assert.match(await page.locator('.quality-ledger .el-table__body tr').innerText(), /待确认/)
  assert.match(await page.locator('.quality-ledger .el-table__body tr').innerText(), /正在返/)
  await page.getByRole('button', { name: 'APG098A', exact: true }).click()
  assert.equal(await detail().getByText('已按原表实际完成日期结案（历史记录）', { exact: true }).count(), 0)
  await detail().getByRole('button', { name: '确认方案', exact: true }).waitFor()
  await detail().locator('.el-drawer__close-btn').click(); await detail().waitFor({ state: 'hidden' })
  log('正在返工的APG098A仍为待确认，12000件与操作入口保留；进展文字未误判为完成日期')
  const uncertain = closed.find(row => !row.quantityVerified)
  await page.goto(`${base}/nonconforming?scope=imported&company=tianyue&record=${encodeURIComponent(uncertain.id)}`)
  await detail().getByText('已按原表实际完成日期结案（历史记录）', { exact: true }).waitFor()
  assert.match(await detail().innerText(), /数量未核实/)
  assert.equal(await detail().locator('.quality-result-grid').count(), 0)
  await closeDetail()
  log('两条数量待核对的历史完成记录保留数量提示，未虚构验收数量')
  const other = await browser.newContext({ viewport: { width: 390, height: 844 }, locale: 'zh-CN' })
  const mobile = await other.newPage(); mobile.on('pageerror', error => errors.push(error.message))
  await mobile.goto(`${base}/nonconforming?scope=imported&company=tianyue`)
  await mobile.getByRole('button', { name: /^已关闭\s*37$/ }).click()
  assert.match(await mobile.locator('.quality-toolbar-total').innerText(), /共 37 条/)
  assert.equal(await mobile.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true)
  await mobile.screenshot({ path: path.join(output, 'completed-mobile.png'), animations: 'disabled' })
  log('独立手机会话读取相同37条已关闭结果，无整页横向溢出')
  assert.deepEqual(errors, [])
  await fs.writeFile(path.join(output, 'browser-report.json'), JSON.stringify({ base, browser: browser.version(), passed, errors }, null, 2))
} catch (error) {
  await page.screenshot({ path: path.join(output, 'failure.png'), animations: 'disabled' }).catch(() => {})
  throw error
} finally { await browser.close() }
