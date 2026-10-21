<template>
  <div class="production-container">
    <header class="page-header">
      <div>
        <h1>生产计划</h1>
        <p>业务提交生产目标，资材确认材料备齐后进入排产。</p>
      </div>
      <div class="header-actions">
        <span class="sync-state" aria-live="polite">{{ loading ? '正在更新' : `已载入 ${plans.length} 条计划` }}</span>
        <el-button :icon="Refresh" circle aria-label="刷新生产计划" @click="loadWorkbench" />
      </div>
    </header>

    <el-alert v-if="linkedPlanId" class="linked-plan-notice" type="info" :closable="false" show-icon>
      <template #title>从工作台打开：生产计划 #{{ linkedPlanId }}</template>
      <template #default>下方队列仅显示此计划。<router-link to="/production">查看全部计划</router-link></template>
    </el-alert>
    <section class="entry-panel" aria-labelledby="entry-title">
      <div class="section-heading">
        <div>
          <h2 id="entry-title">新建计划</h2>
          <p>填写客户件号和目标数量。TWP 不完整时不能提交。</p>
        </div>
        <div class="entry-actions">
          <el-button :icon="Plus" @click="addDraftRow">增加一行</el-button>
          <el-button type="primary" :loading="submitting" @click="submitPlans">提交给资材确认</el-button>
        </div>
      </div>

      <div class="table-scroll entry-table-wrap">
        <el-table :data="draftRows" row-key="key" class="entry-table" aria-label="生产计划录入表">
          <el-table-column label="#" width="46" align="center">
            <template #default="{ $index }"><span class="row-index">{{ $index + 1 }}</span></template>
          </el-table-column>
          <el-table-column label="客户件号 / 零件名称" min-width="258">
            <template #default="{ row }">
              <el-select
                v-model="row.partId"
                class="part-picker"
                filterable
                remote
                clearable
                reserve-keyword
                placeholder="输入客户件号或零件名称"
                :remote-method="partSearchHandler(row)"
                :loading="row.searching"
                @visible-change="handlePickerVisible(row, $event)"
                @change="handlePartChange(row, $event)"
              >
                <el-option v-for="option in row.options" :key="option.id" :label="partOptionLabel(option)" :value="option.id">
                  <div class="part-option"><strong>{{ option.customer_part_no || '未维护客户件号' }}</strong><span>{{ option.part_name || '未命名零件' }}</span></div>
                </el-option>
              </el-select>
              <el-input
                v-if="row.part?.left_right_partner"
                class="paired-part-picker"
                :model-value="`已自动附带：${partOptionLabel(row.part.left_right_partner)} · 同步生产，共享 TWP`"
                readonly
                tabindex="-1"
                aria-label="自动附带的左右件"
              />
              <p v-else-if="row.duplicateMessage" class="inline-warning" role="status">{{ row.duplicateMessage }}</p>
            </template>
          </el-table-column>
          <el-table-column label="材料" min-width="120">
            <template #default="{ row }">
              <span class="cell-text">{{ row.part?.material_name || '—' }}</span>
              <small v-if="row.part && row.part.material_density === null" class="cell-hint">缺少密度</small>
            </template>
          </el-table-column>
          <el-table-column label="TWP" min-width="280">
            <template #default="{ row }">
              <div v-if="row.partId" class="twp-cell">
                <el-select v-model="row.twpSourceSpecId" placeholder="选择来源 TWP" @change="() => selectTwp(row)">
                  <el-option v-for="option in row.part?.twp_options || []" :key="option.id" :label="twpOptionLabel(option)" :value="option.id" />
                </el-select>
                <el-tooltip :content="row.manualTwp ? '使用来源 TWP' : '手动修改本计划 TWP'" placement="top">
                  <el-button :icon="row.manualTwp ? RefreshLeft : EditPen" circle text :aria-label="row.manualTwp ? '使用来源 TWP' : '手动修改本计划 TWP'" :disabled="!row.twpSourceSpecId" @click="toggleManualTwp(row)" />
                </el-tooltip>
                <span v-if="!row.manualTwp" class="twp-source-value">{{ sourceTwpValue(row) || 'TWP 不完整' }}</span>
                <div v-else class="manual-twp-inputs" aria-label="手动 TWP">
                  <el-input-number v-model="row.manualValues.thickness" :min="0" :precision="3" controls-position="right" placeholder="T" aria-label="厚度 T" />
                  <span>×</span>
                  <el-input-number v-model="row.manualValues.width" :min="0" :precision="3" controls-position="right" placeholder="W" aria-label="宽度 W" />
                  <span>×</span>
                  <el-input-number v-model="row.manualValues.pitch" :min="0" :precision="3" controls-position="right" placeholder="P" aria-label="步距 P" />
                </div>
              </div>
              <span v-else class="cell-text">先选择零件</span>
            </template>
          </el-table-column>
          <el-table-column label="目标数量" width="128" align="right">
            <template #default="{ row }">
              <el-input-number v-model="row.totalQty" :min="1" :precision="0" controls-position="right" aria-label="目标数量" />
            </template>
          </el-table-column>
          <el-table-column label="加急" width="72" align="center">
            <template #default="{ row }"><el-checkbox v-model="row.isUrgent" aria-label="加急备料" /></template>
          </el-table-column>
          <el-table-column label="操作" width="62" align="center">
            <template #default="{ $index }">
              <el-tooltip content="删除此行" placement="top"><el-button :icon="Delete" circle text type="danger" aria-label="删除此行" :disabled="draftRows.length === 1" @click="removeDraftRow($index)" /></el-tooltip>
            </template>
          </el-table-column>
        </el-table>
      </div>
      <p class="entry-note">手动修改的 TWP 会随计划保存，并在资材确认列表中明确标记。</p>
    </section>

    <section class="queue-section" aria-labelledby="queue-title">
      <div class="queue-toolbar">
        <div class="queue-title"><h2 id="queue-title">资材确认队列</h2><span>{{ filteredPlans.length }} 条</span></div>
        <div class="queue-controls">
          <el-input v-model="filters.search" :prefix-icon="Search" placeholder="搜索客户件号或零件名称" clearable aria-label="搜索生产计划" />
          <el-select v-model="filters.materialStatus" clearable placeholder="资材状态" aria-label="按资材状态筛选">
            <el-option label="待资材确认" value="pending" />
            <el-option label="可排产" value="ready" />
          </el-select>
          <el-button :disabled="!selectedPendingPlans.length" @click="confirmSelectedPlans">确认材料已备齐（{{ selectedPendingPlans.length }}）</el-button>
        </div>
      </div>

      <div class="status-strip" aria-label="生产计划状态摘要">
        <div><span>待资材确认</span><strong>{{ pendingPlans.length }}</strong></div>
        <div><span>可排产</span><strong>{{ readyPlans.length }}</strong></div>
        <div><span>加急计划</span><strong>{{ urgentPlans.length }}</strong></div>
        <p>资材确认只表示材料已备齐，不安排机台。</p>
      </div>

      <div class="table-scroll queue-table-wrap">
        <el-table
          :data="filteredPlans"
          class="queue-table"
          row-key="id"
          v-loading="loading"
          @selection-change="handleSelectionChange"
        >
          <el-table-column type="selection" width="44" :selectable="isPlanConfirmable" />
          <el-table-column label="组合产出" min-width="170">
            <template #default="{ row }">
              <span v-if="row.is_left_right_pair" class="paired-hint">一出二：{{ row.paired_customer_part_no || row.paired_part_name }}</span>
              <span v-else class="cell-text">单件</span>
            </template>
          </el-table-column>
          <el-table-column label="客户件号" min-width="130">
            <template #default="{ row }"><span class="part-number">{{ row.customer_part_no || '未维护' }}</span></template>
          </el-table-column>
          <el-table-column prop="part_name" label="零件名称" min-width="150" show-overflow-tooltip />
          <el-table-column prop="material_name" label="材料" min-width="118" show-overflow-tooltip />
          <el-table-column label="TWP" min-width="165">
            <template #default="{ row }">
              <div class="queue-twp"><span>{{ row.twp_value || '—' }}</span><span v-if="row.twp_manual_override" class="manual-flag">手动修改</span></div>
            </template>
          </el-table-column>
          <el-table-column label="目标 / 剩余" width="128" align="right">
            <template #default="{ row }"><span class="numeric">{{ row.total_qty }} / {{ row.remaining_qty }}</span></template>
          </el-table-column>
          <el-table-column label="理论用量" width="116" align="right">
            <template #default="{ row }"><span class="numeric">{{ row.estimated_material_weight_kg === null ? '待资材判断' : `${row.estimated_material_weight_kg} kg` }}</span></template>
          </el-table-column>
          <el-table-column label="资材确认" min-width="190">
            <template #default="{ row }">
              <div class="material-status">
                <span class="status-dot" :class="row.material_status" aria-hidden="true" />
                <span>{{ materialStatusLabel(row.material_status) }}</span>
                <small v-if="row.material_status === 'pending' && row.confirmation_increment">新增 {{ row.confirmation_increment }}</small>
                <small v-else-if="row.material_confirmed_at">{{ formatDate(row.material_confirmed_at) }}</small>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="用量方式" width="124">
            <template #default="{ row }">
              <el-select v-model="row.material_calculation_mode" size="small" :disabled="row.estimated_material_weight_kg === null" aria-label="材料用量方式" @change="handleCalculationChange(row, $event)">
                <el-option label="系统计算" value="auto" />
                <el-option label="资材确认" value="manual" />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="70" fixed="right" align="center">
            <template #default="{ row }">
              <el-tooltip content="取消计划" placement="top"><el-button :icon="CircleClose" circle text type="danger" aria-label="取消计划" :disabled="!isPlanCancellable(row)" @click="cancelPlan(row)" /></el-tooltip>
            </template>
          </el-table-column>
          <template #empty><el-empty description="暂无生产计划" :image-size="46" /></template>
        </el-table>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { CircleClose, Delete, EditPen, Plus, Refresh, RefreshLeft, Search } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { productionApi } from '@/api/production'

