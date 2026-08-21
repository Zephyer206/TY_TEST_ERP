<template>
  <main class="preview-page">
    <header class="page-head">
      <div>
        <p class="eyebrow">ZEPHYR ERP / DESIGN REVIEW</p>
        <h1>两套制造工作台，放在同一批业务数据上比较</h1>
        <p class="lede">A 方案偏档案与列表工作台；B 方案偏实时控制台与高密度数据。两者都遵循四大业务导航，不显示自动生成 ID。</p>
      </div>
      <div class="review-note">
        <span class="note-label">本轮评审关注</span>
        <strong>层级 · 密度 · 任务路径</strong>
        <small>用于决定正式零件模块的长期设计基线</small>
      </div>
    </header>

    <section class="comparison" aria-label="两套 UI 方案对比">
      <article class="option-card option-craft">
        <div class="option-head">
          <div class="option-title">
            <span class="option-index">A</span>
            <div>
              <p class="option-kicker">UI CRAFT / SHARP GEOMETRIC</p>
              <h2>档案工作台</h2>
              <p>精确网格、克制青绿、档案优先的日常业务界面。</p>
            </div>
          </div>
          <button type="button" class="select-button" :class="{ selected: selected === 'craft' }" @click="selected = 'craft'">
            <el-icon><CircleCheck v-if="selected === 'craft'" /><ArrowRight v-else /></el-icon>
            {{ selected === 'craft' ? '当前参考' : '选用此方案' }}
          </button>
        </div>

        <div class="craft-shell">
          <header class="craft-topbar">
            <span class="brand-square">Z</span>
            <strong>Zephyr ERP</strong>
            <span class="topbar-divider" />
            <span class="topbar-context">产品 / 零件档案</span>
            <span class="topbar-spacer" />
            <span class="online-state"><i /> 已同步</span>
            <button type="button" class="icon-button" aria-label="搜索"><el-icon><Search /></el-icon></button>
            <span class="user-label">王工</span>
          </header>
          <div class="craft-body">
            <aside class="craft-nav">
              <p class="nav-caption">业务导航</p>
              <button type="button" class="nav-link active"><el-icon><Grid /></el-icon>产品</button>
              <button type="button" class="nav-link"><el-icon><Connection /></el-icon>工艺与生产</button>
              <button type="button" class="nav-link"><el-icon><Files /></el-icon>库存</button>
              <button type="button" class="nav-link"><el-icon><DocumentChecked /></el-icon>客户与报价</button>
              <span class="nav-line" />
              <p class="nav-caption">最近访问</p>
              <button type="button" class="nav-link muted">零件档案</button>
              <button type="button" class="nav-link muted">修改历史</button>
            </aside>
            <div class="craft-main">
              <div class="craft-heading">
                <div><span class="breadcrumb">产品 / 零件</span><h3>零件档案</h3></div>
                <button type="button" class="primary-button"><el-icon><Plus /></el-icon>新建零件</button>
              </div>
              <div class="craft-toolbar">
                <label class="search-box"><el-icon><Search /></el-icon><input aria-label="搜索零件" placeholder="搜索零件名称、客户件号或材料" /><kbd>⌘ K</kbd></label>
                <button type="button" class="toolbar-link"><el-icon><Filter /></el-icon>筛选</button>
                <button type="button" class="toolbar-link">分组</button>
                <span class="count-label">1,248 条记录</span>
              </div>
              <div class="table-wrap">
                <table class="craft-table">
                  <thead><tr><th>零件</th><th>客户件号</th><th>TWP</th><th>材料</th><th>模具</th><th>状态</th></tr></thead>
                  <tbody>
                    <tr v-for="row in rows" :key="row.part"><td><strong>{{ row.name }}</strong><small>{{ row.part }}</small></td><td>{{ row.customer }}</td><td class="mono">{{ row.twp }}</td><td>{{ row.material }}</td><td>{{ row.tooling }}</td><td><span class="status" :class="row.statusClass">{{ row.status }}</span></td></tr>
                  </tbody>
                </table>
              </div>
              <footer class="table-foot"><span>已选 0 条</span><span>每页 20 · 1 / 63 <el-icon><ArrowRight /></el-icon></span></footer>
            </div>
          </div>
        </div>
        <p class="option-foot"><strong>适合：</strong>产品、零件、材料、包装、客户报价等需要稳定浏览与进入详情的页面。</p>
      </article>

      <article class="option-card option-dense">
        <div class="option-head">
          <div class="option-title">
            <span class="option-index">B</span>
            <div>
              <p class="option-kicker">UI CRAFT DENSE DASHBOARD</p>
              <h2>制造控制台</h2>
              <p>IBM Plex 字体、4/8px 网格、状态优先的实时异常处理。</p>
            </div>
          </div>
          <button type="button" class="select-button" :class="{ selected: selected === 'dense' }" @click="selected = 'dense'">
            <el-icon><CircleCheck v-if="selected === 'dense'" /><ArrowRight v-else /></el-icon>
            {{ selected === 'dense' ? '当前参考' : '选用此方案' }}
          </button>
        </div>

        <div class="dense-shell">
          <header class="dense-topbar">
            <div class="dense-brand"><span class="dense-mark">Z</span><strong>制造控制台</strong><kbd>⌘ K</kbd></div>
            <span class="dense-live"><i /> LIVE · 08:54:12</span>
            <button type="button" class="dense-icon" aria-label="更多操作"><el-icon><MoreFilled /></el-icon></button>
          </header>
          <div class="dense-body">
            <aside class="dense-rail">
              <p class="dense-caption">工作队列</p>
              <button type="button" class="dense-nav active"><i class="dot danger" /><span>待确认规格</span><b>06</b></button>
              <button type="button" class="dense-nav"><i class="dot warning" /><span>排产影响</span><b>04</b></button>
              <button type="button" class="dense-nav"><i class="dot info" /><span>最近修改</span><b>09</b></button>
              <span class="dense-rule" />
              <p class="dense-caption">生产概览</p>
              <div class="rail-metric"><strong>24</strong><span>个零件<br />正在生产</span></div>
              <div class="rail-progress"><i style="width: 72%" /></div>
              <small>72% 今日完成</small>
            </aside>
            <div class="dense-main">
              <div class="dense-heading"><div><span class="dense-breadcrumb">工艺与生产 / 控制台</span><h3>需要处理</h3></div><button type="button" class="dense-primary"><el-icon><Plus /></el-icon>新建任务</button></div>
              <div class="dense-tabs"><button type="button" class="active">全部 <b>12</b></button><button type="button">影响排产 <b>4</b></button><button type="button">最近变更</button><span><el-icon><Filter /></el-icon>仅看我的</span></div>
              <div class="alert-list">
                <article v-for="alert in alerts" :key="alert.title" class="dense-alert"><i class="alert-dot" :class="alert.level" /><div><strong>{{ alert.title }}</strong><p>{{ alert.detail }}</p><small>{{ alert.part }} · {{ alert.owner }}</small></div><time>{{ alert.time }}</time><button type="button" aria-label="打开异常"><el-icon><ArrowRight /></el-icon></button></article>
              </div>
            </div>
            <aside class="dense-inspector">
              <p class="dense-caption">修改历史</p>
              <div class="health-number"><strong>04</strong><span> 条记录</span></div>
              <p class="inspector-copy">最近更新的零件档案与模具关联</p>
              <div class="health-track"><i style="width: 72%" /></div>
              <div class="health-legend"><span><i class="ok" />主信息 <b>02</b></span><span><i class="warn" />模具关联 <b>01</b></span><span><i class="bad" />TWP <b>01</b></span></div>
              <span class="dense-rule" />
              <p class="dense-caption">本周影响</p>
              <div class="impact-number"><strong>04</strong><span>个零件<br />需要调整排产</span></div>
              <button type="button" class="inspector-link">查看影响计划 <el-icon><ArrowRight /></el-icon></button>
            </aside>
          </div>
          <footer class="dense-shortcuts"><span><kbd>J</kbd><kbd>K</kbd> 浏览队列</span><span><kbd>E</kbd> 编辑详情</span><span><kbd>↵</kbd> 打开记录</span><span class="shortcut-spacer" /><span>更新于 8 秒前</span></footer>
        </div>
        <p class="option-foot"><strong>适合：</strong>生产计划、异常处理和班组需要持续盯住的制造控制台。</p>
      </article>
    </section>

    <section class="production-preview" aria-labelledby="production-preview-title">
      <div class="production-preview-head">
        <div>
          <p class="eyebrow">PRODUCTION / SCHEDULING PREVIEW</p>
          <h2 id="production-preview-title">生产排产</h2>
          <p>从已确认的订单卡片出发，拖入满足最低吨位的固定机台队列。</p>
        </div>
        <div class="production-summary" aria-label="排产摘要">
          <span><b>{{ unassignedOrders.length }}</b> 待排产</span>
          <span><b>{{ scheduledCount }}</b> 已排入</span>
          <span><b>{{ machineGroups.flatMap(group => group.machines).filter(machine => machine.state === 'running').length }}</b> 台运行中</span>
        </div>
      </div>

      <div class="production-toolbar">
        <label class="production-search"><el-icon><Search /></el-icon><input v-model="productionSearch" aria-label="搜索待排产订单" placeholder="搜索件号或模具号" /></label>
        <div class="tonnage-filter" aria-label="固定机台吨位筛选">
          <span>机台吨位</span>
          <button type="button" :class="{ active: dispatchTonnage === 'all' }" @click="dispatchTonnage = 'all'">全部</button>
          <button v-for="tonnage in availableTonnages" :key="tonnage" type="button" :class="{ active: dispatchTonnage === tonnage }" @click="dispatchTonnage = tonnage">{{ tonnage }}T</button>
        </div>
      </div>

      <div class="production-board">
        <aside class="order-pool" aria-label="待排产订单">
          <div class="board-section-head"><div><h3>待排产</h3><span>仅显示资材已确认订单</span></div><strong>{{ filteredOrders.length }}</strong></div>
          <div v-if="filteredOrders.length" class="order-list">
            <article
              v-for="order in filteredOrders"
              :key="order.id"
              class="order-card"
              :class="{ urgent: order.urgent, dragging: dragOrderId === order.id, selected: selectedOrderId === order.id }"
              draggable="true"
              tabindex="0"
              :aria-label="`${order.partNumbers}，最低吨位 ${order.minTonnage}T，订单量 ${order.quantity}`"
              @dragstart="startOrderDrag(order)"
              @dragend="clearOrderDrag"
              @click="selectOrder(order)"
            >
              <div class="order-card-top"><strong>{{ order.partNumbers }}</strong><span v-if="order.urgent" class="urgent-mark">加急</span></div>
              <dl><div><dt>模具号</dt><dd>{{ order.toolingNo }}</dd></div><div><dt>最低吨位</dt><dd>{{ order.minTonnage ? `${order.minTonnage}T` : '未维护' }}</dd></div></dl>
              <div class="order-card-foot"><span>订单量：<b>{{ order.quantity.toLocaleString() }}</b></span><span v-if="!order.minTonnage" class="special-notice">需特别确认</span></div>
            </article>
          </div>
          <div v-else class="pool-empty">没有符合筛选条件的待排产订单</div>
        </aside>

        <div class="machine-queues" aria-label="固定机台队列">
          <div v-for="group in visibleMachineGroups" :key="group.tonnage" class="tonnage-group">
            <div class="tonnage-group-head"><h3>{{ group.tonnage }}T</h3><span>{{ group.machines.length }} 台固定机台</span></div>
            <div class="machine-list">
              <article
                v-for="machine in group.machines"
                :key="machine.id"
                class="machine-row"
                :class="{ 'drop-target': dragOrderId !== null && canDropOnMachine(draggedOrder, machine), 'drop-blocked': dragOrderId !== null && !canDropOnMachine(draggedOrder, machine) }"
                @dragover.prevent
                @drop.prevent="dropOrderOnMachine(machine)"
                @click="selectedOrder && dropSelectedOrderOnMachine(machine)"
              >
                <div class="machine-fixed"><div><strong>{{ machine.name }}</strong><span>{{ machine.tonnage }}T · {{ machine.location }}</span></div><span class="machine-state" :class="machine.state">{{ machineStateLabel(machine.state) }}</span></div>
                <div class="queue-lane">
                  <template v-if="machine.queue.length">
                    <div v-for="(item, index) in machine.queue" :key="item.id" class="queue-item" :class="{ current: index === 0 && machine.state === 'running' }"><span class="queue-index">{{ index === 0 && machine.state === 'running' ? '生产中' : `等待 ${index}` }}</span><strong>{{ item.partNumbers }}</strong><span class="queue-tooling">{{ item.toolingNo }} · {{ item.quantity.toLocaleString() }}</span><button type="button" aria-label="移出排产队列" @click="removeFromQueue(machine, item.id)"><el-icon><Close /></el-icon></button></div>
                  </template>
                  <div v-else class="queue-empty">拖到此处排入队列</div>
                </div>
              </article>
            </div>
          </div>
        </div>
      </div>
      <p class="production-note">吨位不足的机台不会接受拖放；未维护最低吨位的订单拖入时会要求特别确认。拖放仅为设计预览，不会写入正式排产数据。</p>
    </section>

    <footer class="decision-bar">
      <span>当前选择</span><strong>{{ selected === 'craft' ? 'A · 档案工作台' : 'B · 制造控制台' }}</strong><small>点击上方“选用此方案”切换评审基线；本页仅用于视觉决策，不会修改正式业务页面。</small>
    </footer>
  </main>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { ArrowRight, CircleCheck, Close, Connection, DocumentChecked, Files, Filter, Grid, MoreFilled, Plus, Search } from '@element-plus/icons-vue'

