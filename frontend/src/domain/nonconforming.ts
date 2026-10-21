/** First-page workflow contract. Preview persistence lives in its own store. */
export type DefectStatus = 'pending_confirmation' | 'pending' | 'processing' | 'inspection' | 'closed'
export type Disposition = 'rework' | 'sorting' | 'scrap' | 'other'
export type Company = 'tianyue' | 'gaibo'
export interface Actor { name: string; dept: string; role_level: number }
export type Action = 'create' | 'edit' | 'priority' | 'confirm' | 'prepare' | 'start' | 'submit' | 'inspect' | 'return' | 'mold'
export interface HistoryEntry { id: string; at: string; actor: string; action: string; detail: string; snapshot?: string }
export interface Submission { good: number; scrap: number; other?: number; note: string }
export type StepKind = Disposition | 'postprocess'
export interface TreatmentStep { id: string; kind: StepKind; requirement: string; completedAt: string; completedBy: string; result: string }
export interface InspectionItem { id: string; name: string; standard: string }
export interface InspectionCheck { id: string; actual: string; passed: boolean | null }
export interface InspectionEvidence { checks: InspectionCheck[]; quantityChecked: boolean; releaseChecked: boolean }
export interface QuantityLot { id: string; batch: string; container: string; quantity: number; note: string }
export interface Traceability {
  productState: string; marking: string; stockForm: '' | 'single' | 'finished'; returnBatch: string;
  expectedReturnQty: number; quantityBasis: string; isolationLocation: string; containerNo: string; relatedRecordNo: string;
}
export interface ReleaseRequirements {
  mode: 'standard' | 'concession'; basis: string; approvedBy: string; outputPartNo: string;
  destination: string; labeling: string; packing: string; batchRequirement: string;
}
export interface WorkbookOrigin {
  batchId: string; fileName: string; sources: Array<{ sheet: string; row: number; serial: string }>;
  raw: Record<string, string>; quantityNote: string; splitLabel: string;
  progress: 'reported_completed' | 'reported_processing' | 'unrecorded';
  originalPlanned: string; originalActual: string; reviewNotes: string[]; reviewed: boolean;
}
export interface DefectRecord {
  revision?: number;
  id: string; no: string; company: Company; customer: string; partNo: string; partName: string;
  batchNo: string; source: string; quantity: number; quantityVerified: boolean; description: string;
  disposition: Disposition | ''; treatment: string; assignee: string; priority: number;
  plannedDate: string; week: string; status: DefectStatus; moldReady: boolean; paused: boolean;
  acceptedQty: number; scrappedQty: number; otherQty: number; submission: Submission | null; actualDate: string;
  createdAt: string; history: HistoryEntry[];
  trace: Traceability; quantityLots: QuantityLot[]; planSteps: TreatmentStep[];
  inspectionItems: InspectionItem[]; release: ReleaseRequirements;
  importInfo?: WorkbookOrigin;
  historicalCompletion?: { basis: 'source_actual_date'; originalActual: string; recordedAt: string };
  importedProgress?: { basis: 'source_planned_date'; originalPlanned: string; recordedAt: string };
}
export interface ReworkMold {
  revision?: number;
  id: string; company: Company; partNo: string; location: string;
  availability: 'available' | 'maintenance' | 'unavailable'; photos: string[]; defectIds: string[];
}
export interface PreviewData { version: 1; records: DefectRecord[]; molds: ReworkMold[] }
export type DefectDraft = Pick<DefectRecord, 'customer' | 'partNo' | 'partName' | 'batchNo' | 'source' | 'quantity' | 'quantityVerified' | 'description' | 'disposition' | 'treatment' | 'assignee' | 'plannedDate' | 'week' | 'trace' | 'quantityLots' | 'planSteps' | 'inspectionItems' | 'release'>