type MaterialStatus = 'pending' | 'ready'
type CalculationMode = 'auto' | 'manual'
const route = useRoute()
const linkedPlanId = computed(() => /^\d+$/.test(String(route.query.plan_id)) && Number(route.query.plan_id) > 0 ? Number(route.query.plan_id) : undefined)

interface TWPOption {
  id: number
  tooling_number: string | null
  value: string | null
  thickness: number | null
  width: number | null
  pitch: number | null
  cavity_count: number | null
  is_primary: boolean
}

interface PartOption {
  id: number
  customer_part_no: string | null
  part_name: string | null
  material_name: string | null
  material_density: number | null
  twp_options: TWPOption[]
  left_right_partner?: Omit<PartOption, 'left_right_partner'> | null
  left_right_tooling_number?: string | null
}

interface DraftRow {
  key: number
  partId?: number
  part?: PartOption
  options: PartOption[]
  searching: boolean
  twpSourceSpecId?: number
  manualTwp: boolean
  manualValues: { thickness?: number; width?: number; pitch?: number }
  totalQty?: number
  isUrgent: boolean
  duplicateMessage: string
  acknowledgeTwpChange: boolean
}

interface WorkbenchPlan {
  id: number
  part_id: number | null
  customer_part_no: string | null
  part_name: string | null
  material_name: string | null
  total_qty: number
  completed_qty: number
  remaining_qty: number
  is_urgent: boolean
  status: string
  material_status: MaterialStatus
  material_confirmed_qty: number | null
  material_confirmed_by: number | null
  material_confirmed_at: string | null
  material_confirmation_note: string | null
  material_calculation_mode: CalculationMode
  twp_value: string | null
  twp_manual_override: boolean
  material_density: number | null
  estimated_material_weight_kg: number | null
  confirmation_increment: number
  created_at: string | null
  updated_at: string | null
}

