<template>
  <div class="boss-workbench">
    <header class="boss-heading">
      <div><span class="boss-eyebrow">全公司 · 经营总览</span><p>掌握生产进度，让交付与开发有序推进。</p></div>
      <div class="boss-heading-actions"><span class="boss-demo-badge">布局预览 · 示例数据</span><button class="boss-button" type="button" @click="openRules"><el-icon><InfoFilled /></el-icon>统计口径</button></div>
    </header>
    <p class="boss-demo-notice" role="note"><el-icon><InfoFilled /></el-icon>当前为布局评审，数据截至示例日期2026年10月17日，尚未接入实时业务统计。原有待办可在“岗位待办”查看。</p>

    <section aria-labelledby="boss-production-title">
      <div class="boss-section-heading"><div class="boss-title-note"><h2 id="boss-production-title">生产与发货</h2><span>{{ periodLabel }}</span></div><nav class="boss-periods" aria-label="产出统计时间"><button v-for="tab in periodTabs" :key="tab.key" type="button" :class="{ active: period === tab.key }" :aria-pressed="period === tab.key" @click="selectPeriod(tab.key)">{{ tab.label }}</button></nav></div>
      <form v-if="showCustom" class="boss-date-range" @submit.prevent="applyRange"><label>开始日期<input v-model="customStart" type="date" :min="DEMO_MIN" :max="TODAY" required /></label><label>结束日期<input v-model="customEnd" type="date" :min="DEMO_MIN" :max="TODAY" required /></label><button class="boss-button primary" type="submit">查看</button><span>示例范围：9月1日—10月17日</span><span role="alert">{{ rangeError }}</span></form>
      <div class="boss-kpis">
        <button v-for="card in productionCards" :key="card.key" type="button" class="boss-kpi" :data-boss-stage="card.key" :aria-label="`查看${card.name}明细`" @click="openStage(card.key)">
          <span class="boss-kpi-top">{{ card.name }}<span class="boss-kpi-icon" :class="card.key"><el-icon><component :is="stageIcons[card.key]" /></el-icon></span></span>
          <span class="boss-kpi-number">{{ fmt(card.total) }}<small>件</small></span>
          <span class="boss-kpi-trend"><span v-if="card.change !== null"><b :class="{ down: card.change < 0 }">{{ card.change >= 0 ? '↗' : '↘' }} {{ Math.abs(card.change).toFixed(1) }}%</b>{{ card.comparison }}</span><span v-else>所选日期累计</span><svg viewBox="0 0 88 24" aria-label="近7日产出趋势"><title>近7日产出趋势（示例）</title><polyline :points="sparkPoints(card.key)" /></svg></span>
          <span class="boss-kpi-quality" v-if="card.key !== 'ship'"><span>不良 <b>{{ fmt(card.bad) }}</b> 件</span><span>返工 <b>{{ fmt(card.rework) }}</b> 件</span></span><span v-else class="boss-kpi-quality">按实际发出数量统计</span>
        </button>
      </div>
    </section>

    <div class="boss-middle-grid">
      <section class="boss-panel" aria-labelledby="boss-backlog-title"><div class="boss-panel-heading"><div><h2 id="boss-backlog-title">当前待处理</h2><small>各环节现有待处理数量</small></div><span class="boss-live">当前状态</span></div><div class="boss-backlog-list"><button v-for="item in backlog" :key="item.key" type="button" class="boss-backlog-row" :data-boss-backlog="item.key" @click="openBacklog(item)"><span class="boss-backlog-icon" :class="item.key"><el-icon><component :is="stageIcons[item.key]" /></el-icon></span><span class="boss-backlog-copy"><strong>{{ item.name }}</strong><small>{{ item.count }}笔待处理 · 最长等待{{ item.oldest }}天</small></span><span class="boss-backlog-number">{{ fmt(item.quantity) }}<small>件</small></span><el-icon class="boss-row-arrow"><ArrowRight /></el-icon></button></div><div class="boss-panel-note"><el-icon><InfoFilled /></el-icon>按实际工艺路线统计剩余数量</div></section>

      <section class="boss-panel" aria-labelledby="boss-development-title"><div class="boss-panel-heading"><div class="boss-title-note"><h2 id="boss-development-title">产品开发</h2><span class="boss-live">当前状态</span></div><button type="button" class="boss-text-button" @click="openDevelopment('all')">查看全部<el-icon><ArrowRight /></el-icon></button></div><div class="boss-development-stats"><button v-for="stat in developmentStats" :key="stat.key" type="button" :data-boss-dev="stat.key" @click="openDevelopment(stat.key)"><span>{{ stat.label }}</span><strong>{{ stat.number }}</strong><small>款</small></button></div><div class="boss-table-wrap"><table class="boss-table boss-dev-table"><thead><tr><th>重点开发产品</th><th>类型</th><th>当前进度</th><th>负责人</th></tr></thead><tbody><tr v-for="product in development.slice(0,3)" :key="product.id"><td><button type="button" class="boss-table-link" @click="openDevelopmentItem(product)">{{ product.name }}</button></td><td>{{ product.type }}</td><td><span class="boss-status" :class="product.tone">{{ product.observe ? `观察中 · 剩${observationDays(product)}天` : product.stage }}</span></td><td>{{ product.owner }}</td></tr></tbody></table></div><footer class="boss-development-footer"><span>开发总款数按产品去重</span><button type="button" class="boss-text-button" data-boss-observation @click="openDevelopment('observe')">交付观察中 <strong>3</strong> 款<el-icon><ArrowRight /></el-icon></button></footer></section>
    </div>

    <div class="boss-bottom-grid">
      <section class="boss-panel" aria-labelledby="boss-delivery-title"><div class="boss-panel-heading"><div class="boss-title-note"><h2 id="boss-delivery-title">订单交付</h2><span>本周交付情况</span></div><button type="button" class="boss-text-button" @click="openDelivery('all')">查看全部<el-icon><ArrowRight /></el-icon></button></div><div class="boss-delivery-stats"><button v-for="stat in deliveryStats" :key="stat.key" type="button" :data-boss-delivery="stat.key" @click="openDelivery(stat.key)"><span>{{ stat.label }}</span><strong>{{ stat.number }}</strong><small>单</small><em>{{ fmt(stat.amount) }}件</em></button></div><div class="boss-table-wrap"><table class="boss-table boss-delivery-table"><thead><tr><th>待交付订单</th><th>客户 / 产品</th><th>剩余数量</th><th>交付状态</th></tr></thead><tbody><tr v-for="order in outstandingOrders.slice(0,3)" :key="order.id"><td><button type="button" class="boss-table-link order-number" @click="openOrder(order)">{{ order.id }}</button></td><td>{{ order.client }}<small>{{ order.product }}</small></td><td>{{ fmt(order.quantity) }}件</td><td><span class="boss-status" :class="order.tone">{{ order.state }}</span></td></tr></tbody></table></div></section>

      <section class="boss-panel" aria-labelledby="boss-attention-title"><div class="boss-panel-heading"><div class="boss-title-note"><h2 id="boss-attention-title">重点关注</h2><span class="boss-count">{{ issues.length }}</span></div><small>需要跟进与协调</small></div><div class="boss-issue-list"><button v-for="(issue,index) in issues" :key="issue.title" type="button" class="boss-issue" :data-boss-issue="index" @click="openIssue(issue)"><span class="boss-issue-symbol"><el-icon><WarningFilled /></el-icon></span><span class="boss-issue-copy"><span class="boss-issue-title">{{ issue.title }}<em>{{ issue.tag }}</em></span><small>{{ issue.description }}</small></span><el-icon class="boss-row-arrow"><ArrowRight /></el-icon></button></div></section>
    </div>
    <footer class="boss-page-footer"><span>布局预览 · 示例数据，不代表当前项目的实际经营情况</span><span>产出按所选日期统计 · 待处理和开发显示当前状态</span></footer>

    <dialog ref="detailDialog" class="boss-dialog" aria-labelledby="boss-dialog-title" @click="onDialogClick">
      <template v-if="detail"><header class="boss-dialog-header"><div><span class="boss-eyebrow">{{ detail.rules ? '业务规则' : '明细查看' }}</span><h2 id="boss-dialog-title">{{ detail.title }}</h2><p>{{ detail.subtitle }}</p></div><button class="boss-close" type="button" aria-label="关闭明细" @click="closeDetail"><el-icon><Close /></el-icon></button></header><div class="boss-dialog-body">
        <template v-if="detail.rules"><section class="boss-rule"><h3>产出与返工</h3><p>生产量指冲压完成数量。冲压、喷涂、包装均按合格完成数量统计；不良和返工单独记录，已经计入的合格产量避免重复累计。发货量按实际发出数量统计。</p></section><section class="boss-rule"><h3>开发结项</h3><p>软模已交付客户后，从最后一次相关业务操作起连续30天无后续，视为完成；没有后续时从交付日算起。</p><p>连续模和工程模以客户批准PPAP作为完成节点。有硬模开发安排的产品，软模阶段结束后继续计入开发中；总款数与完成款数按产品去重。</p></section><section class="boss-rule"><h3>时间与数量</h3><p>日期筛选仅影响顶部四项产出。待处理与开发展示当前状态，本月完成固定统计示例日期所在月份。待处理按实际工艺路线和剩余数量统计。</p></section></template>
        <template v-else-if="detail.issue"><div class="boss-issue-fields"><div v-for="field in issueFields(detail.issue)" :key="field.label" :class="{ wide: field.wide }"><small>{{ field.label }}</small><p>{{ field.value }}</p></div></div></template>
        <template v-else><div v-if="detail.summary" class="boss-detail-summary">{{ detail.summary.label }}<strong>{{ fmt(detail.summary.number) }}</strong>{{ detail.summary.unit }}</div><div class="boss-detail-scroll"><table class="boss-detail-table"><thead><tr><th v-for="header in detail.headers" :key="header">{{ header }}</th></tr></thead><tbody><tr v-for="(row,index) in detail.rows" :key="index"><td v-for="(cell,cellIndex) in row" :key="cellIndex">{{ cell }}</td></tr></tbody></table></div><p v-if="detail.note" class="boss-detail-note">{{ detail.note }}</p></template>
      </div><footer class="boss-dialog-footer"><span>本页数据均为布局演示。</span><button type="button" class="boss-button" @click="closeDetail">关闭</button></footer></template>
    </dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref } from 'vue'