type OptionId = 'craft' | 'dense'
const selected = ref<OptionId>('craft')
const rows = [
  { part: 'TYF-Q0047-1', name: '左侧支架', customer: '35D041348', twp: '0.4 × 130 × 62', material: 'SPCC', tooling: '连续模', status: '量产', statusClass: 'success' },
  { part: 'TYF-Q0061', name: '回位弹簧座', customer: 'LS00317', twp: '0.8 × 54 × 51', material: 'SUS304', tooling: '简易模', status: '待确认', statusClass: 'warning' },
  { part: 'TYG-Q0071', name: '支架', customer: 'HT-00371', twp: '0.6 × 76 × 74', material: 'SPCC', tooling: '连续模', status: '量产', statusClass: 'success' },
]
const alerts = [
  { level: 'high', title: '主规格存在多个候选项', detail: '同一连续模下有 2 条 TWP 候选规格，需要确认生产主规格。', part: 'TYF-Q0061', owner: '工程组', time: '12 分钟前' },
  { level: 'medium', title: '左右件尚未设置关联', detail: '当前零件尚未建立左右件关联，请在模具关联中确认。', part: 'TYG-Q0071', owner: '技术员', time: '1 小时前' },
  { level: 'low', title: '材料牌号与厚度等待备注确认', detail: '保留来源备注，等待数据管理员确认。', part: 'TYAP-Q0092', owner: '数据管理员', time: '昨天' },
]