interface WorkbenchPage { items: WorkbenchPlan[]; total: number; active_items: WorkbenchPlan[] }

let rowSequence = 0
const makeDraftRow = (): DraftRow => ({
  key: ++rowSequence,
  options: [],
  searching: false,
  manualTwp: false,
  manualValues: {},
  totalQty: undefined,
  isUrgent: false,
  duplicateMessage: '',
  acknowledgeTwpChange: false,
})

const draftRows = ref<DraftRow[]>([makeDraftRow()])
const plans = ref<WorkbenchPlan[]>([])
const activePlans = ref<WorkbenchPlan[]>([])
const selectedPlans = ref<WorkbenchPlan[]>([])
const loading = ref(false)
const submitting = ref(false)
const filters = reactive({ search: '', materialStatus: '' as '' | MaterialStatus })

const pendingPlans = computed(() => plans.value.filter(plan => plan.material_status === 'pending' && !isTerminal(plan)))
const readyPlans = computed(() => plans.value.filter(plan => plan.material_status === 'ready' && !isTerminal(plan)))
const urgentPlans = computed(() => plans.value.filter(plan => plan.is_urgent && !isTerminal(plan)))
const selectedPendingPlans = computed(() => selectedPlans.value.filter(isPlanConfirmable))
const filteredPlans = computed(() => {
  const keyword = filters.search.trim().toLowerCase()
  return plans.value.filter(plan => {
    const matchingStatus = !filters.materialStatus || plan.material_status === filters.materialStatus
    const matchingKeyword = !keyword || [plan.customer_part_no, plan.part_name, plan.material_name]
      .filter(Boolean)
      .some(value => String(value).toLowerCase().includes(keyword))
    return matchingStatus && matchingKeyword
  })
})

