<template>
  <main class="scheduling-page" aria-labelledby="scheduling-title">
    <header class="page-header">
      <div>
        <p class="eyebrow">制造执行 / 生产排产</p>
        <h1 id="scheduling-title">生产排产</h1>
        <p class="page-lede">将资材已确认的生产计划，排入固定机台的等待队列。</p>
      </div>
      <div class="header-metrics" aria-label="排产摘要">
        <div><strong>{{ board.pending.length }}</strong><span>待排产</span></div>
        <div><strong>{{ scheduledCount }}</strong><span>已排入</span></div>
        <div><strong>{{ runningCount }}</strong><span>生产中</span></div>
      </div>
    </header>

    <section class="toolbar" aria-label="排产筛选">
      <label class="search-control">
        <el-icon><Search /></el-icon>
        <input v-model="search" aria-label="搜索待排产计划" placeholder="搜索客户件号或模具号" />
      </label>
      <div class="tonnage-filters" aria-label="机台吨位和类型筛选">
        <span>机台吨位/类型</span>
        <button type="button" :class="{ active: tonnageFilter === 'all' }" @click="tonnageFilter = 'all'">全部</button>
        <button v-for="tonnage in availableTonnages" :key="tonnage" type="button" :class="{ active: tonnageFilter === tonnage }" @click="tonnageFilter = tonnage">{{ tonnage }}T</button>
        <button type="button" :class="{ active: tonnageFilter === 'dual-axis' }" @click="tonnageFilter = 'dual-axis'">双轴</button>
      </div>
      <button class="refresh-button" type="button" :disabled="loading" @click="loadBoard">
        <el-icon><Refresh /></el-icon>刷新
      </button>
    </section>

    <div v-if="errorMessage" class="error-strip" role="alert">
      <span>{{ errorMessage }}</span>
      <button type="button" @click="loadBoard">重试</button>
    </div>

    <section class="scheduling-board" aria-label="生产排产工作台">
      <aside class="pending-panel" aria-labelledby="pending-title">
        <div class="panel-heading">
          <div><h2 id="pending-title">待排产</h2><p>仅显示资材已确认计划</p></div>
          <strong>{{ filteredPending.length }}</strong>
        </div>
        <div v-if="loading" class="state-message">正在读取排产计划…</div>
        <div v-else-if="filteredPending.length" class="pending-list">
          <article
            v-for="plan in filteredPending"
            :key="plan.id"
            class="plan-card"
            :class="{ selected: selectedPlanId === plan.id, urgent: plan.is_urgent, dragging: dragPlanId === plan.id || pointerDragPlanId === plan.id }"
            :draggable="false"
            tabindex="0"
            :aria-label="planAriaLabel(plan)"
            @dragstart="startPlanDrag(plan, $event)"
            @dragend="clearPlanDrag"
            @pointerdown="startPointerDrag(plan, $event)"
            @click="selectPlan(plan)"
            @keydown.enter.prevent="selectPlan(plan)"
          >
            <div class="plan-card-top">
              <strong>{{ displayPartNumbers(plan) }}</strong>
              <span v-if="plan.is_urgent" class="urgent-mark">加急</span>
            </div>
            <dl>
              <div><dt>模具号</dt><dd>{{ plan.tooling_number || '未维护' }}</dd></div>
              <div><dt>最低吨位</dt><dd>{{ plan.minimum_tonnage === null ? '未维护' : `${plan.minimum_tonnage}T` }}</dd></div>
            </dl>
            <div class="plan-card-foot">
              <span>订单量：<b>{{ formatQty(plan.total_qty) }}</b></span>
              <span v-if="plan.minimum_tonnage === null" class="special-notice">需特别确认</span>
            </div>
          </article>
        </div>
        <div v-else class="state-message">暂无符合条件的待排产计划</div>
        <p class="panel-note">点击计划卡片后，再点击机台，也可以完成排入。</p>
      </aside>

      <div class="machine-area" aria-label="固定机台队列">
        <div v-if="loading" class="machine-loading">正在读取固定机台…</div>
        <template v-else-if="visibleGroups.length">
          <section v-for="group in visibleGroups" :key="group.key" class="tonnage-group">
            <header class="group-heading"><h2>{{ group.label }}</h2><span>{{ group.machines.length }} 台固定机台</span></header>
            <div class="machine-list">
              <article
                v-for="machine in group.machines"
                :key="machine.id"
                class="machine-row"
                :data-machine-id="machine.id"
                :class="{ 'drop-target': canDropOnMachine(draggedPlan, machine), 'drop-blocked': draggedPlan && !canDropOnMachine(draggedPlan, machine) }"
                @dragover.prevent
                @drop.prevent="dropPlanOnMachine(machine)"
                @click="selectedPlan && dropSelectedPlanOnMachine(machine)"
              >
                <div class="machine-fixed">
                  <div class="machine-identity">
                    <strong>{{ machine.name }}</strong>
                    <span class="machine-type">{{ formatMachineType(machine) }}</span>
                    <span class="machine-meta">{{ machine.location || '未设置位置' }} · 队列 {{ machine.queue.length }}</span>
                  </div>
                  <div class="machine-actions">
                    <span class="machine-state" :class="machine.state">{{ machineStateLabel(machine.state) }}</span>
                    <button type="button" class="machine-detail-button" :aria-label="`编辑 ${machine.name} 资料`" @click.stop="openMachineDetails(machine)">
                      <el-icon><Edit /></el-icon>
                    </button>
                  </div>
                </div>
                <div class="queue-lane" @dragover.prevent @drop.prevent.stop="handleQueueLaneDrop(machine)">
                  <template v-if="machine.queue.length">
                    <article
                      v-for="(plan, index) in machine.queue"
                      :key="plan.id"
                      class="queue-item"
                      :class="{ current: index === 0 && machine.state === 'running' }"
                      :draggable="plan.status === 'queued'"
                      @dragstart.stop="plan.status === 'queued' && startQueueDrag(plan.id)"
                      @dragend="clearQueueDrag"
                      @dragover.prevent
                      @drop.prevent.stop="dropQueuePlan(machine, queueDragPlanId, plan.id)"
                    >
                      <span class="queue-index">{{ index === 0 && machine.state === 'running' ? '生产中' : `等待 ${index}` }}</span>
                      <strong>{{ displayPartNumbers(plan) }}</strong>
                      <span class="queue-tooling">{{ plan.tooling_number || '未维护模具号' }}</span>
                      <span class="queue-qty">订单量：{{ formatQty(plan.total_qty) }}<em v-if="plan.is_urgent">加急</em></span>
                      <button type="button" aria-label="移出排产队列" @click.stop="unschedule(plan)"><el-icon><Close /></el-icon></button>
                    </article>
                  </template>
                  <div v-else class="queue-empty">拖到此处排入队列</div>
                </div>
              </article>
            </div>
          </section>
        </template>
        <div v-else class="state-message">暂无固定机台主数据</div>
      </div>
    </section>

    <el-dialog
      v-model="machineDialogVisible"
      title="机台资料"
      width="520px"
      destroy-on-close
    >
      <div v-if="selectedMachine" class="machine-dialog-intro">
        <strong>{{ selectedMachine.machine_no }}</strong>
        <span>编辑后会同步到机台主数据和排产看板</span>
      </div>
      <el-form :model="machineForm" label-position="top" class="machine-edit-form">
        <div class="machine-edit-grid">
          <el-form-item label="机台名称">
            <el-input v-model="machineForm.name" maxlength="200" />
          </el-form-item>
          <el-form-item label="设备型号">
            <el-input v-model="machineForm.machine_type" maxlength="50" placeholder="例如：200T（双)料架" />
          </el-form-item>
          <el-form-item label="吨位（T）">
            <el-input-number v-model="machineForm.tonnage" :min="0" :max="2000" :precision="1" controls-position="right" />
          </el-form-item>
          <el-form-item label="位置">
            <el-input v-model="machineForm.location" maxlength="200" placeholder="例如：天越" />
          </el-form-item>
          <el-form-item label="台面尺寸">
            <el-input v-model="machineForm.bed_size" maxlength="100" placeholder="可选" />
          </el-form-item>
          <el-form-item label="最大行程">
            <el-input-number v-model="machineForm.max_stroke" :min="0" :max="10000" :precision="1" controls-position="right" />
          </el-form-item>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="machineDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="machineDialogLoading" @click="saveMachineDetails">保存</el-button>
      </template>
    </el-dialog>

    <p class="page-note">吨位不足、故障、维修或离线机台不会接受排产；未维护最低吨位的计划需要特别确认。排序仅调整等待队列顺序。</p>
  </main>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { Close, Edit, Refresh, Search } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { productionApi } from '@/api/production'
