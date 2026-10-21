import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { mergeWorkbookPreview } from '../src/domain/nonconformingImport.ts'
import { draftFrom, editDefect, validateDraft } from '../src/domain/nonconforming.ts'
const bundle = JSON.parse(fs.readFileSync(new URL('../src/data/nonconforming-workbook.json', import.meta.url), 'utf8'))
const imported = () => mergeWorkbookPreview({ version: 1, records: [], molds: [] }, bundle).records

test('106 source rows reconcile to 105 records, with two cross-sheet duplicates merged and one shape split', () => {
  assert.equal(bundle.sourceRows, 106); assert.equal(bundle.uniqueRows, 104); assert.equal(bundle.records.length, 105)
  assert.equal(bundle.mergedDuplicateRows, 2); assert.equal(bundle.splitRows, 1)
  const sourceRefs = new Set(bundle.records.flatMap(row => row.importInfo.sources.map(ref => `${ref.sheet}!${ref.row}`)))
  assert.equal(sourceRefs.size, 106)
  const duplicate = bundle.records.find(row => row.no === 'NC-XLS-SPR-042')
  assert.deepEqual(duplicate.importInfo.sources.map(ref => [ref.sheet, ref.row]), [['弹簧片', 44], ['盖博不良品返工', 4]])
  for (const row of bundle.records) assert.equal(Object.keys(row.importInfo.raw).length, 12)
})

test('mixed states and numeric part numbers are normalized without changing identifiers or force criteria', () => {
  const a = imported().find(row => row.partNo === 'APG098A')
  assert.equal(a.quantity, 12000); assert.equal(a.quantityVerified, true); assert.equal(a.trace.productState, '新状态')
  assert.equal(a.inspectionItems.length, 3); assert.equal(a.release.destination, '安吉'); assert.match(a.release.packing, /箱子底部/)
  assert.equal(a.importInfo.raw['数量'], '12000 新状态')
  const old = imported().find(row => row.no === 'NC-XLS-SPR-045')
  assert.equal(old.quantity, 4000); assert.equal(old.trace.marking, '无字码')
  assert.ok(bundle.records.some(row => row.partNo === '00495308950'))
  assert.ok(bundle.records.some(row => row.partNo === '10027206'))
  assert.equal(bundle.records.find(row => row.no === 'NC-XLS-SPR-053').planSteps.map(step => step.kind).join(','), 'sorting,rework,postprocess')
  assert.equal(bundle.records.find(row => row.no === 'NC-XLS-SPR-052').planSteps.some(step => step.kind === 'rework'), false)
  assert.deepEqual(bundle.records.find(row => row.no === 'NC-XLS-SPR-019').planSteps.map(step => step.kind), ['postprocess', 'sorting'])
})

test('six unclear quantities stay flagged; forecasts, blank values and different product shapes do not inflate known totals', () => {
  const rows = imported()
  assert.equal(rows.filter(row => !row.quantityVerified).length, 6)
  const forecast = rows.find(row => row.partNo === '38013738')
  assert.equal(forecast.quantity, 3000); assert.equal(forecast.trace.expectedReturnQty, 100000); assert.equal(forecast.quantityVerified, false)
  const blank = rows.find(row => row.partNo === '113121-40020-B')
  assert.equal(blank.quantity, 0); assert.equal(blank.quantityVerified, false)
  const split = rows.filter(row => row.partNo === '05.E443.92-2')
  assert.equal(split.length, 2); assert.deepEqual(split.map(row => row.quantity), [10000, 1000])
  assert.deepEqual(split.map(row => row.trace.stockForm), ['single', 'finished'])
  assert.ok(split.every(row => !row.quantityVerified && row.trace.relatedRecordNo))
  const compounded = rows.find(row => row.importInfo.raw['数量'] === '6300+3700')
  assert.equal(compounded.quantity, 10000); assert.equal(compounded.quantityVerified, false)
  assert.match(compounded.importInfo.quantityNote, /第36行/)
})

test('import is idempotent and preserves existing preview edits, company placement and molds', () => {
  const original = { version: 1, records: [{ id: 'user-preview', priority: 10, company: 'gaibo' }], molds: [{ id: 'existing-mold' }] }
  const first = mergeWorkbookPreview(original, bundle)
  assert.equal(original.records.length, 1); assert.equal(first.records.length, 106)
  first.records.find(row => row.partNo === 'APG098A').description = '用户已补充的内容'
  const second = mergeWorkbookPreview(first, bundle)
  assert.equal(second.records.length, 106); assert.equal(second.records.find(row => row.partNo === 'APG098A').description, '用户已补充的内容')
  assert.equal(second.records[0].company, 'gaibo'); assert.deepEqual(second.molds, original.molds)
  assert.ok(second.records.filter(row => row.importInfo).every(row => row.company === 'tianyue'))
})

test('historical dates and progress never create acceptance, ready molds, current deadlines or guessed years', () => {
  const rows = imported()
  assert.equal(rows.filter(row => row.importInfo.progress === 'reported_completed').length, 45)
  assert.ok(rows.every(row => row.status === 'pending_confirmation' && row.acceptedQty === 0 && row.scrappedQty === 0 && !row.moldReady && row.actualDate === '' && row.plannedDate === '' && row.week === ''))
  assert.equal(rows.find(row => row.no === 'NC-XLS-SPR-039').importInfo.originalPlanned, '2026-10-14')
  const textual = rows.find(row => row.no === 'NC-XLS-SPR-004')
  assert.match(textual.importInfo.originalPlanned, /9.20/); assert.ok(!textual.importInfo.originalPlanned.includes('2026'))
})

test('unclear quantities cannot be saved as a workflow draft before an explicit quantity check; raw cells remain unchanged', () => {
  const row = imported().find(row => row.partNo === '113121-40020-B')
  const draft = { ...draftFrom(row), description: '核实后的异常描述', source: '库存排查' }
  assert.throws(() => validateDraft(draft), /正整数/)
  draft.quantity = 120
  assert.throws(() => validateDraft(draft), /勾选数量核对/)
  draft.quantityVerified = true
  editDefect(row, draft, { name: '品质', dept: 'quality', role_level: 2 })
  assert.equal(row.quantity, 120); assert.equal(row.importInfo.raw['数量'], '')
  assert.equal(row.importInfo.reviewed, false)
})