const isTerminal = (plan: WorkbenchPlan) => ['cancelled', 'completed', 'closed'].includes(plan.status)
const isPlanConfirmable = (plan: WorkbenchPlan) => plan.material_status === 'pending' && !isTerminal(plan)
const isPlanCancellable = (plan: WorkbenchPlan) => !['in_progress', 'completed', 'closed', 'cancelled'].includes(plan.status)
const materialStatusLabel = (status: MaterialStatus) => status === 'ready' ? '可排产' : '待资材确认'
const formatDate = (value: string) => new Intl.DateTimeFormat('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }).format(new Date(value))
const partOptionLabel = (option: PartOption) => [option.customer_part_no, option.part_name].filter(Boolean).join(' · ') || '未命名零件'
const twpOptionLabel = (option: TWPOption) => [option.tooling_number, option.value || 'TWP 不完整'].filter(Boolean).join(' · ')

const selectedTwpOption = (row: DraftRow): TWPOption | undefined => row.part?.twp_options.find(option => option.id === row.twpSourceSpecId)
const sourceTwpValue = (row: DraftRow): string | null => selectedTwpOption(row)?.value || null

const loadWorkbench = async (): Promise<void> => {
  loading.value = true
  try {
  const page = await productionApi.workbench<WorkbenchPage>({ limit: 200, plan_id: linkedPlanId.value })
    plans.value = page.items
    activePlans.value = page.active_items
    refreshDuplicateWarnings()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '获取生产计划失败')
  } finally {
    loading.value = false
  }
}

const searchPartOptions = async (row: DraftRow, query: string): Promise<void> => {
  row.searching = true
  try {
    row.options = await productionApi.planningPartOptions<PartOption[]>({ query, limit: 30 })
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '搜索零件失败')
  } finally {
    row.searching = false
  }
}