import { machinesApi } from '@/api/machines'

interface SchedulingPlan {
  id: number
  customer_part_no: string | null
  paired_customer_part_no: string | null
  tooling_number: string | null
  minimum_tonnage: number | null
  total_qty: number
  is_urgent: boolean
  material_status: 'pending' | 'ready'
  status: string
  machine_id: number | null
  plan_order: number | null
}

interface SchedulingMachine {
  id: number
  machine_no: string
  name: string
  machine_type: string | null
  tonnage: number | null
  max_stroke: number | null
  bed_size: string | null
  state: string
  location: string | null
  queue: SchedulingPlan[]
}

interface MachineEditForm {
  name: string
  machine_type: string
  tonnage: number | null
  max_stroke: number | null
  bed_size: string
  location: string
}

interface SchedulingBoard { pending: SchedulingPlan[]; machines: SchedulingMachine[] }
interface MachineGroup { key: string; tonnage: number | null; dualAxis: boolean; label: string; machines: SchedulingMachine[] }
type TonnageFilter = 'all' | 'dual-axis' | number

const board = ref<SchedulingBoard>({ pending: [], machines: [] })
const loading = ref(false)
const errorMessage = ref('')
const search = ref('')
const tonnageFilter = ref<TonnageFilter>('all')
const selectedPlanId = ref<number | null>(null)
const dragPlanId = ref<number | null>(null)
const queueDragPlanId = ref<number | null>(null)
const pointerDragPlanId = ref<number | null>(null)
const pointerDragActive = ref(false)
const pointerDragStart = ref({ x: 0, y: 0 })
const suppressNextPlanClick = ref(false)
const machineDialogVisible = ref(false)
const machineDialogLoading = ref(false)
const selectedMachine = ref<SchedulingMachine | null>(null)
const machineForm = ref<MachineEditForm>({
  name: '',
  machine_type: '',
  tonnage: null,
  max_stroke: null,
  bed_size: '',
  location: '',
})