import { ArrowRight, Box, Brush, Calendar, Close, InfoFilled, Van } from '@element-plus/icons-vue'
import { TODAY, DEMO_MIN, PERIODS, stageDefinitions, development, completedDevelopment, backlog, orders, issues, observationDays, totalFor, fmt, sum, splitTotal, dateLabel, addDays, sparkPoints, type BacklogItem, type DevelopmentProduct, type Issue, type OrderItem, type StageKey } from './bossPreviewData'

const stageIcons = { stamp: Calendar, paint: Brush, pack: Box, ship: Van }
const periodTabs = [{key:'today',label:'今日'},{key:'week',label:'本周'},{key:'month',label:'本月'},{key:'custom',label:'自定义'}]
const period = ref('today')
const range = ref<[string,string]>([TODAY,TODAY])
const showCustom = ref(false)
const customStart = ref('2026-10-01')
const customEnd = ref(TODAY)
const rangeError = ref('')
const periodLabel = computed(() => `${range.value[0] === range.value[1] ? dateLabel(range.value[0]) : `${dateLabel(range.value[0])}—${dateLabel(range.value[1])}`} · 合格完成 / 实际发货`)
const productionCards = computed(() => stageDefinitions.map(stage => {
  const total = totalFor(stage.key,...range.value)
  const previous: Record<string,[string,string,string]> = {today:['2026-10-16','2026-10-16','较昨日'],week:['2026-10-05','2026-10-10','较上周同期'],month:['2026-09-01','2026-09-17','较上月同期']}
  const prev = previous[period.value]
  const previousTotal = prev ? totalFor(stage.key,prev[0],prev[1]) : 0
  return { ...stage,total,bad:totalFor(`${stage.key}Bad`,...range.value),rework:totalFor(`${stage.key}Rework`,...range.value),change:previousTotal ? (total-previousTotal)/previousTotal*100 : null,comparison:prev?.[2] || '' }
}))
const developmentStats = [
  {key:'all',label:'开发中产品',number:development.length},
  ...['软模','连续模','工程模'].map(type=>({key:type,label:type==='软模'?'软模验证':`${type}开发`,number:development.filter(p=>p.type===type).length})),
  {key:'completed',label:'本月完成',number:completedDevelopment.length},
]
const outstandingOrders = orders.filter(o=>o.quantity>0)
const deliveryStats = [
  {key:'all',label:'本周应发',number:orders.length,amount:sum(orders.map(o=>o.quantity+(o.shipped || 0)))},
  {key:'pending',label:'尚未发完',number:outstandingOrders.length,amount:sum(outstandingOrders.map(o=>o.quantity))},
  {key:'late',label:'逾期未交',number:outstandingOrders.filter(o=>o.due<TODAY).length,amount:sum(outstandingOrders.filter(o=>o.due<TODAY).map(o=>o.quantity))},
]
function selectPeriod(key: string) { if(key==='custom'){showCustom.value=true;return}period.value=key;range.value=[...PERIODS[key]];showCustom.value=false;rangeError.value='' }
function applyRange() { if(!customStart.value || !customEnd.value || customStart.value>customEnd.value || customStart.value<DEMO_MIN || customEnd.value>TODAY){rangeError.value='请选择示例范围内的有效日期。';return}rangeError.value='';range.value=[customStart.value,customEnd.value];period.value='custom' }