type DispatchTonnage = 'all' | number
type MachineState = 'running' | 'idle' | 'fault'
interface DispatchOrder { id: string; partNumbers: string; toolingNo: string; minTonnage: number | null; quantity: number; urgent: boolean }
interface QueueMachine { id: string; name: string; tonnage: number; location: string; state: MachineState; queue: DispatchOrder[] }
interface MachineGroup { tonnage: number; machines: QueueMachine[] }

const productionSearch = ref('')
const dispatchTonnage = ref<DispatchTonnage>('all')
const dragOrderId = ref<string | null>(null)
const selectedOrderId = ref<string | null>(null)
const orders = ref<DispatchOrder[]>([
  { id: 'dispatch-1', partNumbers: '60015399 / 60015400', toolingNo: 'TYAA-Q0085-1', minTonnage: 110, quantity: 8000, urgent: true },
  { id: 'dispatch-2', partNumbers: '60015421', toolingNo: 'TYAA-Q0091', minTonnage: 110, quantity: 4200, urgent: false },
  { id: 'dispatch-3', partNumbers: 'TYAB-Q0032', toolingNo: 'TYAB-Q0032-2', minTonnage: 160, quantity: 12000, urgent: false },
  { id: 'dispatch-4', partNumbers: '60015508 / 60015509', toolingNo: 'TYAC-Q0018', minTonnage: null, quantity: 2500, urgent: true },
])
const machineGroups = ref<MachineGroup[]>([
  { tonnage: 110, machines: [
    { id: 'machine-1', name: '1号机', tonnage: 110, location: '冲压一区', state: 'running', queue: [{ id: 'running-1', partNumbers: '60015220', toolingNo: 'TYAA-Q0072', minTonnage: 110, quantity: 3000, urgent: false }] },
    { id: 'machine-2', name: '2号机', tonnage: 110, location: '冲压一区', state: 'idle', queue: [] },
  ] },
  { tonnage: 160, machines: [
    { id: 'machine-3', name: '3号机', tonnage: 160, location: '冲压二区', state: 'idle', queue: [{ id: 'queued-1', partNumbers: '60015381', toolingNo: 'TYAB-Q0026', minTonnage: 160, quantity: 5600, urgent: false }] },
    { id: 'machine-4', name: '4号机', tonnage: 160, location: '冲压二区', state: 'fault', queue: [] },
  ] },
])
const scheduledIds = computed(() => new Set(machineGroups.value.flatMap(group => group.machines.flatMap(machine => machine.queue.map(item => item.id)))))
const unassignedOrders = computed(() => orders.value.filter(order => !scheduledIds.value.has(order.id)))
const scheduledCount = computed(() => orders.value.length - unassignedOrders.value.length)
const availableTonnages = computed(() => machineGroups.value.map(group => group.tonnage))
const filteredOrders = computed(() => {
  const keyword = productionSearch.value.trim().toLowerCase()
  return unassignedOrders.value.filter(order => !keyword || `${order.partNumbers} ${order.toolingNo}`.toLowerCase().includes(keyword))
})
const visibleMachineGroups = computed(() => dispatchTonnage.value === 'all' ? machineGroups.value : machineGroups.value.filter(group => group.tonnage === dispatchTonnage.value))
const draggedOrder = computed(() => orders.value.find(order => order.id === dragOrderId.value) || null)
const selectedOrder = computed(() => orders.value.find(order => order.id === selectedOrderId.value && !scheduledIds.value.has(order.id)) || null)
const machineStateLabel = (state: MachineState) => ({ running: '生产中', idle: '空闲', fault: '故障' })[state]
const startOrderDrag = (order: DispatchOrder) => { dragOrderId.value = order.id }
const clearOrderDrag = () => { dragOrderId.value = null }
const selectOrder = (order: DispatchOrder) => { selectedOrderId.value = selectedOrderId.value === order.id ? null : order.id }
const canDropOnMachine = (order: DispatchOrder | null, machine: QueueMachine) => Boolean(order && machine.state === 'idle' && (order.minTonnage === null || machine.tonnage >= order.minTonnage))
const dropOrderOnMachine = (machine: QueueMachine) => {
  const order = draggedOrder.value
  if (!order || !canDropOnMachine(order, machine)) return
  if (!order.minTonnage && !window.confirm('该订单未维护最低冲床吨位。确认后允许手动排入此机台吗？')) return
  machine.queue.push(order)
  dragOrderId.value = null
  selectedOrderId.value = null
}
const dropSelectedOrderOnMachine = (machine: QueueMachine) => {
  const order = selectedOrder.value
  if (!order || !canDropOnMachine(order, machine)) return
  if (!order.minTonnage && !window.confirm('该订单未维护最低冲床吨位。确认后允许手动排入此机台吗？')) return
  machine.queue.push(order)
  selectedOrderId.value = null
}
const removeFromQueue = (machine: QueueMachine, orderId: string) => {
  const index = machine.queue.findIndex(item => item.id === orderId)
  if (index >= 0) machine.queue.splice(index, 1)
}
</script>