const formatQty = (value: number) => value.toLocaleString('zh-CN')
const formatTonnage = (value: number | null) => value === null ? '未标注吨位' : `${value}T`
const formatMachineType = (machine: SchedulingMachine) => machine.machine_type || formatTonnage(machine.tonnage)
const isDualAxisMachine = (machine: SchedulingMachine) => {
  const machineType = machine.machine_type || ''
  return machineType.includes('双') && !machineType.includes('料架')
}
const displayPartNumbers = (plan: SchedulingPlan) => [plan.customer_part_no, plan.paired_customer_part_no].filter(Boolean).join(' / ') || '未维护客户件号'
const planAriaLabel = (plan: SchedulingPlan) => `${displayPartNumbers(plan)}，订单量 ${formatQty(plan.total_qty)}`
const machineStateLabel = (state: string) => ({ running: '生产中', idle: '空闲', fault: '故障', pending_check: '待确认', repairing: '维修中', offline: '离线' }[state] || state)

const scheduledPlans = computed(() => board.value.machines.flatMap(machine => machine.queue))
const scheduledCount = computed(() => scheduledPlans.value.length)
const runningCount = computed(() => board.value.machines.filter(machine => machine.state === 'running').length)
const availableTonnages = computed(() => [...new Set(board.value.machines.map(machine => machine.tonnage).filter((tonnage): tonnage is number => tonnage !== null))].sort((a, b) => a - b))
const filteredPending = computed(() => {
  const keyword = search.value.trim().toLowerCase()
  return board.value.pending.filter(plan => !keyword || `${displayPartNumbers(plan)} ${plan.tooling_number || ''}`.toLowerCase().includes(keyword))
})
const visibleGroups = computed<MachineGroup[]>(() => {
  const groups = new Map<string, { tonnage: number | null; dualAxis: boolean; machines: SchedulingMachine[] }>()
  board.value.machines.forEach(machine => {
    const dualAxis = isDualAxisMachine(machine)
    if (tonnageFilter.value === 'dual-axis' && !dualAxis) return
    if (typeof tonnageFilter.value === 'number' && machine.tonnage !== tonnageFilter.value) return
    const key = `${machine.tonnage ?? 'unknown'}-${dualAxis ? 'dual-axis' : 'standard'}`
    const group = groups.get(key) || { tonnage: machine.tonnage, dualAxis, machines: [] }
    group.machines.push(machine)
    groups.set(key, group)
  })
  return [...groups.entries()]
    .sort(([, a], [, b]) => (a.tonnage ?? Number.POSITIVE_INFINITY) - (b.tonnage ?? Number.POSITIVE_INFINITY) || Number(a.dualAxis) - Number(b.dualAxis))
    .map(([key, group]) => ({
      key,
      tonnage: group.tonnage,
      dualAxis: group.dualAxis,
      label: group.dualAxis ? `${formatTonnage(group.tonnage)}（双轴）` : formatTonnage(group.tonnage),
      machines: group.machines,
    }))
})
const selectedPlan = computed(() => board.value.pending.find(plan => plan.id === selectedPlanId.value) || null)
const draggedPlan = computed(() => board.value.pending.find(plan => plan.id === dragPlanId.value) || null)
const queuedDraggedPlan = computed(() => board.value.machines.flatMap(machine => machine.queue).find(plan => plan.id === queueDragPlanId.value) || null)

