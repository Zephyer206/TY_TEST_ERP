<template>
  <div class="dashboard-workbench">
    <header class="workbench-header">
      <div><p class="eyebrow">ZEPHYR ERP / 工作台</p><h1>制造工作台</h1><p class="subtitle">{{ currentDateTime }} · 今日优先处理需要工程判断的事项</p></div>
      <div class="header-actions"><span class="sync-state"><i /> 数据已同步</span><el-button type="primary" @click="router.push('/parts')"><el-icon><Grid /></el-icon>打开零件档案</el-button></div>
    </header>

    <section class="metric-strip" aria-label="工作台摘要">
      <button type="button" class="metric" @click="router.push('/quotes')"><span>待审批报价</span><strong>{{ stats.pendingQuotes }}</strong><small>客户与报价</small><el-icon><ArrowRight /></el-icon></button>
      <button type="button" class="metric" @click="router.push('/production')"><span>进行中计划</span><strong>{{ stats.activePlans }}</strong><small>工艺与生产</small><el-icon><ArrowRight /></el-icon></button>
      <button type="button" class="metric" @click="router.push('/warehouse')"><span>库存预警</span><strong class="warning">{{ stats.lowStockItems }}</strong><small>库存</small><el-icon><ArrowRight /></el-icon></button>
    </section>

    <section class="workbench-grid">
      <article class="queue-panel">
        <div class="panel-head"><div><p class="section-kicker">需要判断</p><h2>优先队列</h2></div><button type="button" class="text-link" @click="router.push('/parts')">查看全部 <el-icon><ArrowRight /></el-icon></button></div>
        <div class="queue-list">
          <button v-for="item in priorityQueue" :key="item.key" type="button" class="queue-row" @click="router.push(item.route)"><i class="severity" :class="item.level" /><span><strong>{{ item.title }}</strong><small>{{ item.detail }}</small></span><time>{{ item.time }}</time><el-icon><ArrowRight /></el-icon></button>
        </div>
      </article>

      <article class="status-panel">
        <div class="panel-head"><div><p class="section-kicker">工艺与生产</p><h2>今日生产概览</h2></div><button type="button" class="text-link" @click="router.push('/production')">打开控制台 <el-icon><ArrowRight /></el-icon></button></div>
        <div class="production-health"><div><strong>86</strong><span>%</span><small>今日完成率</small></div><div class="health-track"><i style="width: 86%" /></div></div>
        <div class="machine-list"><div v-for="machine in machineStatuses" :key="machine.key" class="machine-row"><i :style="{ background: machine.color }" /><span>{{ machine.label }}</span><strong>{{ machine.count }}</strong><small>台</small></div></div>
      </article>
    </section>

    <section class="domain-links" aria-label="业务入口">
      <button v-for="link in quickLinks" :key="link.route" type="button" class="domain-link" @click="router.push(link.route)"><span class="link-icon"><el-icon><component :is="link.icon" /></el-icon></span><span><strong>{{ link.label }}</strong><small>{{ link.detail }}</small></span><el-icon class="link-arrow"><ArrowRight /></el-icon></button>
    </section>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowRight, Box, Connection, Document, DocumentChecked, Grid, Setting } from '@element-plus/icons-vue'
import { quotesApi } from '@/api/quotes'
import { productionApi } from '@/api/production'
import { packagingApi } from '@/api/packaging'

