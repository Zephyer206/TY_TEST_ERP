<template>
  <div class="quality-workspace">
    <header class="page-header">
      <div>
        <p class="eyebrow">产品 / 数据质量</p>
        <h2>数据质量控制台</h2>
        <p>集中处理 T/W/P、来源证据、模具关联和人工修改差异。</p>
      </div>
      <div class="header-actions">
        <span class="last-sync"><i /> 数据快照 · 08:54</span>
        <el-button type="primary" :disabled="!selectedIssue" @click="markReviewed">标记已复核</el-button>
      </div>
    </header>

    <section class="quality-summary" aria-label="数据质量摘要">
      <div><span>待处理</span><strong>{{ issues.length }}</strong><small>条异常记录</small></div>
      <div><span>影响排产</span><strong class="warning">4</strong><small>个零件</small></div>
      <div><span>来源差异</span><strong>12</strong><small>条需要查看原值</small></div>
      <div class="summary-note"><el-icon><InfoFilled /></el-icon><span>原始 Excel 值只在与当前值不同的时候显示。</span></div>
    </section>

    <section class="quality-grid" aria-label="质量队列分类">
      <button v-for="queue in queues" :key="queue.key" type="button" class="quality-card" :class="{ active: activeQueue === queue.key }" @click="activeQueue = queue.key">
        <span class="queue-icon"><el-icon><component :is="queue.icon" /></el-icon></span>
        <span><strong>{{ queue.title }}</strong><small>{{ queue.description }}</small></span>
        <b>{{ queue.count }}</b>
      </button>
    </section>

    <section class="quality-panel" aria-label="待核查记录">
      <div class="panel-heading"><div><h3>待核查记录</h3><p>按严重程度排序；点击记录后在右侧查看建议动作。</p></div><div class="panel-tools"><el-button text><el-icon><Filter /></el-icon>筛选</el-button><el-button text><el-icon><Refresh /></el-icon>刷新</el-button></div></div>
      <div class="quality-content">
        <div class="issue-list">
          <button v-for="issue in filteredIssues" :key="issue.key" type="button" class="issue-row" :class="[{ selected: selectedIssue?.key === issue.key }, issue.severity]" @click="selectedIssue = issue">
            <span class="severity-dot" /><span class="issue-main"><strong>{{ issue.title }}</strong><small>{{ issue.part }} · {{ issue.owner }}</small></span><time>{{ issue.time }}</time><el-icon><ArrowRight /></el-icon>
          </button>
          <el-empty v-if="!filteredIssues.length" description="当前队列已清空" :image-size="70" />
        </div>
        <aside class="issue-inspector" aria-label="异常详情">
          <template v-if="selectedIssue">
            <span class="severity-label" :class="selectedIssue.severity">{{ severityLabel(selectedIssue.severity) }}</span>
            <h3>{{ selectedIssue.title }}</h3>
            <p>{{ selectedIssue.detail }}</p>
            <dl><div><dt>影响零件</dt><dd>{{ selectedIssue.part }}</dd></div><div><dt>建议动作</dt><dd>{{ selectedIssue.action }}</dd></div><div><dt>负责人</dt><dd>{{ selectedIssue.owner }}</dd></div></dl>
            <div class="inspector-actions"><el-button type="primary" @click="markReviewed">标记已复核</el-button><el-button text>打开零件档案 <el-icon><ArrowRight /></el-icon></el-button></div>
          </template>
          <el-empty v-else description="选择一条记录查看详情" :image-size="64" />
        </aside>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { ArrowRight, DocumentChecked, Filter, InfoFilled, Link, Refresh, Warning, WarningFilled } from '@element-plus/icons-vue'

type Severity = 'high' | 'medium' | 'low'
type Issue = { key: string; title: string; detail: string; part: string; owner: string; action: string; time: string; severity: Severity; queue: string }

