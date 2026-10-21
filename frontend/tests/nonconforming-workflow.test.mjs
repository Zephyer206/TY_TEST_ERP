import test from 'node:test'
import assert from 'node:assert/strict'
import { activeStep, businessDate, canAct, completeStep, confirmDefect, draftFrom, editDefect, hasRework, hasReworkHistory, inspectResult as inspectDirect, makeInspectionItem, makeStep, mondayOf, movePriority, normalizeDefect, remainingQty, returnDefect, setMoldReady, startDefect, submitResult as submitDirect, validateDraft } from '../src/domain/nonconforming.ts'

const quality = { name: '品质', dept: 'quality', role_level: 2 }
const sales = { name: '业务', dept: 'sales', role_level: 2 }
const development = { name: '开发', dept: 'engineering', role_level: 2 }
const production = { name: '生产', dept: 'prod', role_level: 1 }
const record = (patch = {}) => normalizeDefect({ id: 'one', no: 'NC-1', company: 'tianyue', customer: '亚太', partNo: 'APG098A', partName: '弹簧片', batchNo: 'B1', source: '厂内检验', quantity: 12000, description: '力值异常', disposition: 'rework', treatment: '调整力值，品质验收', assignee: '生产', priority: 1, plannedDate: '2026-10-17', week: '2026-10-12', status: 'pending_confirmation', moldReady: false, paused: false, acceptedQty: 0, scrappedQty: 0, submission: null, actualDate: '', createdAt: '2026-10-17T01:00:00Z', history: [], ...patch })
const evidenceFor = row => ({ checks: row.inspectionItems.map(item => ({ id: item.id, actual: '复核符合已确认标准', passed: true })), quantityChecked: true, releaseChecked: true })
const finishAll = row => { if (hasRework(row)) row.moldReady = true; while (activeStep(row)) completeStep(row, activeStep(row).id, '本步执行完成', production) }
const submitResult = (row, result, actor) => { finishAll(row); submitDirect(row, result, actor) }
const inspectResult = (row, passed, note, actor) => inspectDirect(row, passed, note, actor, evidenceFor(row))

test('historical source-date closure has no pending work without inventing accepted quantities', () => {
  const row = record({ status: 'closed', actualDate: '2026-10-12', historicalCompletion: { basis: 'source_actual_date', originalActual: '2026-10-12', recordedAt: '2026-10-17T01:00:00Z' } })
  assert.equal(remainingQty(row), 0)
  assert.equal(row.acceptedQty, 0)
  row.status = 'pending_confirmation'
  assert.equal(remainingQty(row), 12000)
})

test('confirm requires a complete disposition and locks editing and ordering', () => {
  const incomplete = record({ treatment: '' })
  assert.throws(() => confirmDefect(incomplete, quality), /确认前/)
  assert.equal(incomplete.status, 'pending_confirmation')
  const row = record()
  confirmDefect(row, quality)
  assert.equal(row.status, 'pending')
  assert.equal(JSON.parse(row.history[0].snapshot).priority, 1)
  assert.throws(() => editDefect(row, { ...row, quantity: 100 }, quality), /锁定/)
  assert.throws(() => movePriority([row], row.id, 1, sales), /锁定/)
})

test('business sorting moves only unconfirmed records and preserves confirmed positions', () => {
  const a = record(), locked = record({ id: 'locked', status: 'pending', priority: 2 }), b = record({ id: 'two', priority: 3 })
  movePriority([a, locked, b], a.id, 1, sales)
  assert.equal(a.priority, 3); assert.equal(b.priority, 1); assert.equal(locked.priority, 2)
  assert.throws(() => movePriority([a, b], a.id, -1, production), /权限/)
})

test('quality, development and sales can return every open confirmed status with a reason', () => {
  for (const actor of [quality, development, sales]) for (const status of ['pending', 'processing', 'inspection']) {
    const row = record({ status, moldReady: true, acceptedQty: 10000, submission: status === 'inspection' ? { good: 1000, scrap: 0, note: '已处理' } : null })
    assert.throws(() => returnDefect(row, ' ', actor), /原因/)
    returnDefect(row, '剩余产品改用其他方案', actor)
    assert.equal(row.status, 'pending_confirmation'); assert.equal(row.paused, true)
    assert.equal(row.acceptedQty, 10000); assert.equal(row.moldReady, true); assert.equal(row.submission, null)
    const snapshot = JSON.parse(row.history[0].snapshot)
    assert.equal(snapshot.status, status); assert.equal(snapshot.acceptedQty, 10000)
    if (status === 'inspection') assert.equal(snapshot.submission.good, 1000)
  }
  assert.throws(() => returnDefect(record({ status: 'processing' }), '调整', production), /权限/)
  for (const status of ['closed', 'pending_confirmation']) assert.throws(() => returnDefect(record({ status }), '调整', quality), /未关闭/)
})