const loadBoard = async (): Promise<void> => {
  loading.value = true
  errorMessage.value = ''
  try {
    board.value = await productionApi.schedulingWorkbench<SchedulingBoard>()
    selectedPlanId.value = null
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '获取排产工作台失败'
  } finally {
    loading.value = false
  }
}

const selectPlan = (plan: SchedulingPlan) => {
  if (suppressNextPlanClick.value) {
    suppressNextPlanClick.value = false
    return
  }
  selectedPlanId.value = selectedPlanId.value === plan.id ? null : plan.id
}
const startPlanDrag = (plan: SchedulingPlan, event?: DragEvent) => {
  dragPlanId.value = plan.id
  if (event?.dataTransfer) {
    event.dataTransfer.effectAllowed = 'move'
    event.dataTransfer.setData('text/plain', String(plan.id))
  }
}
const clearPlanDrag = () => { dragPlanId.value = null }
const startQueueDrag = (planId: number) => { queueDragPlanId.value = planId }
const clearQueueDrag = () => { queueDragPlanId.value = null }
const stopPointerDrag = () => {
  pointerDragPlanId.value = null
  pointerDragActive.value = false
  document.body.style.removeProperty('cursor')
  window.removeEventListener('pointermove', handlePointerDragMove)
  window.removeEventListener('pointerup', handlePointerDragEnd)
}
const startPointerDrag = (plan: SchedulingPlan, event: PointerEvent) => {
  if (event.pointerType === 'mouse' && event.button !== 0) return
  pointerDragPlanId.value = plan.id
  pointerDragStart.value = { x: event.clientX, y: event.clientY }
  pointerDragActive.value = false
  ;(event.currentTarget as HTMLElement | null)?.setPointerCapture?.(event.pointerId)
  window.addEventListener('pointermove', handlePointerDragMove)
  window.addEventListener('pointerup', handlePointerDragEnd)
}
const handlePointerDragMove = (event: PointerEvent) => {
  if (pointerDragPlanId.value === null) return
  const moved = Math.hypot(event.clientX - pointerDragStart.value.x, event.clientY - pointerDragStart.value.y)
  if (!pointerDragActive.value && moved > 6) {
    pointerDragActive.value = true
    document.body.style.cursor = 'grabbing'
  }
  if (pointerDragActive.value) event.preventDefault()
}
const handlePointerDragEnd = (event: PointerEvent) => {
  const planId = pointerDragPlanId.value
  const wasDragging = pointerDragActive.value
  const target = document.elementFromPoint(event.clientX, event.clientY)?.closest<HTMLElement>('.machine-row')
  stopPointerDrag()
  if (!wasDragging || planId === null || !target) return
  const machineId = Number(target.dataset.machineId)
  const machine = board.value.machines.find(item => item.id === machineId)
  const plan = board.value.pending.find(item => item.id === planId) || scheduledPlans.value.find(item => item.id === planId)
  if (!machine || !plan) return
  suppressNextPlanClick.value = true
  void assignPlan(plan, machine)
}
const canDropOnMachine = (plan: SchedulingPlan | null, machine: SchedulingMachine) => {
  if (!plan || ['fault', 'pending_check', 'repairing', 'offline'].includes(machine.state)) return false
  return plan.minimum_tonnage === null || (machine.tonnage !== null && machine.tonnage >= plan.minimum_tonnage)
}