const partSearchHandler = (row: DraftRow) => (query: string): Promise<void> => searchPartOptions(row, query)
const handlePickerVisible = (row: DraftRow, visible: boolean): void => {
  if (visible && !row.options.length) void searchPartOptions(row, '')
}
const handlePartChange = (row: DraftRow, partId: number | undefined): void => selectPart(row, partId)

const selectPart = (row: DraftRow, partId?: number): void => {
  row.part = row.options.find(option => option.id === partId)
  row.twpSourceSpecId = undefined
  row.manualTwp = false
  row.manualValues = {}
  if (!row.part) {
    row.duplicateMessage = ''
    return
  }
  const primary = row.part.twp_options.find(option => option.is_primary)
  if (primary) {
    row.twpSourceSpecId = primary.id
  } else if (row.part.twp_options.length === 1) {
    row.twpSourceSpecId = row.part.twp_options[0].id
  }
  refreshDuplicateWarnings()
}

const selectTwp = (row: DraftRow): void => {
  row.manualTwp = false
  row.manualValues = {}
}

const toggleManualTwp = (row: DraftRow): void => {
  if (!row.manualTwp) {
    const source = selectedTwpOption(row)
    row.manualValues = {
      thickness: source?.thickness ?? undefined,
      width: source?.width ?? undefined,
      pitch: source?.pitch ?? undefined,
    }
  } else {
    row.manualValues = {}
  }
  row.manualTwp = !row.manualTwp
}

const refreshDuplicateWarnings = (): void => {
  const activePlansByPart = new Map<number, WorkbenchPlan[]>()
  activePlans.value.filter(plan => plan.part_id !== null && !isTerminal(plan)).forEach(plan => {
    const entries = activePlansByPart.get(plan.part_id as number) || []
    entries.push(plan)
    activePlansByPart.set(plan.part_id as number, entries)
  })
  const draftCounts = new Map<number, number>()
  draftRows.value.forEach(row => {
    if (row.partId) draftCounts.set(row.partId, (draftCounts.get(row.partId) || 0) + 1)
  })
  draftRows.value.forEach(row => {
    if (!row.partId) {
      row.duplicateMessage = ''
      return
    }
    const existing = activePlansByPart.get(row.partId) || []
    const messages = existing.map(plan => `已有未完成计划：目标 ${plan.total_qty}，已完成 ${plan.completed_qty}，剩余 ${plan.remaining_qty}，${materialStatusLabel(plan.material_status)}`)
    if ((draftCounts.get(row.partId) || 0) > 1) messages.unshift('本次录入中存在重复零件')
    row.duplicateMessage = messages.join('；')
  })
}

const addDraftRow = (): void => { draftRows.value.push(makeDraftRow()) }
const removeDraftRow = (index: number): void => {
  if (draftRows.value.length > 1) draftRows.value.splice(index, 1)
  refreshDuplicateWarnings()
}

const validateDraftRows = (): boolean => {
  for (const [index, row] of draftRows.value.entries()) {
    if (!row.partId || !row.part || !row.totalQty || row.totalQty < 1) {
      ElMessage.warning(`第 ${index + 1} 行需要选择零件并填写目标数量`)
      return false
    }
    if (!row.twpSourceSpecId) {
      ElMessage.warning(`第 ${index + 1} 行需要选择来源 TWP`)
      return false
    }
    const source = selectedTwpOption(row)
    const values = row.manualTwp ? row.manualValues : source
    if (!values?.thickness || !values.width || !values.pitch) {
      ElMessage.warning(`第 ${index + 1} 行 TWP 不完整，不能提交给资材`)
      return false
    }
  }
  return true
}

const buildBatchPayload = () => ({
  lines: draftRows.value.map(row => ({
    part_id: row.partId,
    total_qty: row.totalQty,
    twp_source_spec_id: row.twpSourceSpecId,
    manual_twp: row.manualTwp ? {
      thickness: row.manualValues.thickness,
      width: row.manualValues.width,
      pitch: row.manualValues.pitch,
    } : undefined,
    is_urgent: row.isUrgent,
    acknowledge_twp_change: row.acknowledgeTwpChange,
  })),
})

