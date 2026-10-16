<template>
  <div class="projects-container">
    <div class="list-view-toolbar">
      <div class="list-title-block"><div><h1>项目总览</h1><p class="list-caption">从客户定点到量产移交，按项目追踪进度</p></div><el-button type="primary" :icon="Plus" @click="createVisible = true">新建项目</el-button></div>
      <div class="search-control"><el-icon><Search /></el-icon><el-input v-model="keyword" placeholder="搜索项目、客户或车型" clearable /></div>
      <div class="filter-controls"><el-select v-model="stage" placeholder="阶段" clearable><el-option v-for="item in stages" :key="item" :label="item" :value="item" /></el-select><el-select v-model="status" placeholder="状态" clearable><el-option v-for="item in statuses" :key="item" :label="item" :value="item" /></el-select></div>
    </div>
    <div class="project-metrics"><div><span>进行中项目</span><strong>{{ filteredProjects.filter(item => item.status === '进行中').length }}</strong><small>按目标SOP跟踪</small></div><div><span>定点报价组</span><strong>{{ filteredProjects.reduce((sum, item) => sum + item.quoteGroups.length, 0) }}</strong><small>左右件已成组管理</small></div><div><span>待处理事项</span><strong class="warning">{{ filteredProjects.reduce((sum, item) => sum + item.pending.length, 0) }}</strong><small>技术、客户与资料</small></div><div><span>最近SOP</span><strong>2026.12</strong><small>启明座椅弹片</small></div></div>
    <div class="table-meta"><span>{{ filteredProjects.length }} 个项目</span><span>点击项目查看报价组、样件、模具、PPAP和图纸变更</span></div>
    <el-table :data="filteredProjects" stripe @row-click="openDetail">
      <el-table-column label="项目" min-width="250"><template #default="{ row }"><div class="project-cell"><strong>{{ row.name }}</strong><small class="mono">{{ row.id }} · {{ row.customerProject }}</small></div></template></el-table-column>
      <el-table-column prop="customer" label="客户" width="130" />
      <el-table-column label="项目阶段" width="125"><template #default="{ row }"><el-tag size="small" :type="stageType(row.stage)">{{ row.stage }}</el-tag></template></el-table-column>
      <el-table-column label="当前节点" min-width="190"><template #default="{ row }"><div class="current-stage-cell"><el-tag size="small" type="warning">{{ currentMilestone(row) }}</el-tag><small v-if="nextMilestone(row)">下一步：{{ nextMilestone(row) }}</small></div></template></el-table-column>
      <el-table-column label="目标SOP" width="125"><template #default="{ row }"><span class="mono">{{ row.sop }}</span></template></el-table-column>
      <el-table-column label="负责人" width="100" prop="owner" />
      <el-table-column label="待处理" width="95"><template #default="{ row }"><span :class="['pending-count', { danger: row.pending.length }]">{{ row.pending.length }} 项</span></template></el-table-column>
      <el-table-column label="操作" width="105" fixed="right"><template #default="{ row }"><el-button link type="primary" @click.stop="openDetail(row)">查看项目</el-button></template></el-table-column>
    </el-table>

    <el-drawer v-model="detailVisible" :title="selected?.name || '项目详情'" size="min(920px, 92vw)">
      <template v-if="selected">
        <div class="detail-head"><div><p class="eyebrow">{{ selected.id }} · {{ selected.customerProject }}</p><h2>{{ selected.customer }} / {{ selected.name }}</h2><p class="detail-subhead">负责人 {{ selected.owner }} · 定点 {{ selected.nominatedAt }} · 目标SOP {{ selected.sop }}</p></div><el-tag :type="selected.status === '进行中' ? 'success' : 'info'">{{ selected.status }}</el-tag></div>
        <div class="detail-tabs"><button v-for="tab in detailTabs" :key="tab" :class="{ active: detailTab === tab }" type="button" @click="detailTab = tab">{{ tab }}</button></div>
        <section v-if="detailTab === '项目概览'" class="detail-section"><div class="section-heading"><div><span class="section-kicker">项目进度</span><h3>里程碑与待处理事项</h3></div><el-button size="small" :icon="Plus" @click="ElMessage.success('任务入口已预留')">添加任务</el-button></div><div class="milestone-line"><div v-for="item in selected.milestones" :key="item.label" :class="['milestone', item.state]"><i></i><strong>{{ item.label }}</strong><small>{{ item.date }}</small></div></div><div class="detail-grid"><div class="inner-panel"><h4>待处理事项</h4><button v-for="item in selected.pending" :key="item" class="pending-row" type="button"><i></i><span>{{ item }}</span><el-icon><ArrowRight /></el-icon></button></div><div class="inner-panel"><h4>项目阶段</h4><div class="stage-summary"><strong>{{ selected.stage }}</strong><span>推荐方案路径：{{ selected.quoteGroups[0]?.path || '待关联报价组' }}</span><el-progress :percentage="progress(selected)" :stroke-width="7" /></div></div></div></section>
        <section v-else-if="detailTab === '报价组与零件'" class="detail-section"><div class="section-heading"><div><span class="section-kicker">已定点</span><h3>报价组与左右件</h3></div><el-button size="small" type="primary" @click="ElMessage.success('报价组入口已预留')">新增报价组</el-button></div><article v-for="group in selected.quoteGroups" :key="group.id" class="quote-group"><header><div><strong>{{ group.id }}</strong><span>{{ group.vehicle }} · {{ group.path }}</span></div><el-tag size="small" type="success">{{ group.status }}</el-tag></header><div class="quote-plan"><span>推荐方案</span><strong>{{ group.toolingType }}</strong><span>共用模具费 <b>¥{{ formatAmount(group.toolingCost) }}</b></span><span>寿命 <b>{{ group.toolingLife.toLocaleString() }}</b> 次</span><span>材料 <b>{{ group.material }}</b></span></div><el-table :data="group.parts" size="small"><el-table-column prop="customerPartNo" label="零件编号" width="160" /><el-table-column prop="name" label="件名" min-width="210" /><el-table-column label="关联" width="140"><template #default="{ row }"><span v-if="row.pairLabel" class="pair-mark">{{ row.pairLabel }}</span><span v-else>单件</span></template></el-table-column><el-table-column prop="annualUsage" label="年用量" width="110" /><el-table-column label="产品价格" width="120"><template #default="{ row }">¥{{ formatAmount(row.price) }}</template></el-table-column></el-table></article></section>
        <section v-else-if="detailTab === '样件与量产模具'" class="detail-section"><div class="detail-grid"><div class="inner-panel"><h4>样件批次</h4><template v-if="selectedSample"><div class="compact-record"><strong>{{ selectedSample.id }}</strong><span>{{ selectedSample.purpose }} · {{ selectedSample.pair }}</span><el-tag size="small" type="success">{{ selectedSample.status }}</el-tag></div><div class="compact-record"><strong>数量</strong><span>{{ selectedSample.qty }} 件 · 计划完成 {{ selectedSample.planned }}</span></div></template><div v-else class="compact-record"><strong>暂无样件批次</strong><span>可从样件模块新建批次</span></div></div><div class="inner-panel"><h4>量产模具 / OTS</h4><div v-if="selected.quoteGroups[0]" class="compact-record"><strong>{{ selected.quoteGroups[0].toolingType }}</strong><span>模具开发中 · 试模计划待确认</span><el-tag size="small" type="warning">OTS准备中</el-tag></div><div v-else class="compact-record"><strong>待关联量产模具</strong><span>报价组确认后进入模具管理</span></div><div class="compact-record"><strong>OTS</strong><span>归属于量产模具记录管理</span></div></div></div></section>
        <section v-else class="detail-section"><div class="detail-grid"><div class="inner-panel"><h4>PPAP资料包</h4><div class="compact-record"><strong>{{ selected.stage === 'PPAP' ? '资料整理中' : '默认不需要' }}</strong><span>文件上传与查询入口</span><el-button link type="primary" size="small" @click="ElMessage.success('PPAP上传入口已预留')">打开</el-button></div></div><div class="inner-panel"><h4>最近图纸变更</h4><div v-if="selectedChange" class="compact-record"><strong>{{ selectedChange.drawing }} {{ selectedChange.to }}</strong><span>{{ selectedChange.reason }} · 默认不需要更新PPAP</span><el-tag size="small" :type="selectedChange.status === '已生效' ? 'success' : 'warning'">{{ selectedChange.status }}</el-tag></div><div v-else class="compact-record"><strong>暂无图纸变更</strong><span>文控登记新版本后将在此显示</span></div></div></div></section>
      </template>
    </el-drawer>

    <el-dialog v-model="createVisible" title="新建项目" width="520px"><el-form :model="createForm" label-width="100px"><el-form-item label="项目名称"><el-input v-model="createForm.name" placeholder="例如：星海后桥支架开发" /></el-form-item><el-form-item label="客户"><el-input v-model="createForm.customer" /></el-form-item><el-form-item label="客户项目号"><el-input v-model="createForm.customerProject" /></el-form-item><el-form-item label="目标SOP"><el-date-picker v-model="createForm.sop" type="date" value-format="YYYY-MM-DD" style="width:100%" /></el-form-item><el-form-item label="负责人"><el-input v-model="createForm.owner" /></el-form-item></el-form><template #footer><el-button @click="createVisible = false">取消</el-button><el-button type="primary" @click="createProject">保存项目</el-button></template></el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { ArrowRight, Plus, Search } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { changes, projects, samples, type ProjectRecord, type ProjectStage } from './data'