interface Detail { title: string; subtitle: string; headers?: string[]; rows?: (string | number)[][]; summary?: {label:string;number:number;unit:string}; note?: string; issue?: Issue; rules?: boolean }
const detail = ref<Detail | null>(null)
const detailDialog = ref<HTMLDialogElement>()
async function openDetail(value: Detail) { detail.value=value;await nextTick();detailDialog.value?.showModal() }
const closeDetail = () => detailDialog.value?.close()
function onDialogClick(event: MouseEvent) { const dialog=detailDialog.value;if(dialog&&event.target===dialog){const rect=dialog.getBoundingClientRect();if(event.clientX<rect.left||event.clientX>rect.right||event.clientY<rect.top||event.clientY>rect.bottom)closeDetail()} }
onBeforeUnmount(closeDetail)
function openStage(key: StageKey) {
  const card=productionCards.value.find(item=>item.key===key)!
  const quantities=splitTotal(card.total),bad=splitTotal(card.bad),rework=splitTotal(card.rework)
  void openDetail({title:card.name,subtitle:`${dateLabel(range.value[0])}—${dateLabel(range.value[1])} · 按产品汇总`,summary:{label:'所选期间合计',number:card.total,unit:'件'},headers:['产品名称',key==='ship'?'发出数量':'合格数量',...(key==='ship'?[]:['不良数量','返工数量']),'责任部门'],rows:card.products.map((product,i)=>[product,`${fmt(quantities[i])}件`,...(key==='ship'?[]:[`${fmt(bad[i])}件`,`${fmt(rework[i])}件`]),{stamp:'冲压部',paint:'喷涂部',pack:'包装部',ship:'发货部'}[key]]),note:key==='ship'?'按实际发出数量统计。':'不良和返工分别记录，可能涉及同一批产品；已计入的合格产量避免重复累计。'})
}
function openBacklog(item: BacklogItem) { const quantities=splitTotal(item.quantity);void openDetail({title:`${item.name}明细`,subtitle:'当前待处理状态 · 不受产出日期筛选影响',summary:{label:'当前剩余',number:item.quantity,unit:'件'},headers:['产品名称','剩余数量','等待时间','责任部门'],rows:item.items.map((name,i)=>[name,`${fmt(quantities[i])}件`,`${Math.max(1,item.oldest-i)}天`,item.owner]),note:'按实际需要进入该环节的剩余数量统计，支持部分完工与部分发货。'}) }
function openDevelopment(filter: string) {
  if(filter==='completed'){void openDetail({title:'本月完成开发',subtitle:'2026年10月 · 按产品去重',summary:{label:'本月完成',number:completedDevelopment.length,unit:'款'},headers:['产品名称','类型','完成日期','结项依据','负责人'],rows:completedDevelopment.map(p=>[p.name,p.type,p.date,p.basis,p.owner])});return}
  const products=development.filter(p=>filter==='all'||(filter==='observe'?p.observe:p.type===filter))
  void openDetail({title:filter==='all'?'开发中产品':filter==='observe'?'软模交付观察中':`${filter}开发中`,subtitle:'当前开发状态 · 按产品去重',summary:{label:'当前共',number:products.length,unit:'款'},headers:['产品名称','类型','当前进度','预计完成 / 观察到期','负责人'],rows:products.map(p=>[p.name,p.type,p.observe?`${p.stage} · 剩${observationDays(p)}天`:p.stage,p.observe&&p.lastAction?addDays(p.lastAction,30):p.due||'待明确',p.owner]),note:'软模交付后从最后一次相关操作起连续30天无后续视为完成；硬模以客户批准PPAP作为完成节点。'})
}
function openDevelopmentItem(product: DevelopmentProduct) { void openDetail({title:product.name,subtitle:product.id,headers:['类型','当前进度','负责人','预计完成 / 观察到期'],rows:[[product.type,product.stage,product.owner,product.observe&&product.lastAction?addDays(product.lastAction,30):product.due||'待明确']],note:product.observe?`正常交付观察中，剩余${observationDays(product)}天。`:'硬模开发以客户批准PPAP作为完成节点。'}) }
function openDelivery(filter: string) { const records=orders.filter(o=>filter==='all'||(filter==='pending'?o.quantity>0:o.quantity>0&&o.due<TODAY));void openDetail({title:filter==='all'?'本周应交订单':filter==='pending'?'尚未发完的订单':'逾期未交订单',subtitle:'10月12日—10月18日 · 依据订单交期统计',summary:{label:'订单数量',number:records.length,unit:'单'},headers:['订单号','客户','产品','约定交期','剩余数量','状态'],rows:records.map(o=>[o.id,o.client,o.product,o.due,`${fmt(o.quantity)}件`,o.state])}) }
function openOrder(order: OrderItem) { void openDetail({title:order.id,subtitle:'订单交付详情',headers:['客户','产品','约定交期','剩余数量','交付状态','负责人'],rows:[[order.client,order.product,order.due,`${fmt(order.quantity)}件`,order.state,order.owner]]}) }
const openIssue = (issue: Issue) => openDetail({title:issue.title,subtitle:issue.description,issue})
const issueFields = (issue: Issue) => [{label:'跟进负责人',value:issue.owner},{label:'预计解决日期',value:issue.expected},{label:'影响范围',value:issue.impact,wide:true},{label:'当前原因',value:issue.reason,wide:true},{label:'下一步安排',value:issue.next,wide:true}]
const openRules = () => openDetail({title:'统计口径',subtitle:'按本次讨论确定的业务规则设计',rules:true})
</script>

<style scoped src="./bossOverview.css"></style>