const activeQueue = ref('twp')
const selectedIssue = ref<Issue | null>(null)
const queues = [
  { key: 'twp', title: '规格待核查', description: 'T/W/P 字段不完整或存在候选值', count: 6, icon: WarningFilled },
  { key: 'source', title: '来源待补充', description: '缺少 Excel 文件、工作表或行号', count: 9, icon: DocumentChecked },
  { key: 'tooling', title: '模具关联冲突', description: '连续模优先规则需要人工确认', count: 3, icon: Link },
  { key: 'change', title: '人工修改差异', description: '当前值与原始值不一致', count: 12, icon: Warning },
]
const issues = ref<Issue[]>([
  { key: 'twp-1', queue: 'twp', severity: 'high', title: '主规格存在多个候选项', detail: '同一连续模下有 2 条 TWP 候选规格，需要确认生产主规格。', part: '左侧支架', owner: '工程组', action: '打开零件档案，确认 TWP 主规格', time: '12 分钟前' },
  { key: 'tooling-1', queue: 'tooling', severity: 'medium', title: '左右件尚未设置显示分组', detail: '来源证据已存在，但当前尚未建立显式左右件分组。', part: '支架', owner: '技术员', action: '建立显式显示分组，不从名称推断', time: '1 小时前' },
  { key: 'source-1', queue: 'source', severity: 'low', title: '材料牌号与厚度等待备注确认', detail: '保留来源备注，等待数据管理员确认后再进入量产。', part: '回位弹簧座', owner: '数据管理员', action: '查看 Excel 来源并补充行号', time: '昨天' },
])
const filteredIssues = computed(() => issues.value.filter(issue => activeQueue.value === 'all' || issue.queue === activeQueue.value || (activeQueue.value === 'change' && issue.severity === 'low')))
const severityLabel = (severity: Severity) => ({ high: '高优先级', medium: '需确认', low: '信息' })[severity]
const markReviewed = () => {
  if (!selectedIssue.value) return
  const key = selectedIssue.value.key
  issues.value = issues.value.filter(issue => issue.key !== key)
  selectedIssue.value = null
  ElMessage.success('已标记为复核完成')
}
</script>

