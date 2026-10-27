/** Contract verification with the actual typed wrappers and actual request builder.
 * The request transport is replaced before execution: no HTTP, authentication,
 * database or external QR image upload is performed by this check.
 */
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'
import { apiRegistry, getApiDefinition } from '../../shared/api/registry.js'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const frontend = path.join(root, 'frontend')
const requireFrontend = createRequire(path.join(frontend, 'package.json'))
const ts = requireFrontend('typescript')
const calls = []
const transport = { request: async config => { calls.push(config); return { data: { contractTransport: true } } } }
const modules = new Map()
function loadTs(name) {
  if (modules.has(name)) return modules.get(name)
  const filename = path.join(frontend, 'src/api', `${name}.ts`)
  const output = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
    fileName: filename,
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, esModuleInterop: true },
  }).outputText
  const exports = {}
  modules.set(name, exports)
  const require = dependency => {
    if (dependency === '@/utils/request') return transport
    if (dependency === './registry') return { apiRegistry, getApiDefinition }
    if (dependency === './client') return loadTs('client')
    if (dependency === './qr') return loadTs('qr')
    throw new Error(`Unexpected API dependency: ${dependency}`)
  }
  new Function('require', 'exports', output)(require, exports)
  return exports
}
const { materialQrApi: mat } = loadTs('materialQr')
const { machinesApi: machine } = loadTs('machines')
const { productionApi: prod } = loadTs('production')
const { qrApi: qr } = loadTs('qr')