const keyword = ref('')
const stage = ref('')
const status = ref('')
const detailVisible = ref(false)
const createVisible = ref(false)
const selected = ref<ProjectRecord | undefined>()
const detailTab = ref('项目概览')
const detailTabs = ['项目概览', '报价组与零件', '样件与量产模具', 'PPAP与图纸']
const stages: ProjectStage[] = ['待启动', '打样', '量产模具', 'PPAP', '量产导入', '已移交']
const statuses = ['待启动', '进行中', '暂停', '已完成']
const createForm = reactive({ name: '', customer: '', customerProject: '', sop: '', owner: '' })
const formatAmount = (value: number | null | undefined) => {
  if (value == null || !Number.isFinite(Number(value))) return '-'
  return Number(value).toFixed(4).replace(/\.?0+$/, '')
}

const filteredProjects = computed(() => projects.filter(item => { const text = `${item.id} ${item.name} ${item.customer} ${item.customerProject}`.toLowerCase(); return (!keyword.value || text.includes(keyword.value.toLowerCase())) && (!stage.value || item.stage === stage.value) && (!status.value || item.status === status.value) }))
const selectedSample = computed(() => selected.value ? samples.find(item => item.project === selected.value?.id) : undefined)
const selectedChange = computed(() => selected.value ? changes.find(item => item.project === selected.value?.id) : undefined)
const progress = (item: ProjectRecord) => Math.round(item.milestones.filter(m => m.state === 'done').length / item.milestones.length * 100)
const currentMilestone = (item: ProjectRecord) => item.milestones.find(milestone => milestone.state === 'active')?.label || item.milestones.find(milestone => milestone.state === 'pending')?.label || item.milestones[item.milestones.length - 1]?.label || item.stage
const nextMilestone = (item: ProjectRecord) => {
  const activeIndex = item.milestones.findIndex(milestone => milestone.state === 'active')
  return activeIndex >= 0 ? item.milestones[activeIndex + 1]?.label : undefined
}
const stageType = (value: string) => value === '已移交' ? 'success' : value === 'PPAP' ? 'warning' : value === '量产模具' ? 'primary' : 'info'
const openDetail = (item: ProjectRecord) => { selected.value = item; detailTab.value = '项目概览'; detailVisible.value = true }
const createProject = () => { if (!createForm.name || !createForm.customer) return ElMessage.warning('请填写项目名称和客户'); projects.unshift({ id: `P-2026-${String(projects.length + 1).padStart(3, '0')}`, name: createForm.name, customer: createForm.customer, customerProject: createForm.customerProject || '-', owner: createForm.owner || '待分配', stage: '待启动', status: '待启动', sop: createForm.sop || '-', nominatedAt: new Date().toISOString().slice(0, 10), quoteGroups: [], milestones: [{ label: '项目启动', date: new Date().toISOString().slice(0, 10), state: 'active' }], pending: ['待关联定点报价组'] }); Object.assign(createForm, { name: '', customer: '', customerProject: '', sop: '', owner: '' }); createVisible.value = false; ElMessage.success('项目已创建') }
</script>