const submitPlans = async (): Promise<void> => {
  if (!validateDraftRows()) return
  submitting.value = true
  try {
    await productionApi.createBatch(buildBatchPayload())
    ElMessage.success('生产计划已提交给资材确认')
    draftRows.value = [makeDraftRow()]
    await loadWorkbench()
  } catch (error: unknown) {
    const response = (error as { response?: { status?: number; data?: { detail?: { twp_changes?: Array<{ previous_twp: string; current_twp: string }> } } } }).response
    const changes = response?.data?.detail?.twp_changes
    if (response?.status === 409 && changes?.length) {
      const text = changes.map(change => `${change.previous_twp} → ${change.current_twp}`).join('\n')
      try {
        await ElMessageBox.confirm(text, '零件 TWP 已变化', { confirmButtonText: '已知悉，继续提交', cancelButtonText: '返回检查', type: 'warning' })
        draftRows.value.forEach(row => { row.acknowledgeTwpChange = true })
        submitting.value = false
        await submitPlans()
        return
      } catch { /* User chose to revise the draft. */ }
    } else {
      ElMessage.error(error instanceof Error ? error.message : '提交生产计划失败')
    }
  } finally {
    submitting.value = false
  }
}

const handleSelectionChange = (rows: WorkbenchPlan[]): void => { selectedPlans.value = rows }

const confirmSelectedPlans = async (): Promise<void> => {
  const selected = selectedPendingPlans.value
  if (!selected.length) return
  try {
    const { value } = await ElMessageBox.prompt('确认备注（可留空，将写入所有已选计划）', '确认材料已备齐', {
      confirmButtonText: '确认已备齐', cancelButtonText: '取消', inputPlaceholder: '例如：材料已入库并备齐', inputType: 'textarea',
    })
    await productionApi.confirmMaterials({ plan_ids: selected.map(plan => plan.id), note: value || undefined })
    ElMessage.success(`已确认 ${selected.length} 条计划的材料备齐`)
    selectedPlans.value = []
    await loadWorkbench()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error(error instanceof Error ? error.message : '确认材料失败')
  }
}

const updateCalculationMode = async (plan: WorkbenchPlan, mode: CalculationMode): Promise<void> => {
  try {
    await productionApi.updatePlan(plan.id, { material_calculation_mode: mode })
    ElMessage.success(mode === 'auto' ? '将按系统理论用量显示' : '将由资材手动确认')
  } catch (error) {
    plan.material_calculation_mode = mode === 'auto' ? 'manual' : 'auto'
    ElMessage.error(error instanceof Error ? error.message : '更新用量方式失败')
  }
}

const handleCalculationChange = (plan: WorkbenchPlan, value: unknown): void => {
  if (value === 'auto' || value === 'manual') void updateCalculationMode(plan, value)
}

const cancelPlan = async (plan: WorkbenchPlan): Promise<void> => {
  try {
    const { value } = await ElMessageBox.prompt('取消原因会保留在此计划中。', '取消生产计划', {
      confirmButtonText: '取消计划', cancelButtonText: '返回', inputPattern: /\S+/, inputErrorMessage: '请填写取消原因', inputType: 'textarea',
    })
    await productionApi.cancelPlan(plan.id, { reason: value })
    ElMessage.success('生产计划已取消')
    await loadWorkbench()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error(error instanceof Error ? error.message : '取消计划失败')
  }
}

watch(linkedPlanId, loadWorkbench, { immediate: true })
</script>