const inventory = new Map([...fs.readFileSync(path.join(root, 'specs/002-material-qr-traceability/phase0-baseline.md'), 'utf8')
  .matchAll(/^\| (B\d{3}) \| (\w+) \| `([^`]+)`/gm)].map(([, id, method, route]) => [id, { method, route }]))
assert.equal(inventory.size, 32, 'The frozen baseline must retain all 32 legacy QR endpoints')
const scan = { scan_type: 'MAT', entity_id: 37, operation: 'query', notes: 'contract' }
const inbound = { material_id: 5, supplier_id: 6, gross_weight: 100, po_no: 'PO-A' }
const verify = { machine_id: 8, part_id: 9, material_batch_id: 37 }
const cases = [
  ['B001', 'materialQr.create', () => mat.createInbound(inbound), {}, undefined, inbound],
  ['B002', 'materialQr.list', () => mat.listBatches({ status: 'available', material_id: 5, skip: 2, limit: 20 }), {}, { status: 'available', material_id: 5, skip: 2, limit: 20 }],
  ['B003', 'materialQr.detail', () => mat.getBatch(37), { batch_id: 37 }],
  ['B004', 'materialQr.byNo', () => mat.getBatchByNo('BATCH/甲'), { batch_no: 'BATCH/甲' }],
  ['B005', 'materialQr.iqc', () => mat.updateIqc(37, { result: 'passed', notes: 'ok' }), { batch_id: 37 }, undefined, { result: 'passed', notes: 'ok' }],
  ['B006', 'materialQr.split', () => mat.split(37, { splits: [{ weight: 20 }] }), { batch_id: 37 }, undefined, { splits: [{ weight: 20 }] }],
  ['B007', 'materialQr.consume', () => mat.consume(37, { weight: 4, reference_type: 'session', reference_id: 2 }), { batch_id: 37 }, undefined, { weight: 4, reference_type: 'session', reference_id: 2 }],
  ['B008', 'materialQr.scrap', () => mat.scrap(37, { reason: 'contract' }), { batch_id: 37 }, undefined, { reason: 'contract' }],
  ['B009', 'materialQr.trace', () => mat.getTraceability(37), { batch_id: 37 }],
  ['B010', 'materialQr.scan', () => mat.scanQr(37), { batch_id: 37 }],
  ['B011', 'materialQr.childScan', () => mat.scanChild(38), { child_id: 38 }],
  ['B012', 'materialQr.children', () => mat.listChildren(37), { batch_id: 37 }],
  ['B013', 'qrScans.create', () => mat.createScanLog(scan), {}, undefined, scan],
  ['B014', 'qrScans.list', () => mat.listScanLogs('MAT', 37, { skip: 1, limit: 10 }), { entity_type: 'MAT', entity_id: 37 }, { skip: 1, limit: 10 }],
  ['B015', 'materialQr.reprint', () => mat.reprintQr(37), { batch_id: 37 }],
  ['B016', 'machines.repairScan', () => machine.repairScan(8, { scan_type: 'second', action: 'complete' }), { machine_id: 8 }, { scan_type: 'second', action: 'complete' }],
  ['B017', 'machines.generateQr', () => machine.generateQr(8), { machine_id: 8 }],
  ['B018', 'machines.scanQr', () => machine.scanQr(8), { machine_id: 8 }],
  ['B019', 'production.verifyMaterial', () => prod.verifyMaterial(verify), {}, verify],
  ['B020', 'production.startSession', () => prod.startSession({ ...verify, force_start: false }), {}, undefined, { ...verify, force_start: false }],
  ['B021', 'production.closeSession', () => prod.closeSession(2), { session_id: 2 }],
  ['B022', 'production.processFlowCards', () => prod.processFlowCards({ part_id: 9, machine_id: 8, status: 'completed', skip: 0, limit: 20 }), {}, { part_id: 9, machine_id: 8, status: 'completed', skip: 0, limit: 20 }],
  ['B023', 'production.scanProcessFlow', () => prod.scanProcessFlow(3), { card_id: 3 }],
  ['B024', 'production.reverseTraceProcessFlow', () => prod.reverseTraceProcessFlow(3), { card_id: 3 }],
  ['B025', 'production.inboundProcessFlow', () => prod.inboundProcessFlow(3, { notes: 'received' }), { card_id: 3 }, undefined, { notes: 'received' }],
  ['B026', 'production.reprintProcessFlow', () => prod.reprintProcessFlow(3), { card_id: 3 }],
  ['B027', 'qr.lookup', () => qr.lookup({ code: 'BATCH-A', manual: true, type: 'MAT' }), {}, { code: 'BATCH-A', manual: true, type: 'MAT' }],
  ['B028', 'qr.generate', () => qr.generate({ prefix: 'MAT', entity_id: 37 }), {}, undefined, { prefix: 'MAT', entity_id: 37 }],
  ['B029', 'qr.material', () => qr.material(37), { batch_id: 37 }],
  ['B030', 'qr.machine', () => qr.machine(8), { machine_id: 8 }],
  ['B031', 'qr.processFlow', () => qr.processFlow(3), { card_id: 3 }],
  ['B032', 'qr.part', () => qr.part(9), { part_id: 9 }],
]
const endpoints = []
for (const [id, key, invoke, pathParams, params, data] of cases) {
  const baseline = inventory.get(id)
  const definition = getApiDefinition(key)
  assert.equal(definition.key, key, `${id}: registry key`)
  assert.equal(definition.method, baseline.method, `${id}: method changed`)
  assert.equal(definition.path, baseline.route, `${id}: route changed`)
  assert.equal(definition.auth, true, `${id}: authentication required`)
  assert.equal(definition.lifecycle, 'active', `${id}: existing endpoint retained`)
  assert.ok(definition.description.length > 10, `${id}: description missing`)
  const response = await invoke()
  assert.deepEqual(response, { contractTransport: true }, `${id}: response must be unwrapped once`)
  const config = calls.pop()
  assert.equal(config.method, baseline.method.toLowerCase(), `${id}: request method`)
  assert.equal(config.url, baseline.route.replace(/\{([^}]+)\}/g, (_, field) => encodeURIComponent(String(pathParams[field]))), `${id}: encoded path parameters`)
  assert.deepEqual(config.params, params, `${id}: query parameters must reach request transport`)
  assert.deepEqual(config.data, data, `${id}: JSON body must reach request transport`)
  endpoints.push({ id, key, method: baseline.method, path: baseline.route })
}
await mat.lookup({ code: 'MAT:37' })
assert.equal(calls.pop().url, '/qr/lookup', 'Material lookup must share the registered generic lookup')
await mat.listMaterials({ grade: 'SPCC', limit: 100 })
assert.deepEqual(calls.pop(), { method: 'get', url: '/warehouse/materials', params: { grade: 'SPCC', limit: 100 }, data: undefined })
await mat.listSuppliers({ is_active: true, limit: 100 })
assert.deepEqual(calls.pop(), { method: 'get', url: '/warehouse/suppliers', params: { is_active: true, limit: 100 }, data: undefined })
await prod.listPlans({ status: 'pending', limit: 100 })
assert.deepEqual(calls.pop(), { method: 'get', url: '/production/plans', params: { status: 'pending', limit: 100 }, data: undefined })
assert.equal(calls.length, 0)
console.log(JSON.stringify({ legacyEndpoints: endpoints.length, extraWrapperChecks: 4, transport: 'in-memory; zero HTTP calls', endpoints }))