<style scoped>
.projects-container { min-width: 0; padding: 18px 0 30px; color: var(--zephyr-ink); }
.project-metrics { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 0; margin-bottom: 14px; border: 1px solid var(--zephyr-border); border-radius: 8px; overflow: hidden; background: var(--zephyr-surface); box-shadow: var(--zephyr-shadow-sm); }
.project-metrics > div { min-height: 80px; padding: 12px 16px; border-right: 1px solid var(--zephyr-border-soft); background: transparent; }.project-metrics > div:first-child { background: var(--zephyr-primary-soft); }.project-metrics > div:last-child { border-right: 0; }
.project-metrics span, .project-metrics small { display: block; color: var(--zephyr-muted); font-size: 11px; }
.project-metrics strong { display: block; margin: 7px 0 2px; color: var(--zephyr-ink); font-family: 'IBM Plex Mono', Consolas, monospace; font-size: 23px; line-height: 1; }
.project-metrics strong.warning { color: var(--zephyr-warning); }
.project-cell, .current-stage-cell { display: flex; align-items: flex-start; flex-direction: column; gap: 3px; }
.project-cell strong { color: var(--zephyr-ink); font-size: 13px; }
.project-cell small { color: var(--zephyr-muted); }
.mono { font-family: 'IBM Plex Mono', Consolas, monospace; font-size: 11px; }
.current-stage-cell .el-tag { max-width: 100%; }
.current-stage-cell small { overflow: hidden; max-width: 100%; color: var(--zephyr-muted); font-size: 10px; text-overflow: ellipsis; white-space: nowrap; }
.pending-count { color: var(--zephyr-muted); font-size: 11px; }
.pending-count.danger { color: var(--zephyr-danger); font-weight: 650; }
.detail-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; padding-bottom: 16px; border-bottom: 1px solid var(--zephyr-border); }
.detail-head h2 { margin: 4px 0; color: var(--zephyr-ink); font-size: 21px; }
.detail-subhead { margin: 0; color: var(--zephyr-muted); font-size: 12px; }
.eyebrow, .section-kicker { margin: 0; color: var(--zephyr-primary); font-size: 11px; font-weight: 700; letter-spacing: .04em; }
.detail-tabs { display: flex; gap: 18px; margin: 0 -20px; padding: 0 20px; border-bottom: 1px solid var(--zephyr-border); }
.detail-tabs button { height: 44px; padding: 0; border: 0; border-bottom: 2px solid transparent; background: transparent; color: var(--zephyr-muted); font: inherit; font-size: 13px; cursor: pointer; }
.detail-tabs button.active { border-bottom-color: var(--zephyr-primary); color: var(--zephyr-primary); font-weight: 650; }
.detail-section { padding-top: 18px; }
.section-heading { display: flex; align-items: flex-end; justify-content: space-between; gap: 12px; margin-bottom: 12px; }
.section-heading h3 { margin: 3px 0 0; color: var(--zephyr-ink); font-size: 16px; }
.milestone-line { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 8px; padding: 14px 0 22px; }
.milestone { position: relative; display: flex; flex-direction: column; gap: 5px; padding-top: 12px; border-top: 2px solid #dfe7e4; }
.milestone::before { position: absolute; top: -6px; left: 0; width: 10px; height: 10px; border-radius: 50%; background: #cad8d3; content: ''; }
.milestone.done { border-top-color: var(--zephyr-primary); }.milestone.done::before { background: var(--zephyr-primary); }.milestone.active { border-top-color: var(--zephyr-warning); }.milestone.active::before { background: var(--zephyr-warning); }
.milestone strong { font-size: 12px; }.milestone small { color: var(--zephyr-muted); font-family: 'IBM Plex Mono', Consolas, monospace; font-size: 10px; }
.detail-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.inner-panel { min-width: 0; padding: 14px; border: 1px solid var(--zephyr-border); background: #f9fbfa; }.inner-panel h4 { margin: 0 0 10px; color: var(--zephyr-ink); font-size: 13px; }
.pending-row, .compact-record { display: flex; align-items: center; gap: 9px; width: 100%; min-height: 34px; padding: 7px 0; border: 0; border-top: 1px solid #e6edeb; background: transparent; color: var(--zephyr-ink); font: inherit; font-size: 12px; text-align: left; }.pending-row:first-of-type, .compact-record:first-of-type { border-top: 0; }.pending-row i { width: 6px; height: 6px; border-radius: 50%; background: var(--zephyr-warning); }.pending-row span { flex: 1; }.stage-summary { display: grid; gap: 9px; }.stage-summary strong { color: var(--zephyr-primary); font-size: 18px; }.stage-summary span { color: var(--zephyr-muted); font-size: 12px; }.quote-group { margin-bottom: 14px; border: 1px solid var(--zephyr-border); background: #fff; }.quote-group > header, .quote-plan { display: flex; align-items: center; gap: 14px; padding: 11px 13px; }.quote-group > header { justify-content: space-between; border-bottom: 1px solid #e5ece9; }.quote-group > header div { display: flex; align-items: baseline; gap: 10px; }.quote-group > header span, .quote-plan { color: var(--zephyr-muted); font-size: 11px; }.quote-plan { flex-wrap: wrap; background: #f6faf8; }.quote-plan strong { color: var(--zephyr-primary); }.quote-plan b { color: var(--zephyr-ink); font-family: 'IBM Plex Mono', Consolas, monospace; }.pair-mark { color: var(--zephyr-primary); font-size: 11px; }.compact-record strong { min-width: 125px; }.compact-record span { flex: 1; color: var(--zephyr-muted); font-size: 11px; }
@media (max-width: 800px) { .project-metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); }.detail-grid { grid-template-columns: 1fr; }.milestone-line { grid-template-columns: 1fr 1fr; gap: 12px; }.detail-tabs { overflow-x: auto; }.detail-tabs button { flex: 0 0 auto; } }
@media (max-width: 520px) { .project-metrics { grid-template-columns: 1fr 1fr; }.milestone-line { grid-template-columns: 1fr; }.project-metrics > div { min-height: 78px; }.project-metrics strong { font-size: 20px; } }
</style>