const assignPlan = async (plan: SchedulingPlan, machine: SchedulingMachine): Promise<void> => {
  if (!canDropOnMachine(plan, machine)) return
  let confirmMissingTonnage = false
  if (plan.minimum_tonnage === null) {
    if (!window.confirm('该计划未维护最低冲床吨位。确认后允许手动排入此机台吗？')) return
    confirmMissingTonnage = true
  }
  try {
    await productionApi.schedule(plan.id, { machine_id: machine.id, confirm_missing_tonnage: confirmMissingTonnage })
    ElMessage.success(`${displayPartNumbers(plan)} 已排入 ${machine.name}`)
    await loadBoard()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '排入队列失败')
  }
}
const dropPlanOnMachine = (machine: SchedulingMachine) => {
  const plan = draggedPlan.value || queuedDraggedPlan.value
  if (plan) void assignPlan(plan, machine)
  clearPlanDrag()
  clearQueueDrag()
}
const dropSelectedPlanOnMachine = (machine: SchedulingMachine) => { if (selectedPlan.value) void assignPlan(selectedPlan.value, machine) }
const handleQueueLaneDrop = (machine: SchedulingMachine) => {
  // The empty queue lane owns the drop event, so route pending cards directly
  // to the machine instead of relying on bubbling to the parent row.
  if (draggedPlan.value) {
    dropPlanOnMachine(machine)
    return
  }
  clearQueueDrag()
}

const unschedule = async (plan: SchedulingPlan): Promise<void> => {
  try {
    await productionApi.unschedule(plan.id)
    ElMessage.success(`${displayPartNumbers(plan)} 已移回待排产`)
    await loadBoard()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '移出队列失败')
  }
}

const dropQueuePlan = async (machine: SchedulingMachine, sourceId: number | null, targetId?: number): Promise<void> => {
  if (sourceId === null || targetId === undefined || sourceId === targetId) return
  const ids = machine.queue.map(plan => plan.id)
  const from = ids.indexOf(sourceId)
  const to = ids.indexOf(targetId)
  if (from < 0 || to < 0) return
  ids.splice(from, 1)
  ids.splice(ids.indexOf(targetId), 0, sourceId)
  try {
    await productionApi.reorder({ machine_id: machine.id, plan_ids: ids })
    await loadBoard()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '保存队列顺序失败')
  } finally {
    clearQueueDrag()
  }
}