export const statusLabels: Record<DefectStatus, string> = {
  pending_confirmation: '待确认', pending: '待处理', processing: '处理中', inspection: '待验收', closed: '已关闭',
}
export const dispositionLabels: Record<Disposition, string> = { rework: '返工', sorting: '挑选', scrap: '报废', other: '其他' }
export const stepLabels: Record<StepKind, string> = { ...dispositionLabels, postprocess: '后处理' }
export const stepKinds = Object.keys(stepLabels) as StepKind[]
export const makeStep = (kind: StepKind = 'rework', requirement = ''): TreatmentStep => ({ id: crypto.randomUUID(), kind, requirement, completedAt: '', completedBy: '', result: '' })
export const makeInspectionItem = (name = '', standard = ''): InspectionItem => ({ id: crypto.randomUUID(), name, standard })
export function emptyDefectDraft(): DefectDraft {
  return { customer: '', partNo: '', partName: '', batchNo: '', source: '厂内检验', quantity: 1, quantityVerified: true, description: '', disposition: '', treatment: '', assignee: '', plannedDate: '', week: '',
    trace: { productState: '', marking: '', stockForm: '', returnBatch: '', expectedReturnQty: 0, quantityBasis: '', isolationLocation: '', containerNo: '', relatedRecordNo: '' },
    quantityLots: [], planSteps: [], inspectionItems: [],
    release: { mode: 'standard', basis: '', approvedBy: '', outputPartNo: '', destination: '', labeling: '', packing: '', batchRequirement: '' } }
}
/** Add fields to saved v1 records without replacing quantities, dates, history or mold readiness. */
export function normalizeDefect(record: DefectRecord): DefectRecord {
  const defaults = emptyDefectDraft()
  const legacySteps = record.disposition ? [makeStep(record.disposition, record.treatment)] : []
  if (['inspection', 'closed'].includes(record.status)) for (const step of legacySteps) { step.completedAt = 'legacy'; step.completedBy = '原记录'; step.result = '旧版记录已提交处理结果，原步骤时间未记录' }
  return { ...record, quantityVerified: record.quantityVerified ?? true, otherQty: record.otherQty || 0,
    trace: { ...defaults.trace, ...record.trace }, release: { ...defaults.release, ...record.release },
    quantityLots: record.quantityLots || [], planSteps: record.planSteps ?? legacySteps,
    inspectionItems: record.inspectionItems ?? (record.disposition ? [makeInspectionItem('处置结果', record.treatment || '按已确认处理要求验收')] : []) }
}
/** Only editable business fields may be copied; execution and accepted totals are never draft fields. */
export function draftFrom(record: DefectRecord): DefectDraft {
  const source = normalizeDefect(record)
  return JSON.parse(JSON.stringify(Object.fromEntries(Object.keys(emptyDefectDraft()).map(key => [key, source[key as keyof DefectDraft]])))) as DefectDraft
}
export const hasRework = (record: DefectDraft) => record.planSteps?.length ? record.planSteps.some(step => step.kind === 'rework') : record.disposition === 'rework'
export function hasReworkHistory(record: DefectRecord): boolean {
  if (hasRework(record)) return true
  return record.history.some(entry => {
    if (!entry.snapshot) return false
    try { return hasRework(JSON.parse(entry.snapshot) as DefectDraft) } catch { return false }
  })
}
export const planLabel = (record: DefectDraft) => record.planSteps?.length ? record.planSteps.map(step => stepLabels[step.kind]).join(' → ') : record.disposition ? dispositionLabels[record.disposition] : '待讨论'
export const activeStep = (record: DefectRecord) => record.planSteps?.find(step => !step.completedAt)
export const releaseRequired = (release: ReleaseRequirements) => release.mode === 'concession' || [release.basis, release.approvedBy, release.outputPartNo, release.destination, release.labeling, release.packing, release.batchRequirement].some(value => value.trim())
export const sourceOptions = ['生产过程', '厂内检验', '库存排查', '出货检验', '客户反馈', '客户退回']
export const statuses = Object.keys(statusLabels) as DefectStatus[]
export const dispositions = Object.keys(dispositionLabels) as Disposition[]
export const remainingQty = (record: DefectRecord) => record.status === 'closed' && record.historicalCompletion?.basis === 'source_actual_date' ? 0 : record.quantity - record.acceptedQty - record.scrappedQty - (record.otherQty || 0)
export const submittedQty = (result: Submission) => result.good + result.scrap + (result.other || 0)
export const businessDate = (now = new Date()) => new Intl.DateTimeFormat('sv-SE', { timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit' }).format(now)
export function mondayOf(value: string, offset = 0): string {
  const date = new Date(`${value}T12:00:00Z`)
  date.setUTCDate(date.getUTCDate() - (date.getUTCDay() + 6) % 7 + offset * 7)
  return date.toISOString().slice(0, 10)
}
export function canAct(actor: Actor, action: Action): boolean {
  if (actor.role_level >= 4) return true
  const roles: Record<Action, string[]> = {
    create: ['quality', 'qc', '品质'], edit: ['quality', 'qc', '品质'],
    priority: ['sales', '业务'], confirm: ['quality', 'qc', '品质'],
    prepare: ['engineering', 'design', 'development', 'tech', '开发'],
    start: ['prod', 'production', 'quality', 'qc', '生产', '品质'],
    submit: ['prod', 'production', 'quality', 'qc', '生产', '品质'],
    inspect: ['quality', 'qc', '品质'],
    return: ['quality', 'qc', 'engineering', 'design', 'development', 'tech', 'sales', '品质', '开发', '业务'],
    mold: ['engineering', 'design', 'development', 'tech', '开发'],
  }
  return roles[action].includes(actor.dept)
}
function requireAction(actor: Actor, action: Action) {
  if (!canAct(actor, action)) throw new Error('当前岗位没有此操作权限')
}
export function appendHistory(record: DefectRecord, actor: Actor, action: string, detail: string, snapshot?: string) {
  record.history.unshift({ id: crypto.randomUUID(), at: new Date().toISOString(), actor: actor.name, action, detail, snapshot })
}
export function validateDraft(draft: DefectDraft, alreadyResolved = 0) {
  if (![draft.customer, draft.partNo, draft.partName, draft.description].every(value => value.trim())) throw new Error('请填写客户、零件号、零件名称和异常描述')
  if (!sourceOptions.includes(draft.source)) throw new Error('请选择发现来源')
  if (!Number.isSafeInteger(draft.quantity) || draft.quantity < 1 || draft.quantity < alreadyResolved) throw new Error('不良数量须为正整数，且不能少于已经验收的数量')
  if (draft.quantityVerified === false) throw new Error('请先核实原表实际数量，并勾选数量核对确认')
  if (draft.disposition && !dispositions.includes(draft.disposition)) throw new Error('请选择有效处置方式')
  for (const date of [draft.week, draft.plannedDate]) {
    if (date) {
      const parsed = new Date(`${date}T12:00:00Z`)
      if (!/^\d{4}-\d{2}-\d{2}$/.test(date) || !Number.isFinite(parsed.getTime()) || parsed.toISOString().slice(0, 10) !== date) throw new Error('计划日期无效')
    }
  }
  if (draft.week && mondayOf(draft.week) !== draft.week) throw new Error('任务周必须从周一开始')
  if (draft.week && draft.plannedDate && mondayOf(draft.plannedDate) !== draft.week) throw new Error('计划完成日期须在所选任务周内')
  if (draft.trace && (!Number.isSafeInteger(draft.trace.expectedReturnQty) || draft.trace.expectedReturnQty < 0)) throw new Error('预计退货数量须为非负整数，不计入本条不良数量')
  if (draft.trace?.stockForm && !['single', 'finished'].includes(draft.trace.stockForm)) throw new Error('请选择有效产品形态')
  if (draft.quantityLots?.length) {
    if (draft.quantityLots.length > 50 || draft.quantityLots.some(lot => !Number.isSafeInteger(lot.quantity) || lot.quantity <= 0 || !lot.batch.trim())) throw new Error('数量分项须填写批次或来源和正整数数量，最多50项')
    if (draft.quantityLots.reduce((sum, lot) => sum + lot.quantity, 0) !== draft.quantity) throw new Error('数量分项合计必须等于本条实际不良数量；预计退货不得加入分项')
  }
  for (const items of [draft.planSteps || [], draft.inspectionItems || [], draft.quantityLots || []]) {
    if (new Set(items.map(item => item.id)).size !== items.length || items.some(item => !item.id)) throw new Error('明细标识重复或缺失，请重新添加该明细')
  }
  if (draft.planSteps?.length > 12 || draft.planSteps?.some(step => !stepKinds.includes(step.kind))) throw new Error('处理步骤无效，最多12步')
  if (draft.inspectionItems?.length > 30) throw new Error('验收项目最多30项')
  if (draft.release && !['standard', 'concession'].includes(draft.release.mode)) throw new Error('请选择有效放行方式')
}
export function editDefect(record: DefectRecord, draft: DefectDraft, actor: Actor) {
  requireAction(actor, 'edit')
  if (record.status !== 'pending_confirmation') throw new Error('已确认内容已锁定，请先填写原因并退回待确认')
  validateDraft(draft, record.acceptedQty + record.scrappedQty + (record.otherQty || 0))
  const previous = JSON.stringify({ ...record, history: undefined })
  const editable = draftFrom(draft as DefectRecord)
  // Reconfirmation begins a new execution cycle for the unresolved quantity.
  editable.planSteps = editable.planSteps.map(step => ({ ...step, completedAt: '', completedBy: '', result: '' }))
  Object.assign(record, editable, { week: draft.week || (draft.plannedDate ? mondayOf(draft.plannedDate) : '') })
  appendHistory(record, actor, '更新待确认内容', '保存不良信息与待讨论方案', previous)
}
export function confirmDefect(record: DefectRecord, actor: Actor) {
  requireAction(actor, 'confirm')
  if (record.status !== 'pending_confirmation') throw new Error('只有待确认记录可以确认')
  validateDraft(record, record.acceptedQty + record.scrappedQty + (record.otherQty || 0))
  if (!record.disposition || !record.treatment.trim() || !record.assignee.trim() || !record.plannedDate) throw new Error('确认前请填写处置方式、处理要求、执行负责人和计划完成时间')
  if (!record.planSteps?.length || record.planSteps.some(step => !step.requirement.trim())) throw new Error('确认前请填写每个处理步骤的要求')
  if (!record.planSteps.some(step => step.kind === record.disposition)) throw new Error('处理步骤须包含所选处置方式')
  if (record.planSteps.some(step => step.kind === 'scrap') && (record.disposition !== 'scrap' || record.planSteps.some(step => step.kind !== 'scrap'))) throw new Error('报废须作为单独方案确认；部分产品报废时先退回讨论剩余数量')
  if (!record.inspectionItems?.length || record.inspectionItems.some(item => !item.name.trim() || !item.standard.trim())) throw new Error('确认前至少填写一个验收项目及标准')
  if (record.release?.mode === 'concession' && (!record.release.basis.trim() || !record.release.approvedBy.trim())) throw new Error('让步放行须记录批准依据及批准人')
  if (remainingQty(record) <= 0) throw new Error('全部数量已验收，请由品质核对历史结果')
  const snapshot = JSON.stringify({ ...record, history: undefined })
  record.status = 'pending'; record.paused = false
  if (record.importInfo) record.importInfo.reviewed = true
  record.planSteps.forEach(step => { step.completedAt = ''; step.completedBy = ''; step.result = '' })
  appendHistory(record, actor, '确认处理方案', `${planLabel(record)} · 整条 ${record.quantity} 件（本轮剩余 ${remainingQty(record)} 件） · 计划 ${record.plannedDate} · 顺序 ${record.priority}`, snapshot)
}
export function returnDefect(record: DefectRecord, reason: string, actor: Actor) {
  requireAction(actor, 'return')
  if (!['pending', 'processing', 'inspection'].includes(record.status)) throw new Error('只有未关闭的已确认记录可以退回')
  if (!reason.trim()) throw new Error('请填写退回原因')
  const snapshot = JSON.stringify({ ...record, history: undefined })
  const previous = statusLabels[record.status]
  record.status = 'pending_confirmation'; record.paused = true; record.submission = null
  appendHistory(record, actor, '退回待确认', `原状态：${previous}；原因：${reason.trim()}。原任务暂停，已验收数量及模具就绪情况保留。`, snapshot)
}
export function setMoldReady(record: DefectRecord, ready: boolean, actor: Actor) {
  requireAction(actor, 'prepare')
  if (!hasRework(record) || !['pending', 'processing'].includes(record.status)) throw new Error('仅待处理或处理中的返工任务可更新模具就绪情况')
  if (record.planSteps?.some(step => step.kind === 'rework') && record.planSteps.filter(step => step.kind === 'rework').every(step => step.completedAt)) throw new Error('本轮返工步骤已完成，不能再修改模具就绪情况')
  record.moldReady = ready
  appendHistory(record, actor, '更新模具就绪', ready ? '返工模具已就绪' : '返工模具尚未就绪')
}
export function startDefect(record: DefectRecord, actor: Actor) {
  requireAction(actor, 'start')
  if (record.status !== 'pending') throw new Error('只有待处理任务可以开工')
  if ((activeStep(record)?.kind || record.disposition) === 'rework' && !record.moldReady) throw new Error('返工模具尚未就绪')
  record.status = 'processing'
  appendHistory(record, actor, '开始处理', `${record.assignee} 开始${record.disposition ? dispositionLabels[record.disposition] : '处理'}`)
}
export function completeStep(record: DefectRecord, stepId: string, note: string, actor: Actor) {
  requireAction(actor, 'submit')
  if (record.status !== 'processing') throw new Error('只有处理中的任务可以记录步骤完成')
  const step = activeStep(record)
  if (!step || step.id !== stepId) throw new Error('请按已确认顺序完成当前步骤')
  if (step.kind === 'rework' && !record.moldReady) throw new Error('返工模具尚未就绪')
  if (!note.trim()) throw new Error('请填写本步实际处理情况')
  step.completedAt = new Date().toISOString(); step.completedBy = actor.name; step.result = note.trim()
  appendHistory(record, actor, '完成处理步骤', `${stepLabels[step.kind]} · 本轮剩余 ${remainingQty(record)} 件；${step.result}。数量以本轮提交及品质验收为准。`)
}
export function submitResult(record: DefectRecord, result: Submission, actor: Actor) {
  requireAction(actor, 'submit')
  if (record.status !== 'processing') throw new Error('只有处理中的任务可以提交验收')
  if (activeStep(record)) throw new Error('请先按顺序完成本轮全部处理步骤，再提交品质验收')
  if (![result.good, result.scrap, result.other || 0].every(value => Number.isSafeInteger(value) && value >= 0) || submittedQty(result) < 1 || submittedQty(result) > remainingQty(record)) throw new Error('本次结果数量须大于零，且不能超过剩余待处理数量')
  if (record.disposition === 'scrap' && result.good !== 0) throw new Error('报废方案只能提交报废数量')
  if (record.disposition !== 'scrap' && result.scrap !== 0) throw new Error('需要报废剩余产品时，请退回待确认后确认报废方案')
  if (record.disposition === 'other' && (result.good !== 0 || result.scrap !== 0)) throw new Error('其他处置请填写按方案完成的数量')
  if (record.disposition !== 'other' && (result.other || 0) !== 0) throw new Error('其他处置数量只能用于其他方案')
  if (!result.note.trim()) throw new Error('请填写处理结果说明')
  record.submission = { ...result, note: result.note.trim() }; record.status = 'inspection'
  appendHistory(record, actor, '提交品质验收', `本次合格 ${result.good} 件，报废 ${result.scrap} 件${result.other ? `，其他处置 ${result.other} 件` : ''}；${result.note.trim()}`)
}
export function inspectResult(record: DefectRecord, passed: boolean, note: string, actor: Actor, evidence?: InspectionEvidence) {
  requireAction(actor, 'inspect')
  if (record.status !== 'inspection' || !record.submission) throw new Error('没有待验收的处理结果')
  if (!note.trim()) throw new Error('请填写品质验收意见')
  if (passed && (!evidence || !evidence.quantityChecked)) throw new Error('验收通过前须核对本次实物数量')
  if (passed && (!record.inspectionItems?.length || !evidence || evidence.checks.length !== record.inspectionItems.length || record.inspectionItems.some(item => {
    const matches = evidence.checks.filter(check => check.id === item.id)
    return matches.length !== 1 || !matches[0].actual.trim() || matches[0].passed !== true
  }))) throw new Error('验收通过前，每个项目须填写实测或核实结果并判定通过')
  if (passed && record.release && releaseRequired(record.release) && !evidence?.releaseChecked) throw new Error('验收通过前须核对放行及发货要求')
  const result = record.submission
  if (submittedQty(result) > remainingQty(record) || submittedQty(result) <= 0) throw new Error('待验收数量与剩余数量不符，请退回待确认核对')
  const snapshot = JSON.stringify({ ...record, history: undefined, inspection: { ...evidence, passed, note: note.trim() } })
  if (passed) { record.acceptedQty += result.good; record.scrappedQty += result.scrap; record.otherQty = (record.otherQty || 0) + (result.other || 0) }
  record.submission = null
  const closed = passed && remainingQty(record) === 0
  record.status = closed ? 'closed' : 'processing'
  if (closed) record.actualDate = businessDate()
  if (!closed) record.planSteps?.forEach(step => { step.completedAt = ''; step.completedBy = ''; step.result = '' })
  appendHistory(record, actor, passed ? (closed ? '验收通过并关闭' : '部分验收通过') : '验收不通过', `${note.trim()}；本次合格 ${result.good}、报废 ${result.scrap}${result.other ? `、其他处置 ${result.other}` : ''}；剩余 ${remainingQty(record)} 件${!passed ? '（本次结果未计入已验收数量）' : ''}。${closed ? '' : '剩余数量进入下一轮处理，步骤重新记录。'}`, snapshot)
}
export function movePriority(records: DefectRecord[], id: string, direction: -1 | 1, actor: Actor) {
  requireAction(actor, 'priority')
  const record = records.find(item => item.id === id)
  if (!record || record.status !== 'pending_confirmation') throw new Error('已确认的处理顺序已锁定')
  const pending = records.filter(item => item.company === record.company && item.status === 'pending_confirmation').sort((a, b) => a.priority - b.priority)
  const target = pending[pending.findIndex(item => item.id === id) + direction]
  if (!target) return
  const rank = record.priority; record.priority = target.priority; target.priority = rank
  appendHistory(record, actor, '调整处理顺序', `当前顺序 ${record.priority}`)
  appendHistory(target, actor, '调整处理顺序', `当前顺序 ${target.priority}`)
}