const router = useRouter()
const userInfo = ref(JSON.parse(localStorage.getItem('userInfo') || '{}'))
const currentDateTime = ref('')
let timeInterval = null
const stats = reactive({ pendingQuotes: 0, activePlans: 0, lowStockItems: 0 })
const priorityQueue = [
  { key: 'twp', level: 'high', title: '主规格存在多个候选项', detail: '左侧支架 · 需要确认 TWP 主规格', time: '12 分钟前', route: '/parts' },
  { key: 'pair', level: 'medium', title: '左右件尚未设置关联', detail: '支架 · 请在模具关联中确认', time: '1 小时前', route: '/parts' },
  { key: 'quote', level: 'low', title: '报价等待主管审批', detail: '客户与报价 · 需要业务确认', time: '今天 08:42', route: '/quotes' },
]
const machineStatuses = [
  { key: 'running', label: '运行中', count: 5, color: '#4b9b7e' },
  { key: 'idle', label: '空闲', count: 2, color: '#6795a3' },
  { key: 'fault', label: '故障', count: 1, color: '#be514d' },
  { key: 'repairing', label: '维修中', count: 1, color: '#c88b34' },
]
const quickLinks = [
  { label: '零件档案', detail: '产品 / 列表优先', route: '/parts', icon: Box },
  { label: '材料主数据', detail: '产品 / 规格与价格', route: '/materials', icon: Document },
  { label: '模具生命周期', detail: '工艺与生产 / 关联', route: '/tooling', icon: Connection },
  { label: '客户与报价', detail: '审批与定价', route: '/quotes', icon: DocumentChecked },
  { label: '生产计划', detail: '控制台 / 排产影响', route: '/production', icon: Setting },
]
const updateDateTime = () => { currentDateTime.value = new Date().toLocaleString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric', weekday: 'long', hour: '2-digit', minute: '2-digit' }) }
const fetchStats = async () => {
  const results = await Promise.allSettled([quotesApi.list({ status: 'PENDING_BOSS', page_size: 1 }), productionApi.plansCount({ status: 'in_progress' }), packagingApi.inventory()])
  if (results[0].status === 'fulfilled') stats.pendingQuotes = results[0].value.total || 0
  if (results[1].status === 'fulfilled') stats.activePlans = results[1].value.total || 0
  if (results[2].status === 'fulfilled' && Array.isArray(results[2].value)) {
    stats.lowStockItems = results[2].value.filter((item) => Number(item.stock_qty ?? 0) <= Number(item.reserved_qty ?? 0)).length
  }
}
onMounted(() => { updateDateTime(); timeInterval = setInterval(updateDateTime, 60000); fetchStats() })
onUnmounted(() => { if (timeInterval) clearInterval(timeInterval) })
</script>

<style scoped>
.dashboard-workbench { min-width: 0; color: var(--zephyr-ink); }.workbench-header { display: flex; align-items: flex-end; justify-content: space-between; gap: 18px; margin: 14px 0 12px; }.eyebrow, .section-kicker { margin: 0 0 4px; color: var(--zephyr-primary); font-size: 10px; font-weight: 700; letter-spacing: .1em; text-transform: uppercase; }.workbench-header h1 { margin: 0; color: var(--zephyr-ink); font-size: 22px; letter-spacing: -.025em; }.subtitle { margin: 5px 0 0; color: var(--zephyr-muted); font-size: 12px; }.header-actions { display: flex; align-items: center; gap: 10px; }.sync-state { display: inline-flex; align-items: center; gap: 5px; color: var(--zephyr-muted); font-size: 10px; }.sync-state i { width: 6px; height: 6px; border-radius: 50%; background: var(--zephyr-primary); }
  .metric-strip { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); margin-bottom: 10px; border: 1px solid var(--zephyr-border); background: #fff; }.metric { position: relative; display: flex; min-width: 0; min-height: 78px; flex-direction: column; align-items: flex-start; gap: 3px; padding: 12px 14px; border: 0; border-right: 1px solid #eff2ff; background: transparent; color: var(--zephyr-muted); cursor: pointer; text-align: left; }.metric:last-child { border-right: 0; }.metric:hover { background: var(--zephyr-primary-soft); }.metric span, .metric small { font-size: 10px; }.metric strong { color: var(--zephyr-ink); font: 700 24px ui-monospace, monospace; }.metric strong.warning { color: #b7791f; }.metric .el-icon { position: absolute; right: 12px; bottom: 13px; color: var(--zephyr-primary); }.workbench-grid { display: grid; grid-template-columns: minmax(0, 1.25fr) minmax(300px, .75fr); gap: 10px; margin-bottom: 10px; }.queue-panel, .status-panel { min-width: 0; border: 1px solid var(--zephyr-border); background: #fff; }.panel-head { display: flex; align-items: flex-end; justify-content: space-between; gap: 10px; padding: 13px 15px; border-bottom: 1px solid #f3f4f6; }.panel-head h2 { margin: 0; color: var(--zephyr-ink); font-size: 14px; }.text-link { display: inline-flex; align-items: center; gap: 4px; border: 0; background: transparent; color: var(--zephyr-primary); cursor: pointer; font-size: 10px; }.queue-row { display: grid; grid-template-columns: 7px minmax(0, 1fr) 65px 18px; align-items: center; gap: 9px; width: 100%; min-height: 66px; padding: 0 15px; border: 0; border-bottom: 1px solid #f3f4f6; background: #fff; color: #4b5563; cursor: pointer; text-align: left; }.queue-row:hover { background: var(--zephyr-surface-muted); }.severity { width: 6px; height: 6px; border-radius: 50%; }.severity.high { background: #be514d; }.severity.medium { background: #c88b34; }.severity.low { background: var(--zephyr-primary); }.queue-row strong { display: block; overflow: hidden; color: var(--zephyr-ink); font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }.queue-row small, .queue-row time { display: block; margin-top: 4px; color: #9ca3af; font-size: 9px; }.queue-row time { margin-top: 0; text-align: right; }.queue-row > .el-icon { color: var(--zephyr-primary); }.production-health { display: flex; align-items: center; gap: 12px; padding: 17px 15px 12px; }.production-health strong { color: var(--zephyr-primary-hover); font: 700 28px ui-monospace, monospace; }.production-health span { color: var(--zephyr-muted); font: 9px ui-monospace, monospace; }.production-health small { display: block; margin-top: 2px; color: #9ca3af; font-size: 9px; }.health-track { flex: 1; height: 6px; overflow: hidden; border-radius: 3px; background: var(--zephyr-border); }.health-track i { display: block; height: 100%; border-radius: inherit; background: var(--zephyr-primary); }.machine-list { display: grid; grid-template-columns: repeat(2, 1fr); padding: 0 15px 13px; }.machine-row { display: grid; grid-template-columns: 7px 1fr auto auto; align-items: center; gap: 6px; min-height: 35px; border-top: 1px solid #f3f4f6; color: var(--zephyr-muted); font-size: 10px; }.machine-row i { width: 6px; height: 6px; border-radius: 50%; }.machine-row strong { color: var(--zephyr-ink); font: 700 14px ui-monospace, monospace; }.machine-row small { color: #9ca3af; font-size: 9px; }.domain-links { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }.domain-link { display: grid; grid-template-columns: 28px minmax(0, 1fr) 16px; align-items: center; gap: 9px; min-width: 0; min-height: 56px; padding: 8px 11px; border: 1px solid var(--zephyr-border); background: #fff; color: #4b5563; cursor: pointer; text-align: left; }.domain-link:hover { border-color: var(--zephyr-primary-border); background: var(--zephyr-primary-soft); }.link-icon { display: grid; width: 28px; height: 28px; place-items: center; border-radius: 4px; background: var(--zephyr-primary-soft); color: var(--zephyr-primary); }.domain-link strong, .domain-link small { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }.domain-link strong { color: var(--zephyr-ink); font-size: 11px; }.domain-link small { margin-top: 3px; color: #9ca3af; font-size: 9px; }.link-arrow { color: var(--zephyr-primary); }
@media (max-width: 900px) { .workbench-header { align-items: flex-start; flex-direction: column; }.header-actions { width: 100%; justify-content: space-between; }.workbench-grid { grid-template-columns: 1fr; }.domain-links { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 560px) { .metric-strip { grid-template-columns: repeat(2, minmax(0, 1fr)); }.metric:nth-child(2) { border-right: 0; }.metric:nth-child(n+3) { border-top: 1px solid #e5ecea; }.domain-links { grid-template-columns: 1fr; }.machine-list { grid-template-columns: 1fr; } }
</style>