test('only rework waits for a ready mold; sorting, scrap and other can start directly', () => {
  const row = record({ status: 'pending' })
  assert.throws(() => startDefect(row, production), /未就绪/)
  setMoldReady(row, true, development); startDefect(row, production)
  assert.equal(row.status, 'processing')
  for (const disposition of ['sorting', 'scrap', 'other']) {
    const direct = record({ status: 'pending', disposition })
    startDefect(direct, production); assert.equal(direct.status, 'processing')
    assert.throws(() => setMoldReady(direct, true, development), /返工任务/)
  }
})

test('12000-piece case retains partial sorting result and closes only after the rest is confirmed scrapped', () => {
  const row = record({ status: 'processing', disposition: 'sorting' })
  submitResult(row, { good: 10000, scrap: 0, note: '挑选合格一万件' }, quality)
  assert.equal(row.acceptedQty, 0)
  inspectResult(row, true, '按图纸复核通过', quality)
  assert.equal(row.status, 'processing'); assert.equal(remainingQty(row), 2000); assert.equal(row.actualDate, '')
  returnDefect(row, '剩余两千件讨论后报废', sales)
  editDefect(row, { ...row, disposition: 'scrap', treatment: '剩余2000件报废', planSteps: [makeStep('scrap', '核实并执行报废')], inspectionItems: [makeInspectionItem('报废凭据', '报废2000件，核对实物及凭据')] }, quality)
  confirmDefect(row, quality); startDefect(row, production)
  submitResult(row, { good: 0, scrap: 2000, note: '已执行报废' }, production)
  inspectResult(row, true, '报废数量核实无误', quality)
  assert.equal(row.status, 'closed'); assert.equal(row.quantity, 12000)
  assert.equal(row.acceptedQty, 10000); assert.equal(row.scrappedQty, 2000)
  assert.equal(remainingQty(row), 0); assert.equal(row.actualDate, businessDate())
  assert.throws(() => returnDefect(row, '调整', development), /未关闭/)
})

test('failed inspection retains history, counts nothing twice and returns to processing', () => {
  const row = record({ status: 'processing' })
  submitResult(row, { good: 12000, scrap: 0, note: '本次返工完成' }, production)
  inspectResult(row, false, '力值仍偏低', quality)
  assert.equal(row.status, 'processing'); assert.equal(row.acceptedQty, 0); assert.equal(row.actualDate, '')
  assert.ok(row.history.some(item => item.action === '验收不通过' && item.detail.includes('力值仍偏低')))
  submitResult(row, { good: 12000, scrap: 0, note: '再次返工完成' }, production)
  inspectResult(row, true, '复测通过', quality)
  assert.equal(row.acceptedQty, 12000); assert.equal(row.quantity, 12000)
})

test('result quantity and disposition prevent unapproved scrap and impossible closure', () => {
  for (const result of [{ good: 12001, scrap: 0, note: '超量' }, { good: -1, scrap: 1, note: '负数' }, { good: 0, scrap: 0, note: '零' }, { good: 1.2, scrap: 0, note: '小数' }]) assert.throws(() => submitResult(record({ status: 'processing' }), result, production), /数量/)
  assert.throws(() => submitResult(record({ status: 'processing' }), { good: 0, scrap: 100, note: '报废' }, production), /退回待确认/)
  assert.throws(() => submitResult(record({ status: 'processing', disposition: 'scrap' }), { good: 100, scrap: 0, note: '合格' }, production), /只能/)
  assert.throws(() => inspectResult(record({ status: 'inspection', submission: { good: 12000, scrap: 0, note: '已完成' } }), true, '通过', production), /权限/)
})

test('dates stay in the assigned week, invalid dates reject, and resolved quantities cannot be erased', () => {
  assert.equal(mondayOf('2026-10-17'), '2026-10-12'); assert.equal(mondayOf('2026-10-17', 1), '2026-10-19')
  assert.equal(businessDate(new Date('2026-10-16T17:00:00Z')), '2026-10-17')
  assert.throws(() => validateDraft(record({ plannedDate: '2026-10-19' })), /任务周/)
  assert.throws(() => validateDraft(record({ plannedDate: '2026-02-30' })), /日期无效/)
  assert.throws(() => validateDraft(record({ plannedDate: 'invalid' })), /日期无效/)
  assert.throws(() => editDefect(record({ acceptedQty: 10000 }), { ...record(), quantity: 9999 }, quality), /已经验收/)
})