<style scoped>
.linked-plan-notice { margin-bottom: 14px; }
.production-container { padding: 16px 0 28px; color: var(--zephyr-ink); font-size: 13px; }
.page-header, .section-heading, .queue-toolbar, .header-actions, .entry-actions, .queue-controls, .queue-title, .material-status, .queue-twp, .twp-cell, .manual-twp-inputs { display: flex; align-items: center; }
.page-header { justify-content: space-between; gap: 16px; margin-bottom: 16px; }
.page-header h1, .section-heading h2, .queue-title h2 { margin: 0; color: var(--zephyr-ink); font-weight: 650; }
.page-header h1 { font-size: 21px; line-height: 1.3; }
.page-header p, .section-heading p { margin: 4px 0 0; color: var(--zephyr-muted); font-size: 12px; line-height: 1.5; }
.header-actions { gap: 8px; }.sync-state { color: var(--zephyr-muted); font-size: 11px; }
.entry-panel, .queue-section { border-top: 1px solid var(--zephyr-border); background: #fff; }
.entry-panel { margin-bottom: 20px; border: 1px solid var(--zephyr-border); border-radius: 5px; }
.section-heading { min-height: 68px; justify-content: space-between; gap: 16px; padding: 12px 16px; border-bottom: 1px solid var(--zephyr-border-soft); }
.section-heading h2, .queue-title h2 { font-size: 15px; }.entry-actions { gap: 8px; }
.table-scroll { overflow-x: auto; scrollbar-gutter: stable; }.entry-table-wrap { min-width: 0; }
.entry-table { min-width: 960px; }.row-index, .numeric, .part-number { font-variant-numeric: tabular-nums slashed-zero; }.row-index { color: #849196; font: 12px ui-monospace, "Cascadia Mono", monospace; }
.part-picker, .paired-part-picker, .twp-cell > .el-select { width: 100%; }.paired-part-picker { display: block; margin-top: 4px; }.paired-part-picker :deep(.el-input__wrapper) { display: flex; box-sizing: border-box; width: 100%; background: #f3f8f6; box-shadow: 0 0 0 1px #bdd8d0 inset; }.paired-part-picker :deep(.el-input__inner) { width: 100%; min-width: 0; color: #2e665b; cursor: default; font-weight: 500; }.part-option { display: grid; grid-template-columns: minmax(95px, .8fr) minmax(0, 1.2fr); gap: 8px; align-items: center; }.part-option strong { color: var(--zephyr-ink); font: 12px ui-monospace, "Cascadia Mono", monospace; }.part-option span { overflow: hidden; color: #65747a; text-overflow: ellipsis; white-space: nowrap; }
.inline-warning, .paired-hint { margin: 4px 0 0; font-size: 11px; line-height: 1.35; }.inline-warning { color: #a06d20; }.paired-hint { color: #47736b; }.cell-text { color: #53646a; }.cell-hint { display: block; margin-top: 3px; color: #a06d20; font-size: 10px; }
.twp-cell { gap: 4px; min-width: 0; flex-wrap: wrap; }.twp-cell > .el-select { min-width: 180px; flex: 1; }.twp-source-value { color: #3b5f59; font: 11px ui-monospace, "Cascadia Mono", monospace; white-space: nowrap; }.manual-twp-inputs { gap: 4px; width: 100%; }.manual-twp-inputs :deep(.el-input-number) { width: 79px; }.manual-twp-inputs span { color: #819096; }.entry-note { margin: 0; padding: 9px 16px; border-top: 1px solid var(--zephyr-border-soft); color: var(--zephyr-muted); font-size: 11px; }
.queue-section { border-top: 0; }.queue-toolbar { min-height: 52px; justify-content: space-between; gap: 12px; padding-bottom: 10px; border-bottom: 1px solid var(--zephyr-border); }.queue-title { gap: 9px; }.queue-title span { color: #758489; font: 11px ui-monospace, "Cascadia Mono", monospace; }.queue-controls { justify-content: flex-end; gap: 8px; }.queue-controls :deep(.el-input) { width: 236px; }.queue-controls :deep(.el-select) { width: 116px; }
.status-strip { display: grid; grid-template-columns: 108px 108px 108px minmax(180px, 1fr); margin: 10px 0; border: 1px solid var(--zephyr-border); background: #fbfcfb; }.status-strip > div { display: grid; align-content: center; min-height: 54px; padding: 7px 12px; border-right: 1px solid var(--zephyr-border-soft); }.status-strip span { color: #78878c; font-size: 10px; }.status-strip strong { margin-top: 2px; color: var(--zephyr-ink); font: 650 20px ui-monospace, "Cascadia Mono", monospace; font-variant-numeric: tabular-nums; }.status-strip p { display: flex; align-items: center; margin: 0; padding: 8px 14px; color: var(--zephyr-muted); font-size: 11px; }
.queue-table { min-width: 1060px; }.part-number { color: var(--zephyr-primary); font-family: ui-monospace, "Cascadia Mono", monospace; }.queue-twp { align-items: flex-start; gap: 5px; flex-direction: column; color: #485d60; font: 11px ui-monospace, "Cascadia Mono", monospace; }.manual-flag { color: #a1691b; font-family: inherit; }.material-status { gap: 6px; color: #53646a; white-space: nowrap; }.material-status small { color: #8b7149; font-size: 10px; }.status-dot { width: 7px; height: 7px; border-radius: 50%; background: #bb7f26; }.status-dot.ready { background: #28785f; }.numeric { color: #3d5055; font-family: ui-monospace, "Cascadia Mono", monospace; }
:deep(.el-table) { --el-table-header-bg-color: var(--zephyr-surface-muted); --el-table-border-color: var(--zephyr-border); --el-table-row-hover-bg-color: var(--zephyr-primary-soft); --el-table-header-text-color: #5d6f74; --el-table-text-color: #415257; border: 0; border-radius: 0; font-size: 12px; }.entry-table :deep(.el-table__header-wrapper), .queue-table :deep(.el-table__header-wrapper) { position: sticky; top: 0; z-index: 2; }.entry-table :deep(th.el-table__cell), .queue-table :deep(th.el-table__cell) { height: 36px; padding: 0 8px; font-size: 11px; font-weight: 600; }.entry-table :deep(td.el-table__cell) { height: 58px; padding: 5px 8px; vertical-align: top; }.queue-table :deep(td.el-table__cell) { height: 44px; padding: 5px 8px; }.entry-table :deep(.cell), .queue-table :deep(.cell) { line-height: 1.35; }.entry-table :deep(.el-input-number .el-input__wrapper) { padding-right: 28px; }.entry-table :deep(.el-input-number), .queue-table :deep(.el-input-number) { width: 100%; }.entry-table :deep(.el-select__wrapper), .entry-table :deep(.el-input__wrapper), .queue-table :deep(.el-select__wrapper) { min-height: 30px; }.queue-table :deep(.el-table__row) { transition: background-color 80ms ease; }.queue-table :deep(.el-table__row:hover > td.el-table__cell) { background: var(--zephyr-primary-soft) !important; }:deep(.el-button.is-circle) { min-width: 30px; min-height: 30px; }
@media (max-width: 900px) { .page-header, .section-heading, .queue-toolbar { align-items: stretch; flex-direction: column; }.header-actions, .entry-actions, .queue-controls { justify-content: flex-start; flex-wrap: wrap; }.queue-controls :deep(.el-input) { width: min(100%, 360px); }.status-strip { grid-template-columns: repeat(3, 1fr); }.status-strip p { grid-column: 1 / -1; border-top: 1px solid var(--zephyr-border-soft); } }
@media (max-width: 620px) { .production-container { padding-top: 12px; }.section-heading, .entry-note { padding-right: 12px; padding-left: 12px; }.entry-actions :deep(.el-button), .queue-controls :deep(.el-button) { flex: 1; }.queue-controls :deep(.el-input), .queue-controls :deep(.el-select) { width: 100%; }.status-strip > div { padding: 7px 8px; }.sync-state { display: none; } }
@media (prefers-reduced-motion: reduce) { .queue-table :deep(.el-table__row) { transition: none; } }
</style>
