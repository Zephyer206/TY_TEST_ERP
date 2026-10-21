/** Compatibility import name retained for the pages; authoritative data comes from the server. */
import { computed, ref, watch } from 'vue'
import { defineStore } from 'pinia'
import { useCompanyStore } from './company'
import { nonconformingApi, type NonconformingWorkspace, type RecordCommand } from '@/api/nonconforming'
import { canAct, validateDraft, type Action, type Actor, type DefectDraft, type DefectRecord, type InspectionEvidence, type ReworkMold, type Submission } from '@/domain/nonconforming'
import type { WorkbookBundle } from '@/domain/nonconformingImport'

const emptyWorkbook: WorkbookBundle = { batchId: '', fileName: '', sha256: '', sourceRows: 0, uniqueRows: 0, mergedDuplicateRows: 0, splitRows: 0, sheets: {}, records: [] }
export const useNonconformingPreview = defineStore('nonconforming-server', () => {
  const company = useCompanyStore()
  const data = ref<NonconformingWorkspace>({ records: [], molds: [], workbook: null, actor: { name: '', dept: '', role_level: 0 }, serverTime: '' })
  const loading = ref(false); const busy = ref(false); const ready = ref(false); const loadError = ref('')
  const records = computed(() => data.value.records.filter(row => row.company === company.selectedCompany).sort((a, b) => a.priority - b.priority))
  const molds = computed(() => data.value.molds.filter(row => row.company === company.selectedCompany))
  const actor = computed<Actor>(() => data.value.actor)
  const workbook = computed<WorkbookBundle>(() => ({ ...emptyWorkbook, ...data.value.workbook, records: [] }))
  const can = (action: Action) => ready.value && canAct(actor.value, action)
  let generation = 0; let requestedCompany = ''; let pending: Promise<void> | null = null
  function reload(): Promise<void> {
    const selected = company.selectedCompany
    if (loading.value && requestedCompany === selected && pending) return pending
    const request = ++generation; requestedCompany = selected
    loading.value = true; ready.value = false; loadError.value = ''
    pending = nonconformingApi.list(selected).then(response => {
      if (request === generation && company.selectedCompany === selected) { data.value = response; ready.value = true }
    }).catch(error => {
      if (request === generation) loadError.value = error instanceof Error ? error.message : '无法读取服务器台账，请重试'
    }).finally(() => { if (request === generation) { loading.value = false; pending = null } })
    return pending
  }
  watch(() => company.selectedCompany, () => { void reload() }, { immediate: true })
  function requireReady() {
    if (!ready.value || loading.value) throw new Error('尚未读取到服务器台账，请先重试加载')
    if (busy.value) throw new Error('正在保存上一次操作，请稍后重试')
  }
  async function save(request: (selected: typeof company.selectedCompany) => Promise<NonconformingWorkspace>) {
    requireReady(); const selected = company.selectedCompany; busy.value = true
    try {
      const response = await request(selected)
      if (selected === company.selectedCompany) data.value = response
      return response
    } finally { busy.value = false }
  }
  function find(id: string): DefectRecord {
    const row = records.value.find(item => item.id === id)
    if (!row) throw new Error('记录不存在或不属于当前公司')
    return row
  }
  const command = (id: string, action: RecordCommand, payload: Record<string, unknown> = {}) => {
    const revision = find(id).revision
    if (!revision) throw new Error('未取得服务器记录版本，请刷新页面')
    return save(selected => nonconformingApi.action(selected, id, revision, action, payload)).then(() => {})
  }
  async function create(payload: DefectDraft): Promise<string> {
    validateDraft(payload)
    const result = await save(selected => nonconformingApi.create(selected, payload))
    if (!result.createdId) throw new Error('服务器未返回新记录编号，请刷新台账核对')
    return result.createdId
  }
  function edit(id: string, payload: DefectDraft) {
    const row = find(id); validateDraft(payload, row.acceptedQty + row.scrappedQty + (row.otherQty || 0))
    return command(id, 'edit', { draft: payload })
  }
  const confirm = (id: string) => command(id, 'confirm')
  const sendBack = (id: string, reason: string) => command(id, 'return', { reason })
  const prepare = (id: string, ready: boolean) => command(id, 'prepare', { ready })
  const start = (id: string) => command(id, 'start')
  const submit = (id: string, result: Submission) => command(id, 'submit', { result })
  const finishStep = (id: string, stepId: string, note: string) => command(id, 'finish_step', { stepId, note })
  const inspect = (id: string, passed: boolean, note: string, evidence: InspectionEvidence) => command(id, 'inspect', { passed, note, evidence })
  function move(id: string, direction: -1 | 1, visibleIds?: string[]) {
    const row = find(id)
    const pendingRows = records.value.filter(item => item.status === 'pending_confirmation' && (!visibleIds || visibleIds.includes(item.id)))
    const target = pendingRows[pendingRows.findIndex(item => item.id === row.id) + direction]
    if (!target) return Promise.resolve()
    return command(id, 'move', { targetId: target.id, targetRevision: target.revision })
  }
  const saveMold = (payload: ReworkMold) => save(selected => nonconformingApi.saveMold(selected, payload)).then(() => {})
  return { records, molds, actor, workbook, loading, busy, ready, loadError, reload, can, create, edit, confirm, sendBack, prepare, start, submit, finishStep, inspect, move, saveMold }
})