test('role boundaries keep quality acceptance and development readiness separate', () => {
  assert.equal(canAct(quality, 'inspect'), true); assert.equal(canAct(sales, 'inspect'), false)
  assert.equal(canAct(sales, 'priority'), true); assert.equal(canAct(development, 'priority'), false)
  assert.equal(canAct(development, 'prepare'), true); assert.equal(canAct(production, 'prepare'), false)
  assert.equal(canAct(production, 'start'), true); assert.equal(canAct(sales, 'create'), false)
})

test('other dispositions resolve their own quantity without misreporting it as qualified or scrapped', () => {
  const row = record({ status: 'processing', disposition: 'other' })
  assert.throws(() => submitResult(row, { good: 12000, scrap: 0, note: '退回供应商' }, production), /按方案/)
  submitResult(row, { good: 0, scrap: 0, other: 12000, note: '依确认方案退回供应商' }, production)
  inspectResult(row, true, '核实处置完成', quality)
  assert.equal(row.status, 'closed'); assert.equal(row.otherQty, 12000)
  assert.equal(row.acceptedQty, 0); assert.equal(row.scrappedQty, 0); assert.equal(remainingQty(row), 0)
})

test('combined plan executes in order and only the rework step waits for a mold', () => {
  const row = record({ planSteps: [makeStep('sorting', '挑变形'), makeStep('rework', '修正尺寸'), makeStep('postprocess', '补标识')] })
  confirmDefect(row, quality); startDefect(row, production)
  assert.throws(() => completeStep(row, row.planSteps[1].id, '跳步', production), /顺序/)
  assert.throws(() => submitDirect(row, { good: 12000, scrap: 0, note: '提前提交' }, production), /全部处理步骤/)
  completeStep(row, row.planSteps[0].id, '挑选完成', quality)
  assert.equal(row.acceptedQty, 0)
  assert.throws(() => completeStep(row, row.planSteps[1].id, '返工', production), /未就绪/)
  assert.throws(() => setMoldReady(row, true, production), /权限/)
  setMoldReady(row, true, development)
  completeStep(row, row.planSteps[1].id, '返工完成', production)
  assert.throws(() => setMoldReady(row, false, development), /已完成/)
  completeStep(row, row.planSteps[2].id, '标识完成', production)
  submitDirect(row, { good: 12000, scrap: 0, note: '三步完成' }, production)
  assert.equal(row.acceptedQty, 0); assert.equal(row.quantity, 12000)
  inspectDirect(row, true, '符合标准', quality, evidenceFor(row))
  assert.equal(row.status, 'closed'); assert.equal(row.acceptedQty, 12000)
})

test('inspection requires every item, actual measurements, quantity check and release check', () => {
  const row = record({ status: 'processing', inspectionItems: [makeInspectionItem('力值', '12–16.5N'), makeInspectionItem('开口', '7.7±0.2')] })
  row.release.mode = 'concession'; row.release.basis = '客户批准单示例'; row.release.approvedBy = '客户品质'
  submitResult(row, { good: 12000, scrap: 0, note: '处理完成' }, production)
  const evidence = evidenceFor(row)
  assert.throws(() => inspectDirect(row, true, '通过', quality), /实物数量/)
  assert.throws(() => inspectDirect(row, true, '通过', quality, { ...evidence, checks: evidence.checks.slice(0, 1) }), /每个项目/)
  for (const bad of [{ ...evidence.checks[1], passed: false }, { ...evidence.checks[1], actual: ' ' }, { ...evidence.checks[1], id: evidence.checks[0].id }]) {
    assert.throws(() => inspectDirect(row, true, '通过', quality, { ...evidence, checks: [evidence.checks[0], bad] }), /每个项目/)
  }
  assert.throws(() => inspectDirect(row, true, '通过', quality, { ...evidence, releaseChecked: false }), /放行及发货/)
  assert.equal(row.status, 'inspection'); assert.equal(row.acceptedQty, 0); assert.equal(row.actualDate, '')
  inspectDirect(row, true, '核对通过', quality, evidence)
  const saved = JSON.parse(row.history[0].snapshot)
  assert.equal(saved.inspection.checks.length, 2); assert.equal(saved.release.basis, '客户批准单示例')
  assert.equal(saved.submission.good, 12000); assert.ok(saved.planSteps.every(step => step.completedAt))
})