<style scoped>
.quality-workspace { min-width: 0; }
.page-header { display: flex; align-items: flex-end; justify-content: space-between; gap: 18px; margin-bottom: 12px; }
.eyebrow { margin: 0 0 4px; color: #176b5a; font-size: 10px; font-weight: 700; letter-spacing: .1em; text-transform: uppercase; }
.page-header h2 { margin: 0; color: #26353a; font-size: 21px; letter-spacing: -.02em; }.page-header p:not(.eyebrow) { margin: 5px 0 0; color: #728087; font-size: 12px; }
.header-actions { display: flex; align-items: center; gap: 10px; }.last-sync { display: inline-flex; align-items: center; gap: 5px; color: #76868b; font-size: 10px; }.last-sync i { width: 6px; height: 6px; border-radius: 50%; background: #4b9b7e; }
.quality-summary { display: grid; grid-template-columns: 120px 120px 120px minmax(0, 1fr); gap: 0; margin-bottom: 10px; border: 1px solid #d8e1df; background: #fff; }.quality-summary > div { display: flex; min-height: 70px; flex-direction: column; gap: 3px; justify-content: center; padding: 10px 14px; border-right: 1px solid #e5ecea; }.quality-summary span, .quality-summary small { color: #7c8b8e; font-size: 10px; }.quality-summary strong { color: #263f3b; font: 700 22px ui-monospace, monospace; }.quality-summary strong.warning { color: #b7791f; }.quality-summary .summary-note { flex-direction: row; align-items: center; gap: 7px; border-right: 0; color: #748387; }.summary-note .el-icon { color: #176b5a; }
.quality-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; margin-bottom: 10px; }.quality-card { display: grid; grid-template-columns: 28px minmax(0, 1fr) auto; align-items: center; gap: 9px; min-width: 0; min-height: 74px; padding: 11px; border: 1px solid #d8e1df; border-radius: 5px; background: #fff; color: #53646a; cursor: pointer; text-align: left; transition: border-color 160ms ease, background-color 160ms ease; }.quality-card:hover, .quality-card.active { border-color: #97c6b9; background: #f0f8f5; }.quality-card .queue-icon { display: grid; width: 28px; height: 28px; place-items: center; border-radius: 4px; background: #eef4f3; color: #176b5a; }.quality-card strong { display: block; color: #304246; font-size: 11px; }.quality-card small { display: block; margin-top: 4px; overflow: hidden; color: #849297; font-size: 9px; text-overflow: ellipsis; white-space: nowrap; }.quality-card b { color: #b7791f; font: 700 17px ui-monospace, monospace; }
.quality-panel { border: 1px solid #d8e1df; background: #fff; }.panel-heading { display: flex; align-items: flex-end; justify-content: space-between; gap: 12px; padding: 13px 15px; border-bottom: 1px solid #e5ecea; }.panel-heading h3 { margin: 0; color: #304246; font-size: 14px; }.panel-heading p { margin: 4px 0 0; color: #859297; font-size: 10px; }.panel-tools { display: flex; gap: 4px; }.panel-tools .el-button { font-size: 10px; }
.quality-content { display: grid; grid-template-columns: minmax(0, 1fr) 260px; min-height: 285px; }.issue-list { min-width: 0; }.issue-row { display: grid; grid-template-columns: 7px minmax(0, 1fr) 65px 18px; align-items: center; gap: 9px; width: 100%; min-height: 72px; padding: 0 15px; border: 0; border-bottom: 1px solid #edf1f0; background: #fff; color: #53646a; cursor: pointer; text-align: left; }.issue-row:hover, .issue-row.selected { background: #f2f8f6; }.severity-dot { width: 6px; height: 6px; border-radius: 50%; }.issue-row.high .severity-dot { background: #be514d; }.issue-row.medium .severity-dot { background: #c88b34; }.issue-row.low .severity-dot { background: #4b9b7e; }.issue-main { min-width: 0; }.issue-main strong { display: block; overflow: hidden; color: #34484d; font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }.issue-main small, .issue-row time { display: block; margin-top: 4px; color: #93a0a3; font-size: 9px; }.issue-row time { margin-top: 0; text-align: right; }.issue-row > .el-icon { color: #5c9485; }
.issue-inspector { padding: 17px 15px; border-left: 1px solid #dfe7e5; background: #f8fbfa; }.severity-label { display: inline-flex; padding: 3px 5px; border-radius: 3px; font-size: 9px; }.severity-label.high { background: #fde7e5; color: #a84440; }.severity-label.medium { background: #fff1d8; color: #a56c1c; }.severity-label.low { background: #e4f3ed; color: #2f7f64; }.issue-inspector h3 { margin: 11px 0 5px; color: #304246; font-size: 14px; }.issue-inspector > p { margin: 0 0 14px; color: #738287; font-size: 10px; line-height: 1.55; }.issue-inspector dl { margin: 0; }.issue-inspector dl div { display: flex; justify-content: space-between; gap: 8px; padding: 8px 0; border-top: 1px solid #e2ebe8; font-size: 9px; }.issue-inspector dt { color: #819095; }.issue-inspector dd { margin: 0; color: #41565a; text-align: right; }.inspector-actions { display: flex; flex-direction: column; gap: 5px; margin-top: 15px; }.inspector-actions .el-button { justify-content: center; font-size: 10px; }
@media (max-width: 900px) { .quality-summary { grid-template-columns: repeat(3, 1fr); }.quality-summary .summary-note { grid-column: 1 / -1; min-height: 42px; border-top: 1px solid #e5ecea; }.quality-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }.quality-content { grid-template-columns: 1fr; }.issue-inspector { border-top: 1px solid #dfe7e5; border-left: 0; } }
@media (max-width: 560px) { .page-header { align-items: flex-start; flex-direction: column; }.header-actions { width: 100%; justify-content: space-between; }.quality-summary { grid-template-columns: repeat(3, 1fr); }.quality-summary > div { padding: 9px; }.quality-grid { grid-template-columns: 1fr; } }
</style>