<style scoped>
:global(*) { box-sizing: border-box; }
:global(button), :global(input) { font: inherit; }
:global(button:focus-visible), :global(input:focus-visible) { outline: 3px solid rgba(23, 107, 90, .28); outline-offset: 2px; }
.preview-page { min-height: 100%; padding: 34px 28px 52px; color: #202b2f; background: #eef1f0; }
.page-head, .comparison, .decision-bar { width: min(1480px, 100%); margin: 0 auto; }
.page-head { display: flex; align-items: flex-end; justify-content: space-between; gap: 28px; margin-bottom: 26px; }
.eyebrow, .option-kicker, .nav-caption, .dense-caption, .note-label, .breadcrumb, .dense-breadcrumb { margin: 0; color: #738186; font-size: 10px; font-weight: 700; letter-spacing: .1em; text-transform: uppercase; }
.page-head h1 { margin: 9px 0 6px; color: #1a292b; font-size: clamp(24px, 3vw, 34px); letter-spacing: -.035em; line-height: 1.08; }
.lede { max-width: 760px; margin: 0; color: #66757a; font-size: 13px; line-height: 1.65; }
.review-note { display: flex; min-width: 245px; flex-direction: column; gap: 5px; padding: 14px 16px; border-left: 3px solid #176b5a; background: #fff; box-shadow: 0 8px 24px rgba(23, 42, 45, .06); }
.review-note strong { color: #213b36; font-size: 13px; }.review-note small { color: #839095; font-size: 10px; line-height: 1.45; }
.comparison { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 22px; }
.option-card { min-width: 0; overflow: hidden; border: 1px solid #d5dddc; border-radius: 8px; background: #fff; box-shadow: 0 14px 34px rgba(26, 44, 47, .08); }
.option-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 18px; padding: 20px 21px 18px; border-bottom: 1px solid #e2e8e7; }
.option-title { display: flex; gap: 12px; min-width: 0; }.option-index { display: grid; flex: 0 0 auto; width: 28px; height: 28px; place-items: center; border: 1px solid #b7c9c5; border-radius: 5px; color: #176b5a; font: 700 12px ui-monospace, monospace; }
.option-kicker { color: #78918b; font-size: 9px; letter-spacing: .12em; }.option-head h2 { margin: 5px 0 4px; color: #1e3030; font-size: 21px; letter-spacing: -.025em; }.option-head p:not(.option-kicker) { margin: 0; color: #6e7c80; font-size: 11px; line-height: 1.45; }
.select-button { display: inline-flex; flex: 0 0 auto; align-items: center; gap: 5px; min-height: 32px; padding: 0 10px; border: 1px solid #c6d2d0; border-radius: 4px; background: #fff; color: #607074; cursor: pointer; font-size: 10px; white-space: nowrap; }.select-button.selected { border-color: #176b5a; background: #176b5a; color: #fff; }
.craft-shell, .dense-shell { margin: 18px; overflow: hidden; border: 1px solid #cdd8d6; border-radius: 5px; }.craft-shell { background: #fff; }.craft-topbar, .dense-topbar { display: flex; align-items: center; gap: 9px; height: 42px; padding: 0 13px; color: #e9f1ef; font-size: 10px; }.craft-topbar { background: #263b3b; }.brand-square, .dense-mark { display: grid; width: 21px; height: 21px; place-items: center; border-radius: 3px; background: #d9eeea; color: #1d4d43; font-weight: 800; }.craft-topbar strong { color: #f7fffd; font-size: 12px; }.topbar-divider { width: 1px; height: 15px; background: rgba(255,255,255,.25); }.topbar-context { color: #b9cfca; }.topbar-spacer { flex: 1; }.online-state { display: inline-flex; align-items: center; gap: 5px; color: #a9d3c4; font-size: 9px; }.online-state i, .dense-live i { width: 6px; height: 6px; border-radius: 50%; background: #61c49a; }.icon-button, .dense-icon { display: grid; width: 25px; height: 25px; place-items: center; border: 0; background: transparent; color: #d7e7e2; cursor: pointer; }.user-label { padding-left: 7px; border-left: 1px solid rgba(255,255,255,.2); color: #c8d8d4; font-size: 9px; }
.craft-body { display: grid; grid-template-columns: 145px minmax(0, 1fr); min-height: 346px; }.craft-nav { padding: 16px 9px; border-right: 1px solid #e0e7e5; background: #f7faf9; }.nav-caption { padding: 0 7px 8px; font-size: 9px; }.nav-link { display: flex; align-items: center; gap: 7px; width: 100%; min-height: 31px; padding: 0 7px; border: 0; border-radius: 3px; background: transparent; color: #5d6c70; cursor: pointer; font-size: 10px; text-align: left; }.nav-link.active { background: #dceee9; color: #176b5a; font-weight: 700; }.nav-link.muted { color: #899598; }.nav-line, .dense-rule { display: block; height: 1px; margin: 15px 7px; background: #e0e7e5; }
.craft-main { min-width: 0; }.craft-heading, .dense-heading { display: flex; align-items: flex-end; justify-content: space-between; gap: 10px; min-height: 65px; padding: 0 16px 13px; border-bottom: 1px solid #e6ecea; }.craft-heading h3, .dense-heading h3 { margin: 5px 0 0; color: #203232; font-size: 18px; letter-spacing: -.02em; }.primary-button, .dense-primary { display: inline-flex; align-items: center; gap: 4px; min-height: 29px; padding: 0 9px; border: 0; border-radius: 3px; background: #176b5a; color: #fff; cursor: pointer; font-size: 10px; }.craft-toolbar { display: flex; align-items: center; gap: 8px; min-height: 50px; padding: 8px 16px; border-bottom: 1px solid #e6ecea; }.search-box { display: flex; min-width: 0; flex: 1; align-items: center; gap: 6px; height: 29px; padding: 0 8px; border: 1px solid #ccd9d5; border-radius: 3px; color: #8a9998; }.search-box input { min-width: 0; width: 100%; border: 0; outline: 0; background: transparent; color: #455558; font-size: 10px; }.search-box input::placeholder { color: #9aa8a6; }.search-box kbd, .dense-topbar kbd, .dense-shortcuts kbd { padding: 2px 4px; border: 1px solid #bccbc7; border-radius: 3px; color: #879995; font: 9px ui-monospace, monospace; white-space: nowrap; }.toolbar-link { display: inline-flex; align-items: center; gap: 3px; border: 0; background: transparent; color: #647477; cursor: pointer; font-size: 10px; }.count-label { margin-left: auto; color: #899795; font-size: 9px; white-space: nowrap; }.table-wrap { overflow-x: auto; }.craft-table { width: 100%; min-width: 535px; border-collapse: collapse; table-layout: fixed; font-size: 10px; }.craft-table th, .craft-table td { height: 40px; padding: 0 8px; border-bottom: 1px solid #edf1f0; text-align: left; }.craft-table th { height: 31px; color: #7a8888; background: #f6f9f8; font-size: 9px; font-weight: 700; }.craft-table th:first-child, .craft-table td:first-child { padding-left: 16px; }.craft-table td strong { display: block; color: #314244; font-size: 10px; }.craft-table td small { display: block; margin-top: 3px; color: #96a29f; font-size: 9px; }.mono { font-variant-numeric: tabular-nums; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }.status { display: inline-flex; padding: 3px 5px; border-radius: 3px; font-size: 9px; }.status.success { background: #e1f2eb; color: #2c7b62; }.status.warning { background: #fff0d5; color: #a16c20; }.table-foot { display: flex; justify-content: space-between; padding: 11px 16px; color: #8a9996; font-size: 9px; }
.option-foot { margin: 0; padding: 0 21px 20px; color: #758286; font-size: 11px; line-height: 1.5; }.option-foot strong { color: #40575a; }
.production-preview { width: min(1480px, 100%); margin: 28px auto 0; padding: 24px; border: 1px solid #cbd7d4; border-radius: 8px; background: #f8fbfa; box-shadow: 0 12px 28px rgba(26, 44, 47, .06); }
.production-preview-head { display: flex; align-items: flex-end; justify-content: space-between; gap: 20px; padding-bottom: 17px; border-bottom: 1px solid #dbe5e2; }.production-preview-head h2 { margin: 6px 0 4px; color: #1e3030; font-size: 24px; letter-spacing: -.03em; }.production-preview-head p:not(.eyebrow) { margin: 0; color: #718084; font-size: 12px; }.production-summary { display: flex; align-items: center; gap: 15px; color: #748487; font-size: 11px; white-space: nowrap; }.production-summary b { margin-right: 3px; color: #235d51; font: 700 17px ui-monospace, monospace; font-variant-numeric: tabular-nums; }
.production-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 14px; padding: 14px 0; }.production-search { display: flex; flex: 0 1 330px; align-items: center; gap: 7px; height: 32px; padding: 0 9px; border: 1px solid #cbd8d4; border-radius: 4px; background: #fff; color: #80918e; }.production-search input { width: 100%; min-width: 0; border: 0; outline: 0; color: #425454; font-size: 11px; }.production-search input::placeholder { color: #a0aeaa; }.tonnage-filter { display: flex; align-items: center; gap: 5px; color: #7a898a; font-size: 10px; }.tonnage-filter button { min-height: 27px; padding: 0 9px; border: 1px solid #cfdbd8; border-radius: 3px; background: #fff; color: #657779; cursor: pointer; font-size: 10px; }.tonnage-filter button:hover, .tonnage-filter button.active { border-color: #176b5a; background: #e0f1ec; color: #176b5a; font-weight: 700; }
.production-board { display: grid; grid-template-columns: minmax(245px, .72fr) minmax(0, 1.8fr); gap: 14px; align-items: start; }.order-pool, .machine-queues { min-width: 0; }.order-pool { padding: 13px; border: 1px solid #d4dfdc; border-radius: 5px; background: #fff; }.board-section-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; padding-bottom: 10px; border-bottom: 1px solid #e6ecea; }.board-section-head h3, .tonnage-group-head h3 { margin: 0; color: #29403e; font-size: 14px; }.board-section-head span, .tonnage-group-head span { display: block; margin-top: 3px; color: #8a9898; font-size: 10px; }.board-section-head > strong { color: #176b5a; font: 700 18px ui-monospace, monospace; font-variant-numeric: tabular-nums; }.order-list { display: grid; gap: 8px; padding-top: 10px; }.order-card { padding: 11px 11px 9px; border: 1px solid #d7e2df; border-left: 3px solid #a6c2ba; border-radius: 4px; background: #fbfdfc; cursor: grab; transition: border-color 120ms ease, box-shadow 120ms ease, transform 120ms ease; }.order-card:hover, .order-card:focus-visible, .order-card.selected { border-color: #75a99b; box-shadow: 0 4px 12px rgba(23, 107, 90, .1); transform: translateY(-1px); outline: 0; }.order-card.selected { background: #eff9f5; }.order-card.dragging { opacity: .52; }.order-card.urgent { border-left-color: #bd7d2e; }.order-card-top { display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; }.order-card-top strong { color: #29403e; font: 700 12px ui-monospace, monospace; letter-spacing: -.015em; }.urgent-mark { color: #a66b21; font-size: 10px; font-weight: 700; }.order-card dl { display: grid; grid-template-columns: 1.35fr .8fr; gap: 8px; margin: 10px 0 8px; }.order-card dl div { min-width: 0; }.order-card dt { color: #8b9999; font-size: 9px; }.order-card dd { overflow: hidden; margin: 3px 0 0; color: #526467; font: 10px ui-monospace, monospace; text-overflow: ellipsis; white-space: nowrap; }.order-card-foot { display: flex; align-items: center; justify-content: space-between; gap: 7px; padding-top: 8px; border-top: 1px solid #e8eeec; color: #718181; font-size: 10px; }.order-card-foot b { color: #315c53; font: 700 11px ui-monospace, monospace; }.special-notice { color: #a66b21; font-size: 9px; }.pool-empty, .queue-empty { padding: 22px 10px; color: #94a19f; font-size: 10px; text-align: center; }
.machine-queues { display: grid; gap: 12px; }.tonnage-group { padding: 13px; border: 1px solid #d4dfdc; border-radius: 5px; background: #fff; }.tonnage-group-head { display: flex; align-items: baseline; justify-content: space-between; gap: 10px; padding-bottom: 9px; border-bottom: 1px solid #e4ebe8; }.tonnage-group-head h3 { color: #176b5a; font: 700 15px ui-monospace, monospace; }.machine-list { display: grid; gap: 7px; padding-top: 9px; }.machine-row { display: grid; grid-template-columns: 150px minmax(0, 1fr); min-width: 0; border: 1px solid #e0e8e6; border-radius: 4px; background: #fbfcfc; }.machine-row.drop-target { border-color: #4f9b86; background: #f0faf6; box-shadow: 0 0 0 2px rgba(79, 155, 134, .13); }.machine-row.drop-blocked { opacity: .62; }.machine-fixed { display: flex; align-items: center; justify-content: space-between; gap: 8px; min-width: 0; padding: 9px 10px; border-right: 1px solid #e1e9e7; }.machine-fixed > div { min-width: 0; }.machine-fixed strong { display: block; color: #344a4a; font-size: 12px; }.machine-fixed span:not(.machine-state) { display: block; margin-top: 3px; color: #8b9999; font-size: 9px; }.machine-state { flex: 0 0 auto; padding: 3px 5px; border-radius: 3px; font-size: 9px; }.machine-state.running { background: #e0f1eb; color: #27765f; }.machine-state.idle { background: #edf2f2; color: #687b7d; }.machine-state.fault { background: #f9e9e1; color: #a95e42; }.queue-lane { display: flex; min-width: 0; align-items: center; gap: 7px; min-height: 52px; padding: 7px 9px; overflow-x: auto; }.queue-item { display: grid; grid-template-columns: auto minmax(125px, auto) auto 22px; align-items: center; gap: 7px; min-width: 310px; min-height: 36px; padding: 0 7px; border: 1px solid #d7e2df; border-radius: 3px; background: #fff; }.queue-item.current { border-color: #95c2b5; background: #eef8f4; }.queue-index { color: #6d8780; font-size: 9px; white-space: nowrap; }.queue-item strong { overflow: hidden; color: #36504d; font: 700 10px ui-monospace, monospace; text-overflow: ellipsis; white-space: nowrap; }.queue-tooling { color: #82918f; font: 9px ui-monospace, monospace; white-space: nowrap; }.queue-item button { display: grid; place-items: center; width: 22px; height: 22px; border: 0; border-radius: 3px; background: transparent; color: #9baaa6; cursor: pointer; }.queue-item button:hover { background: #f3e8e5; color: #a95e42; }.production-note { margin: 13px 0 0; color: #859390; font-size: 10px; line-height: 1.5; }
.option-dense { border-color: #c6d2d6; background: #f5f7f8; }.dense-shell { margin-top: 18px; border-color: #b9c7cc; border-radius: 4px; background: #f7f9fa; font-family: 'IBM Plex Sans', 'Segoe UI', sans-serif; }.dense-topbar { background: #203038; }.dense-brand { display: flex; align-items: center; gap: 8px; }.dense-brand strong { color: #eef5f5; font-size: 11px; letter-spacing: .01em; }.dense-brand kbd { margin-left: 5px; border-color: #53666c; color: #aabcc0; }.dense-live { display: inline-flex; align-items: center; gap: 5px; margin-left: auto; color: #9bc5b8; font: 9px 'IBM Plex Mono', ui-monospace, monospace; }.dense-icon { color: #b4c5c7; }.dense-body { display: grid; grid-template-columns: 135px minmax(0, 1fr) 150px; min-height: 346px; }.dense-rail { padding: 16px 9px; border-right: 1px solid #d9e1e3; background: #edf2f3; }.dense-caption { color: #728388; font-size: 9px; letter-spacing: .08em; }.dense-nav { display: grid; grid-template-columns: 7px minmax(0, 1fr) auto; align-items: center; gap: 6px; width: 100%; min-height: 33px; padding: 0 6px; border: 0; border-radius: 2px; background: transparent; color: #5d6d73; cursor: pointer; font-size: 9px; text-align: left; }.dense-nav.active { background: #d9e8e7; color: #20584c; font-weight: 700; }.dense-nav b { color: #a66c2a; font: 700 9px 'IBM Plex Mono', monospace; }.dot { width: 5px; height: 5px; border-radius: 50%; background: #79a2ad; }.dot.danger { background: #c35f59; }.dot.warning { background: #d29a4b; }.dot.info { background: #6795a3; }.dense-rail .dense-rule { margin: 15px 6px; background: #d6e0e1; }.rail-metric, .impact-number { display: flex; align-items: center; gap: 7px; margin-top: 8px; }.rail-metric strong, .impact-number strong { color: #20584c; font: 700 25px 'IBM Plex Mono', monospace; }.rail-metric span, .impact-number span { color: #6e7e82; font-size: 9px; line-height: 1.35; }.rail-progress, .health-track { height: 5px; overflow: hidden; margin: 13px 1px 6px; border-radius: 2px; background: #d7e1e2; }.rail-progress i, .health-track i { display: block; height: 100%; border-radius: inherit; background: #4d9c83; }.dense-rail > small { color: #8b999c; font-size: 8px; }.dense-main { min-width: 0; background: #fbfcfc; }.dense-heading h3 { color: #263a40; font-size: 18px; }.dense-primary { background: #2b7768; }.dense-breadcrumb { color: #789097; font-size: 9px; }.dense-tabs { display: flex; align-items: center; gap: 13px; height: 40px; padding: 0 14px; border-bottom: 1px solid #e2e8e9; }.dense-tabs button { height: 40px; border: 0; border-bottom: 2px solid transparent; background: transparent; color: #7a8b90; cursor: pointer; font-size: 9px; }.dense-tabs button.active { border-color: #2b7768; color: #2b7768; font-weight: 700; }.dense-tabs b { margin-left: 2px; }.dense-tabs span { display: inline-flex; align-items: center; gap: 3px; margin-left: auto; color: #8b999d; font-size: 8px; white-space: nowrap; }.dense-alert { display: grid; grid-template-columns: 6px minmax(0, 1fr) 45px 17px; align-items: center; gap: 7px; min-height: 80px; padding: 0 14px; border-bottom: 1px solid #e8edef; }.alert-dot { width: 6px; height: 6px; border-radius: 50%; }.alert-dot.high { background: #c35f59; }.alert-dot.medium { background: #d29a4b; }.alert-dot.low { background: #4d9c83; }.dense-alert strong { display: block; overflow: hidden; color: #31464c; font-size: 10px; text-overflow: ellipsis; white-space: nowrap; }.dense-alert p { margin: 4px 0; overflow: hidden; color: #728287; font-size: 9px; line-height: 1.35; text-overflow: ellipsis; white-space: nowrap; }.dense-alert small, .dense-alert time { color: #91a0a4; font: 8px 'IBM Plex Mono', ui-monospace, monospace; }.dense-alert button { display: grid; place-items: center; border: 0; background: transparent; color: #4c8e7d; cursor: pointer; }.dense-inspector { padding: 17px 12px; border-left: 1px solid #d9e1e3; background: #f3f6f7; }.health-number { display: flex; align-items: baseline; gap: 2px; margin-top: 5px; }.health-number strong, .impact-number strong { color: #2c806e; font: 700 29px 'IBM Plex Mono', monospace; }.health-number span { color: #8a999c; font: 9px 'IBM Plex Mono', monospace; }.inspector-copy { margin: 3px 0 0; color: #829094; font-size: 8px; line-height: 1.4; }.health-track { margin-top: 12px; }.health-legend { display: flex; flex-direction: column; gap: 6px; margin-top: 11px; color: #708085; font-size: 8px; }.health-legend span { display: flex; align-items: center; gap: 5px; }.health-legend i { width: 5px; height: 5px; border-radius: 50%; }.health-legend .ok { background: #4d9c83; }.health-legend .warn { background: #d29a4b; }.health-legend .bad { background: #c35f59; }.health-legend b { margin-left: auto; color: #52666b; font: 8px 'IBM Plex Mono', monospace; }.dense-inspector .dense-rule { margin: 16px 0; background: #d8e1e2; }.impact-number strong { color: #b2772f; }.inspector-link { display: inline-flex; align-items: center; gap: 3px; margin-top: 16px; border: 0; background: transparent; color: #2c7d6e; cursor: pointer; font-size: 8px; }.dense-shortcuts { display: flex; align-items: center; gap: 12px; min-height: 30px; padding: 0 12px; border-top: 1px solid #d8e1e2; background: #edf2f3; color: #7c8b8f; font: 8px 'IBM Plex Mono', monospace; }.dense-shortcuts kbd { padding: 1px 4px; border-color: #bdcbd0; color: #65777d; }.shortcut-spacer { flex: 1; }
.decision-bar { display: flex; align-items: center; gap: 10px; margin-top: 18px; padding: 13px 16px; border: 1px solid #cfdad8; border-radius: 5px; background: #f8fbfa; color: #738184; font-size: 11px; }.decision-bar strong { color: #176b5a; font-size: 12px; }.decision-bar small { margin-left: auto; color: #849194; font-size: 10px; }
@media (max-width: 1100px) { .comparison { grid-template-columns: 1fr; }.production-board { grid-template-columns: 1fr; } }
@media (max-width: 700px) { .preview-page { padding: 20px 11px 36px; }.page-head { align-items: flex-start; flex-direction: column; gap: 16px; }.review-note { width: 100%; }.option-head { flex-direction: column; gap: 14px; }.select-button { width: 100%; justify-content: center; }.craft-shell, .dense-shell { margin: 13px; }.craft-body, .dense-body { grid-template-columns: 1fr; }.craft-nav, .dense-rail, .dense-inspector { display: none; }.craft-heading, .dense-heading { padding: 0 12px 12px; }.craft-toolbar { flex-wrap: wrap; padding: 8px 12px; }.search-box { flex-basis: 100%; }.count-label { margin-left: 0; }.craft-table { min-width: 535px; }.craft-main, .dense-main { overflow-x: auto; }.dense-heading { min-width: 445px; }.dense-tabs, .dense-alert { min-width: 445px; }.dense-shortcuts { overflow-x: auto; white-space: nowrap; }.production-preview { padding: 16px 12px; }.production-preview-head, .production-toolbar { align-items: stretch; flex-direction: column; }.production-summary { justify-content: space-between; }.tonnage-filter { flex-wrap: wrap; }.production-search { flex-basis: auto; width: 100%; }.machine-row { grid-template-columns: 1fr; }.machine-fixed { border-right: 0; border-bottom: 1px solid #e1e9e7; }.decision-bar { align-items: flex-start; flex-wrap: wrap; }.decision-bar small { width: 100%; margin-left: 0; line-height: 1.45; } }
@media (prefers-reduced-motion: reduce) { *, *::before, *::after { scroll-behavior: auto !important; transition-duration: .01ms !important; animation-duration: .01ms !important; } }
</style>