test('partial and failed inspection restart steps without duplicating accepted totals', () => {
  const row = record({ status: 'processing', planSteps: [makeStep('sorting', '挑选'), makeStep('rework', '返工')] })
  submitResult(row, { good: 10000, scrap: 0, note: '先完成一万件' }, production)
  inspectDirect(row, true, '一万件通过', quality, evidenceFor(row))
  assert.equal(remainingQty(row), 2000); assert.ok(row.planSteps.every(step => !step.completedAt))
  assert.throws(() => submitDirect(row, { good: 2000, scrap: 0, note: '未重做步骤' }, production), /全部处理步骤/)
  submitResult(row, { good: 2000, scrap: 0, note: '剩余完成' }, production)
  inspectDirect(row, false, '剩余尺寸不通过', quality, { checks: [], quantityChecked: false, releaseChecked: false })
  assert.equal(row.acceptedQty, 10000); assert.ok(row.planSteps.every(step => !step.completedAt))
  assert.ok(row.history.some(entry => entry.action === '验收不通过' && JSON.parse(entry.snapshot).submission.good === 2000))
})

test('forecast stays out of actual totals and quantity lots reconcile to the current physical quantity', () => {
  const row = record()
  row.trace.expectedReturnQty = 100000; row.trace.productState = '老状态'; row.trace.marking = '无字码'
  row.quantityLots = [{ id: 'a', batch: '原库存', container: 'X1', quantity: 6300, note: '已核对不重叠' }, { id: 'b', batch: '本次退货', container: 'X2', quantity: 5700, note: '' }]
  validateDraft(row); assert.equal(row.quantity, 12000); assert.equal(remainingQty(row), 12000)
  row.quantityLots[1].quantity = 3700
  assert.throws(() => validateDraft(row), /分项合计/)
  row.quantityLots = []; row.trace.expectedReturnQty = -1
  assert.throws(() => validateDraft(row), /预计退货/)
})

test('return and edit retain accepted totals and snapshots but cannot inject execution fields', () => {
  const row = record({ status: 'processing', acceptedQty: 10000, moldReady: true })
  completeStep(row, activeStep(row).id, '剩余返工开始', production)
  returnDefect(row, '客户更改发货标识', sales)
  assert.equal(JSON.parse(row.history[0].snapshot).planSteps[0].result, '剩余返工开始')
  const draft = draftFrom(row); draft.release.labeling = '更改后的标签'
  editDefect(row, { ...draft, acceptedQty: 0, status: 'closed', priority: 99, moldReady: false, planSteps: draft.planSteps.map(step => ({ ...step, completedAt: 'forged' })) }, quality)
  assert.equal(row.acceptedQty, 10000); assert.equal(row.status, 'pending_confirmation'); assert.equal(row.priority, 1); assert.equal(row.moldReady, true)
  assert.equal(row.planSteps[0].completedAt, '')
  confirmDefect(row, quality); assert.equal(row.status, 'pending'); assert.equal(row.release.labeling, '更改后的标签')
})

test('confirmation requires explicit standards and concession approval; scrap cannot mix with rework', () => {
  assert.throws(() => confirmDefect(record({ inspectionItems: [] }), quality), /验收项目/)
  assert.throws(() => confirmDefect(record({ planSteps: [makeStep('rework', '')] }), quality), /每个处理步骤/)
  const row = record(); row.release.mode = 'concession'
  assert.throws(() => confirmDefect(row, quality), /批准依据/)
  row.release.basis = '客户批准单'; row.release.approvedBy = '客户品质'; confirmDefect(row, quality)
  assert.throws(() => confirmDefect(record({ planSteps: [makeStep('rework', '调整'), makeStep('scrap', '报废')] }), quality), /单独方案/)
})

test('legacy migration preserves quantities, ready molds, existing history and closed dates', () => {
  const old = { ...record({ status: 'closed', acceptedQty: 12000, actualDate: '2026-10-10', moldReady: true }) }
  for (const key of ['trace', 'release', 'quantityLots', 'planSteps', 'inspectionItems']) delete old[key]
  const migrated = normalizeDefect(old)
  assert.equal(migrated.acceptedQty, 12000); assert.equal(migrated.actualDate, '2026-10-10'); assert.equal(migrated.moldReady, true)
  assert.equal(migrated.trace.expectedReturnQty, 0); assert.equal(migrated.planSteps[0].kind, 'rework')
  assert.ok(migrated.planSteps[0].completedAt); assert.equal(migrated.inspectionItems[0].standard, old.treatment)
})

test('mold traceability still finds prior rework after the remaining quantity changes to scrap', () => {
  const row = record({ status: 'processing', acceptedQty: 10000, moldReady: true })
  returnDefect(row, '剩余报废', quality)
  editDefect(row, { ...draftFrom(row), disposition: 'scrap', planSteps: [makeStep('scrap', '剩余报废')] }, quality)
  assert.equal(hasRework(row), false); assert.equal(hasReworkHistory(row), true)
  assert.equal(hasReworkHistory(record({ disposition: 'sorting' })), false)
})