const openMachineDetails = (machine: SchedulingMachine) => {
  selectedMachine.value = machine
  machineForm.value = {
    name: machine.name,
    machine_type: machine.machine_type || '',
    tonnage: machine.tonnage,
    max_stroke: machine.max_stroke,
    bed_size: machine.bed_size || '',
    location: machine.location || '',
  }
  machineDialogVisible.value = true
}

const saveMachineDetails = async () => {
  if (!selectedMachine.value) return
  machineDialogLoading.value = true
  try {
    await machinesApi.update(selectedMachine.value.id, {
      name: machineForm.value.name.trim(),
      machine_type: machineForm.value.machine_type.trim() || null,
      tonnage: machineForm.value.tonnage,
      max_stroke: machineForm.value.max_stroke,
      bed_size: machineForm.value.bed_size.trim() || null,
      location: machineForm.value.location.trim() || null,
    })
    ElMessage.success(`${selectedMachine.value.machine_no} 机台资料已更新`)
    machineDialogVisible.value = false
    await loadBoard()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '保存机台资料失败')
  } finally {
    machineDialogLoading.value = false
  }
}

onMounted(loadBoard)
onBeforeUnmount(stopPointerDrag)
</script>

<style scoped>
.scheduling-page { min-width: 0; padding: 18px 0 28px; color: var(--zephyr-ink, var(--zephyr-ink)); }
.page-header, .toolbar, .scheduling-board { min-width: 0; }
.page-header { display: flex; align-items: flex-end; justify-content: space-between; gap: 20px; padding-bottom: 16px; border-bottom: 1px solid var(--zephyr-border, var(--zephyr-border)); }
.eyebrow { margin: 0; color: #748487; font-size: 10px; font-weight: 700; letter-spacing: .1em; }
h1 { margin: 7px 0 4px; color: var(--zephyr-ink); font-size: 21px; letter-spacing: -.02em; }
.page-lede { margin: 0; color: var(--zephyr-muted); font-size: 12px; }
.header-metrics { display: flex; gap: 22px; }
.header-metrics div { display: grid; gap: 2px; min-width: 62px; }
.header-metrics strong { color: var(--zephyr-primary); font: 700 21px ui-monospace, monospace; font-variant-numeric: tabular-nums; }
.header-metrics span { color: #7d8b8e; font-size: 10px; }
.toolbar { display: flex; align-items: center; gap: 12px; padding: 12px 0; }
.search-control { display: flex; flex: 0 1 360px; align-items: center; gap: 7px; height: 32px; padding: 0 9px; border: 1px solid #cbd8d4; border-radius: 4px; background: #fff; color: #81908f; }
.search-control .el-icon { flex: 0 0 auto; font-size: 13px; }
.search-control input { width: 100%; min-width: 0; border: 0; outline: 0; color: #425454; font-size: 11px; }
.tonnage-filters { display: flex; align-items: center; gap: 5px; color: #7a898a; font-size: 10px; }
.tonnage-filters button, .refresh-button { min-height: 28px; padding: 0 9px; border: 1px solid #cfdbd8; border-radius: 3px; background: #fff; color: #657779; cursor: pointer; font-size: 10px; }
.tonnage-filters button.active, .tonnage-filters button:hover { border-color: var(--zephyr-primary); background: #e0f1ec; color: var(--zephyr-primary); font-weight: 700; }
.refresh-button { display: inline-flex; align-items: center; gap: 4px; margin-left: auto; }
.refresh-button .el-icon { font-size: 12px; }
.refresh-button:disabled { cursor: wait; opacity: .55; }
.error-strip { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 10px; padding: 8px 10px; border: 1px solid #e4c6bd; background: #fff8f5; color: #9c5b48; font-size: 11px; }
.error-strip button { border: 0; background: transparent; color: #8d4d3b; cursor: pointer; font-size: 11px; text-decoration: underline; }
.scheduling-board { display: grid; grid-template-columns: minmax(250px, .72fr) minmax(0, 1.85fr); gap: 14px; align-items: start; }
.pending-panel, .tonnage-group { min-width: 0; border: 1px solid #d4dfdc; border-radius: 5px; background: #fff; }
.pending-panel { padding: 13px; }
.panel-heading, .group-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; padding-bottom: 10px; border-bottom: 1px solid #e6ecea; }
.panel-heading h2, .group-heading h2 { margin: 0; color: #29403e; font-size: 14px; }
.panel-heading p { margin: 3px 0 0; color: #8a9898; font-size: 10px; }
.panel-heading > strong { color: var(--zephyr-primary); font: 700 18px ui-monospace, monospace; font-variant-numeric: tabular-nums; }
.pending-list { display: grid; gap: 8px; padding-top: 10px; }
.plan-card { padding: 10px 10px 8px; border: 1px solid #d7e2df; border-left: 3px solid #a6c2ba; border-radius: 4px; background: #fbfdfc; cursor: grab; touch-action: none; user-select: none; transition: border-color 120ms ease, box-shadow 120ms ease, transform 120ms ease; }
.plan-card:hover, .plan-card:focus-visible, .plan-card.selected { border-color: #75a99b; box-shadow: 0 4px 12px rgba(86, 101, 168, .1); transform: translateY(-1px); outline: 0; }
.plan-card.selected { background: #eff9f5; }.plan-card.dragging { opacity: .58; cursor: grabbing; }.plan-card.urgent { border-left-color: #bd7d2e; }
.plan-card-top { display: flex; align-items: flex-start; justify-content: space-between; gap: 7px; }
.plan-card-top strong { color: #29403e; font: 700 12px ui-monospace, monospace; }
.urgent-mark { color: #a66b21; font-size: 10px; font-weight: 700; white-space: nowrap; }
.plan-card dl { display: grid; grid-template-columns: 1.35fr .8fr; gap: 8px; margin: 9px 0 8px; }.plan-card dt { color: #8b9999; font-size: 9px; }.plan-card dd { overflow: hidden; margin: 3px 0 0; color: #526467; font: 10px ui-monospace, monospace; text-overflow: ellipsis; white-space: nowrap; }
.plan-card-foot { display: flex; align-items: center; justify-content: space-between; gap: 7px; padding-top: 8px; border-top: 1px solid #e8eeec; color: #718181; font-size: 10px; }.plan-card-foot b { color: #315c53; font: 700 11px ui-monospace, monospace; }.special-notice { color: #a66b21; font-size: 9px; }
.panel-note, .page-note { color: #859390; font-size: 10px; line-height: 1.5; }.panel-note { margin: 11px 0 0; }.page-note { margin: 12px 0 0; }
.machine-area { display: grid; gap: 12px; min-width: 0; }.group-heading { align-items: baseline; padding: 13px 13px 9px; }.group-heading h2 { color: var(--zephyr-primary); font: 700 15px ui-monospace, monospace; }.group-heading span { color: #8a9898; font-size: 10px; }
.machine-list { display: grid; gap: 7px; padding: 9px 13px 13px; }.machine-row { display: grid; grid-template-columns: 190px minmax(0, 1fr); min-width: 0; border: 1px solid #e0e8e6; border-radius: 4px; background: #fbfcfc; }.machine-row.drop-target { border-color: #4f9b86; background: #f0faf6; box-shadow: 0 0 0 2px rgba(79, 155, 134, .13); }.machine-row.drop-blocked { opacity: .62; }
.machine-fixed { display: flex; align-items: center; justify-content: space-between; gap: 8px; min-width: 0; padding: 9px 10px; border-right: 1px solid #e1e9e7; }.machine-identity { min-width: 0; }.machine-fixed strong { display: block; color: #344a4a; font-size: 12px; }.machine-type { display: block; margin-top: 3px; overflow: hidden; color: #58736f; font-size: 10px; font-weight: 600; text-overflow: ellipsis; white-space: nowrap; }.machine-meta { display: block; margin-top: 3px; overflow: hidden; color: #8b9999; font-size: 9px; text-overflow: ellipsis; white-space: nowrap; }.machine-actions { display: flex; flex: 0 0 auto; align-items: center; gap: 4px; }.machine-state { flex: 0 0 auto; padding: 3px 5px; border-radius: 3px; font-size: 9px; }.machine-detail-button { display: grid; place-items: center; width: 24px; height: 24px; border: 0; border-radius: 3px; background: transparent; color: #6c8580; cursor: pointer; }.machine-detail-button:hover, .machine-detail-button:focus-visible { background: #e0f1ec; color: var(--zephyr-primary); outline: 0; }.machine-state.running { background: #e0f1eb; color: #27765f; }.machine-state.idle { background: #edf2f2; color: #687b7d; }.machine-state.fault, .machine-state.pending_check, .machine-state.repairing, .machine-state.offline { background: #f9e9e1; color: #a95e42; }
.queue-lane { display: flex; min-width: 0; align-items: center; gap: 7px; min-height: 52px; padding: 7px 9px; overflow-x: auto; scrollbar-gutter: stable; }.queue-item { display: grid; grid-template-columns: auto minmax(125px, auto) auto auto 22px; align-items: center; gap: 7px; min-width: 430px; min-height: 36px; padding: 0 7px; border: 1px solid #d7e2df; border-radius: 3px; background: #fff; cursor: grab; }.queue-item.current { border-color: #95c2b5; background: #eef8f4; }.queue-index { color: #6d8780; font-size: 9px; white-space: nowrap; }.queue-item strong { overflow: hidden; color: #36504d; font: 700 10px ui-monospace, monospace; text-overflow: ellipsis; white-space: nowrap; }.queue-tooling, .queue-qty { color: #82918f; font: 9px ui-monospace, monospace; white-space: nowrap; }.queue-qty em { margin-left: 5px; color: #a66b21; font-style: normal; font-weight: 700; }.queue-item button { display: grid; place-items: center; width: 22px; height: 22px; border: 0; border-radius: 3px; background: transparent; color: #9baaa6; cursor: pointer; }.queue-item button .el-icon { font-size: 12px; }.queue-item button:hover { background: #f3e8e5; color: #a95e42; }.queue-empty, .state-message, .machine-loading { padding: 22px 10px; color: #94a19f; font-size: 10px; text-align: center; }
.machine-dialog-intro { display: grid; gap: 4px; margin-bottom: 12px; padding: 10px 12px; border: 1px solid #d8e5e1; border-radius: 5px; background: #f5faf8; }.machine-dialog-intro strong { color: var(--zephyr-primary); font: 700 14px ui-monospace, monospace; }.machine-dialog-intro span { color: #718181; font-size: 11px; }.machine-edit-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); column-gap: 14px; }.machine-edit-form :deep(.el-form-item) { margin-bottom: 14px; }.machine-edit-form :deep(.el-input-number) { width: 100%; }
@media (max-width: 1100px) { .scheduling-board { grid-template-columns: 1fr; } }
@media (max-width: 700px) { .page-header, .toolbar { align-items: stretch; flex-direction: column; }.header-metrics { justify-content: space-between; }.search-control { flex-basis: auto; width: 100%; }.tonnage-filters { flex-wrap: wrap; }.refresh-button { margin-left: 0; align-self: flex-start; }.machine-row { grid-template-columns: 1fr; }.machine-fixed { border-right: 0; border-bottom: 1px solid #e1e9e7; }.queue-item { min-width: 365px; }.machine-edit-grid { grid-template-columns: 1fr; } }
@media (prefers-reduced-motion: reduce) { .plan-card { transition: none; } }
</style>
