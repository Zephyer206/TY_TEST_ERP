<template>
  <div class="research-workbench">
    <header class="page-heading">
      <div>
        <h1>研发合规工作台</h1>
        <p>统一研发项目、费用、工时与业务证据链，支持高新认定和 IPO 穿透核查</p>
        <p class="demo-notice">演示台账 · 保存在当前浏览器 · 尚未接入财务和档案系统</p>
      </div>
      <div class="heading-actions">
        <span class="year-label">2026 年度示例</span>
        <el-button type="primary" :icon="Plus" @click="createVisible = true">登记研发项目</el-button>
      </div>
    </header>

    <section class="metric-strip" aria-label="研发合规核心指标">
      <div class="metric metric-primary">
        <span>证据链完整度</span>
        <strong>{{ averageEvidence }}%</strong>
        <small>目标 ≥ 95%，按演示台账计算</small>
        <svg viewBox="0 0 120 28" role="img" aria-label="近六期完整度持续提升"><polyline points="2,24 24,20 47,21 70,12 93,14 118,5" /></svg>
      </div>
      <div class="metric"><span>项目费用台账</span><strong>{{ currency(totalSpent) }}</strong><small>尚未完成四口径核对</small></div>
      <div class="metric"><span>研发项目</span><strong>{{ researchProjects.length }}</strong><small>{{ activeCount }} 个执行中</small></div>
      <div class="metric"><span>待核验事项</span><strong class="warning">{{ riskCount }}</strong><small>{{ missingDocumentCount }} 项资料，{{ pendingSourceCount }} 项单据</small></div>
    </section>

    <section class="stage-console" aria-labelledby="stage-title">
      <div class="section-title">
        <div><h2 id="stage-title">24 周体系建设计划</h2><p>四阶段节点与校验标准模板</p></div>
        <span class="stage-progress-label">示例：第 15 周</span>
      </div>
      <div class="stage-track">
        <button v-for="(item, index) in stagePlan" :key="item.name" type="button" :class="['stage-step', item.state, { selected: selectedStage === index }]" @click="selectedStage = index">
          <span>{{ index + 1 }}</span><strong>{{ item.name }}</strong><small>{{ item.weeks }}</small>
        </button>
      </div>
      <div class="standard-row">
        <span class="standard-label">本阶段校验</span>
        <span v-for="standard in stagePlan[selectedStage].standards" :key="standard" class="standard-item"><i />{{ standard }}</span>
      </div>
    </section>

    <nav class="domain-tabs" aria-label="研发合规数据域">
      <button v-for="tab in tabs" :key="tab.key" type="button" :class="{ active: activeTab === tab.key }" :aria-current="activeTab === tab.key ? 'page' : undefined" @click="activeTab = tab.key">
        <el-icon><component :is="tab.icon" /></el-icon>{{ tab.label }}<span v-if="tab.count">{{ tab.count }}</span>
      </button>
    </nav>

    <template v-if="activeTab === 'projects'">
      <div class="filter-bar">
        <div class="search-control"><el-icon><Search /></el-icon><el-input v-model="keyword" placeholder="搜索项目编号、名称或负责人" clearable /></div>
        <el-select v-model="typeFilter" placeholder="项目类型" clearable><el-option v-for="item in projectTypes" :key="item" :label="item" :value="item" /></el-select>
        <el-select v-model="stageFilter" placeholder="当前阶段" clearable><el-option v-for="item in stagePlan" :key="item.name" :label="item.name" :value="item.name" /></el-select>
        <button v-if="keyword || typeFilter || stageFilter" class="reset-filter" type="button" @click="resetFilters">重置筛选</button>
      </div>
      <div class="project-grid">
        <section class="data-panel project-panel">
          <div class="panel-heading"><div><h2>重点研发项目清单</h2><p>{{ filteredProjects.length }} 个项目；仅展示登记为研发类型的项目</p></div><span class="boundary-note"><i />演示分类</span></div>
          <el-table :data="filteredProjects" stripe row-key="id" @row-click="openProject">
            <el-table-column label="项目" min-width="230"><template #default="{ row }"><div class="project-name"><strong>{{ row.name }}</strong><small>{{ row.id }} · {{ row.department }}</small></div></template></el-table-column>
            <el-table-column prop="type" label="项目类型" width="110" />
            <el-table-column prop="owner" label="负责人" width="84" />
            <el-table-column label="当前阶段" width="116"><template #default="{ row }"><span class="status-text"><i :class="statusClass(row.status)" />{{ row.stage }}</span></template></el-table-column>
            <el-table-column label="费用执行" min-width="160"><template #default="{ row }"><div class="amount-progress"><span>{{ currency(row.spent) }} / {{ currency(row.budget) }}</span><el-progress :percentage="row.budget ? Math.min(100, Math.round(row.spent / row.budget * 100)) : 0" :show-text="false" :stroke-width="5" /></div></template></el-table-column>
            <el-table-column label="证据完整度" width="120" align="right"><template #default="{ row }"><strong :class="['evidence-value', { warning: row.evidenceRate < 95 }]">{{ row.evidenceRate }}%</strong></template></el-table-column>
            <el-table-column label="操作" width="88" align="center"><template #default="{ row }"><el-button link type="primary" @click.stop="openProject(row)">查看档案</el-button></template></el-table-column>
          </el-table>
        </section>
        <aside class="data-panel action-panel">
          <div class="panel-heading"><div><h2>合规待办</h2><p>按核查风险排序</p></div><strong>{{ riskCount }}</strong></div>
          <button v-for="item in riskItems" :key="item.title" type="button" class="risk-row" @click="openProject(item.project)">
            <i :class="item.level" /><span><strong>{{ item.title }}</strong><small>{{ item.project.id }} · {{ item.owner }}</small></span><em>{{ item.due }}</em>
          </button>
        </aside>
      </div>
    </template>

    <template v-else-if="activeTab === 'costs'">
      <div class="two-column-content">
        <section class="data-panel wide-panel">
          <div class="panel-heading"><div><h2>四口径核对</h2><p>统计、会计、税务、科技口径待分别接入</p></div><span class="reconciled"><i />待核对</span></div>
          <el-table :data="researchProjects" stripe>
            <el-table-column prop="id" label="项目编号" width="120" />
            <el-table-column prop="name" label="项目名称" min-width="210" />
            <el-table-column label="项目台账" width="118" align="right"><template #default="{ row }">{{ money(row.spent) }}</template></el-table-column>
            <el-table-column v-for="label in ['统计口径', '会计口径', '税务口径', '科技口径']" :key="label" :label="label" width="118" align="right"><template #default>待接入</template></el-table-column>
            <el-table-column label="结果" width="90"><template #default><span class="status-text"><i class="warning" />待核对</span></template></el-table-column>
          </el-table>
        </section>
        <aside class="data-panel breakdown-panel">
          <div class="panel-heading"><div><h2>费用构成</h2><p>{{ currency(totalSpent) }}</p></div></div>
          <div v-for="item in costBreakdown" :key="item.name" class="breakdown-row"><div><span>{{ item.name }}</span><strong>{{ currency(item.amount) }}</strong></div><div class="bar-track"><i :style="{ width: item.percent + '%' }" /></div><small>{{ item.percent }}%</small></div>
          <div class="validation-note"><el-icon><Warning /></el-icon><span><strong>1 笔分摊待复核</strong>RD-2026-002 共用设备折旧需补充实际机时签字记录。</span></div>
        </aside>
      </div>
      <section class="data-panel trace-panel">
        <div class="panel-heading"><div><h2>项目费用穿透台账</h2><p>项目 → 业务单据 → 财务凭证逐笔关联</p></div></div>
        <el-table :data="allCosts" stripe>
          <el-table-column prop="projectId" label="项目" width="122" /><el-table-column prop="category" label="费用科目" width="110" /><el-table-column prop="amount" label="金额" width="120" align="right"><template #default="{ row }">{{ money(row.amount) }}</template></el-table-column><el-table-column prop="sourceNo" label="业务单据" min-width="155" /><el-table-column prop="voucherNo" label="财务凭证" min-width="160" /><el-table-column prop="allocation" label="归集 / 分摊依据" width="130" /><el-table-column label="税务资格" width="100"><template #default="{ row }"><span class="status-text"><i :class="row.eligible ? 'success' : 'warning'" />{{ row.eligible ? '可扣除' : '待复核' }}</span></template></el-table-column>
        </el-table>
      </section>
    </template>

    <template v-else-if="activeTab === 'people'">
      <section class="data-panel">
        <div class="panel-heading"><div><h2>研发人员身份与工时台账</h2><p>量产测试、后勤、安保及常规生产检测人员不纳入研发人工</p></div><span class="boundary-note"><i />身份边界已公示</span></div>
        <el-table :data="peopleLedger" stripe>
          <el-table-column prop="name" label="姓名" width="90" /><el-table-column prop="role" label="人员分类" min-width="155" /><el-table-column prop="department" label="部门" width="130" /><el-table-column prop="project" label="归属项目" min-width="160" />
          <el-table-column label="研发工时" min-width="190"><template #default="{ row }"><div class="hours-cell"><span>{{ row.hours }} / {{ row.totalHours }} 小时</span><div class="bar-track"><i :style="{ width: Math.round(row.hours / row.totalHours * 100) + '%' }" /></div></div></template></el-table-column>
          <el-table-column label="研发占比" width="100" align="right"><template #default="{ row }">{{ Math.round(row.hours / row.totalHours * 100) }}%</template></el-table-column><el-table-column prop="evidence" label="身份佐证" min-width="230" />
        </el-table>
      </section>
    </template>

    <template v-else-if="activeTab === 'documents'">
      <section class="data-panel">
        <div class="panel-heading"><div><h2>业务原始单据链</h2><p>生产、采购、质量与设备环节按研发项目单独编号</p></div></div>
        <el-table :data="sourceDocuments" stripe>
          <el-table-column prop="no" label="单据编号" width="160" /><el-table-column prop="type" label="单据类型" min-width="190" /><el-table-column prop="project" label="研发项目" width="130" /><el-table-column prop="department" label="责任部门" width="100" /><el-table-column prop="trace" label="穿透路径" min-width="260" /><el-table-column label="归档状态" width="120"><template #default="{ row }"><span class="status-text"><i :class="row.status === '待复核' ? 'warning' : 'success'" />{{ row.status }}</span></template></el-table-column>
        </el-table>
      </section>
      <div class="document-domain-strip"><div v-for="item in documentDomains" :key="item.name"><el-icon><component :is="item.icon" /></el-icon><span><strong>{{ item.name }}</strong><small>{{ item.detail }}</small></span><em>{{ item.coverage }}%</em></div></div>
    </template>

    <template v-else>
      <div class="two-column-content compliance-content">
        <section class="data-panel wide-panel">
          <div class="panel-heading"><div><h2>高新认定量化指标模板</h2><p>下列数值为演示，不作为申报结论</p></div><span class="reconciled"><i />待数据接入</span></div>
          <div class="indicator-list"><div v-for="item in complianceMetrics" :key="item.name" class="indicator-row"><span>{{ item.name }}</span><strong>{{ item.value }}</strong><small>{{ item.target }}</small><em :class="{ attention: item.status === '关注' }"><i />{{ item.status }}</em></div></div>
        </section>
        <aside class="data-panel archive-panel">
          <div class="panel-heading"><div><h2>项目档案清单</h2><p>导出已登记的文档目录与状态</p></div></div>
          <button v-for="project in researchProjects" :key="project.id" type="button" class="archive-row" @click="openProject(project)"><el-icon><FolderOpened /></el-icon><span><strong>{{ project.id }}</strong><small>{{ project.documents.filter(item => item.status === '齐全').length }} / {{ project.documents.length }} 项已归档</small></span><em>{{ project.evidenceRate }}%</em></button>
          <el-button plain :icon="Download" @click="exportArchive">生成核查档案清单</el-button>
        </aside>
      </div>
      <section class="collaboration-strip"><div><span>每周</span><strong>部门研发复盘</strong><small>周五 16:00 · 3 项待办跟进</small></div><div><span>每半月</span><strong>跨部门协调会</strong><small>下次 10 月 16 日 · 财务牵头</small></div><div><span>每月</span><strong>四口径关账核对</strong><small>次月第 3 个工作日完成</small></div></section>
    </template>

    <el-drawer v-model="detailVisible" :title="selectedProject ? `${selectedProject.id} · ${selectedProject.name}` : '项目档案'" size="min(920px, 94vw)" class="research-detail-drawer">
      <template v-if="selectedProject">
        <div class="drawer-summary"><div><span>项目类型</span><strong>{{ selectedProject.type }}</strong></div><div><span>当前阶段</span><strong>{{ selectedProject.stage }}</strong></div><div><span>费用执行</span><strong>{{ selectedProject.budget ? Math.round(selectedProject.spent / selectedProject.budget * 100) : 0 }}%</strong></div><div><span>证据完整度</span><strong :class="{ warning: selectedProject.evidenceRate < 95 }">{{ selectedProject.evidenceRate }}%</strong></div></div>
        <div class="drawer-tabs"><button v-for="tab in ['全周期文档', '费用穿透', '项目摘要']" :key="tab" type="button" :class="{ active: detailTab === tab }" @click="detailTab = tab">{{ tab }}</button></div>
        <section v-if="detailTab === '全周期文档'" class="drawer-section"><div class="document-list"><div v-for="document in selectedProject.documents" :key="document.name" class="document-row"><span class="document-category">{{ document.category }}</span><span><strong>{{ document.name }}</strong><small>最近更新 {{ document.updatedAt }}</small></span><em :class="{ warning: document.status === '待补' }">{{ document.status }}</em></div></div></section>
        <section v-else-if="detailTab === '费用穿透'" class="drawer-section"><el-table :data="selectedProject.costs" stripe><el-table-column prop="category" label="费用科目" width="110" /><el-table-column label="金额" width="120" align="right"><template #default="{ row }">{{ money(row.amount) }}</template></el-table-column><el-table-column prop="sourceNo" label="业务单据" min-width="145" /><el-table-column prop="voucherNo" label="财务凭证" min-width="155" /><el-table-column prop="allocation" label="分摊依据" width="110" /></el-table></section>
        <section v-else class="drawer-section summary-grid"><div><span>执行期间</span><strong>{{ selectedProject.startDate }} 至 {{ selectedProject.endDate }}</strong></div><div><span>项目负责人</span><strong>{{ selectedProject.owner }} · {{ selectedProject.department }}</strong></div><div><span>研发预算</span><strong>{{ money(selectedProject.budget) }}</strong></div><div><span>加计扣除适配率</span><strong>{{ selectedProject.taxRate }}%</strong></div></section>
      </template>
    </el-drawer>

    <el-dialog v-model="createVisible" title="登记研发项目" width="560px">
      <el-form :model="createForm" label-width="96px">
        <el-form-item label="项目名称"><el-input v-model="createForm.name" placeholder="输入研发项目名称" /></el-form-item>
        <el-form-item label="项目类型"><el-segmented v-model="createForm.type" :options="projectTypes" /></el-form-item>
        <el-form-item label="负责人"><el-input v-model="createForm.owner" /></el-form-item>
        <el-form-item label="责任部门"><el-input v-model="createForm.department" /></el-form-item>
        <el-form-item label="研发预算"><el-input-number v-model="createForm.budget" :min="0" :step="10000" controls-position="right" style="width: 100%" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="createVisible = false">取消</el-button><el-button type="primary" @click="createProject">保存项目</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Collection, Document, Download, Files, FolderOpened, Money, Plus, Search, User, Warning } from '@element-plus/icons-vue'
import { complianceMetrics, peopleLedger, researchProjects, sourceDocuments, stagePlan, type ResearchProject, type ResearchProjectType } from './research-data'

type TabKey = 'projects' | 'costs' | 'people' | 'documents' | 'compliance'
const activeTab = ref<TabKey>('projects')
const selectedStage = ref(2)
const keyword = ref('')
const typeFilter = ref('')
const stageFilter = ref('')
const detailVisible = ref(false)
const createVisible = ref(false)
const detailTab = ref('全周期文档')
const selectedProject = ref<ResearchProject | null>(null)
const projectTypes: ResearchProjectType[] = ['新产品研发', '工艺改良', '技术迭代']
const createForm = reactive({ name: '', type: '新产品研发' as ResearchProjectType, owner: '', department: '', budget: 0 })

const tabs = computed(() => [
  { key: 'projects' as TabKey, label: '项目与档案', icon: Collection, count: researchProjects.length },
  { key: 'costs' as TabKey, label: '费用核算', icon: Money, count: 0 },
  { key: 'people' as TabKey, label: '人员工时', icon: User, count: 0 },
  { key: 'documents' as TabKey, label: '业务单据', icon: Document, count: 0 },
  { key: 'compliance' as TabKey, label: '合规监控', icon: Files, count: riskCount.value },
])
const totalSpent = computed(() => researchProjects.reduce((sum, item) => sum + item.spent, 0))
const averageEvidence = computed(() => researchProjects.length ? Math.round(researchProjects.reduce((sum, item) => sum + item.evidenceRate, 0) / researchProjects.length) : 0)
const activeCount = computed(() => researchProjects.filter(item => item.status === '进行中').length)
const missingDocumentCount = computed(() => researchProjects.flatMap(item => item.documents).filter(item => item.status === '待补').length)
const pendingSourceCount = computed(() => sourceDocuments.filter(item => item.status === '待复核').length)
const riskCount = computed(() => missingDocumentCount.value + pendingSourceCount.value)
const filteredProjects = computed(() => researchProjects.filter(item => {
  const term = keyword.value.trim().toLowerCase()
  return (!term || `${item.id} ${item.name} ${item.owner}`.toLowerCase().includes(term)) && (!typeFilter.value || item.type === typeFilter.value) && (!stageFilter.value || item.stage === stageFilter.value)
}))
const allCosts = computed(() => researchProjects.flatMap(project => project.costs.map(cost => ({ ...cost, projectId: project.id }))))
const costBreakdown = computed(() => {
  const grouped = allCosts.value.reduce<Record<string, number>>((result, item) => { result[item.category] = (result[item.category] || 0) + item.amount; return result }, {})
  return Object.entries(grouped).map(([name, amount]) => ({ name, amount, percent: totalSpent.value ? Math.round(amount / totalSpent.value * 100) : 0 })).sort((left, right) => right.amount - left.amount)
})
const riskItems = computed(() => [
  ...researchProjects.flatMap(project => project.documents.filter(document => document.status === '待补').map(document => ({ title: `补充${document.name}`, project, owner: project.owner, due: '待补', level: 'medium' }))),
  ...sourceDocuments.filter(source => source.status === '待复核').map(source => ({ title: `复核${source.type}`, project: researchProjects.find(project => project.id === source.project) || researchProjects[0], owner: source.department, due: '待复核', level: 'high' })),
])
const documentDomains = [
  { name: '生产领料', detail: '专用编号与项目绑定', coverage: 96, icon: Collection },
  { name: '研发采购', detail: '采购、入库、领用全链路', coverage: 93, icon: Document },
  { name: '质量检测', detail: '样品报告按项目归档', coverage: 100, icon: Files },
  { name: '工艺设备', detail: '图纸、变更与机时记录', coverage: 89, icon: Warning },
]

function money(value: number) { return `¥${value.toLocaleString('zh-CN')}` }
function currency(value: number) { return value >= 10000 ? `¥${(value / 10000).toFixed(1)}万` : money(value) }
function statusClass(status: ResearchProject['status']) { return status === '进行中' ? 'success' : status === '待验收' ? 'warning' : 'muted' }
function resetFilters() { keyword.value = ''; typeFilter.value = ''; stageFilter.value = '' }
function openProject(project: ResearchProject) { selectedProject.value = project; detailTab.value = '全周期文档'; detailVisible.value = true }
function exportArchive() {
  const rows = [['项目编号', '项目名称', '文档类别', '文档名称', '状态', '最近更新'], ...researchProjects.flatMap(project => project.documents.map(document => [project.id, project.name, document.category, document.name, document.status, document.updatedAt]))]
  const csv = '\uFEFF' + rows.map(row => row.map(value => `"${String(value).replace(/"/g, '""')}"`).join(',')).join('\r\n')
  const safeCsv = csv.replace(/(^|,|\r\n)"([=+@-])/g, '$1"\'$2')
  const url = URL.createObjectURL(new Blob([safeCsv], { type: 'text/csv;charset=utf-8' }))
  const link = document.createElement('a'); link.href = url; link.download = '研发项目档案清单-演示.csv'; link.click(); URL.revokeObjectURL(url)
  ElMessage.success('演示档案清单已下载')
}
function createProject() {
  if (!createForm.name.trim() || !createForm.owner.trim() || !createForm.department.trim()) return ElMessage.warning('请完整填写项目名称、负责人和责任部门')
  const id = `RD-2026-${String(Math.max(0, ...researchProjects.map(project => Number(project.id.match(/^RD-2026-(\d+)$/)?.[1] || 0))) + 1).padStart(3, '0')}`
  researchProjects.unshift({ id, name: createForm.name.trim(), type: createForm.type, owner: createForm.owner.trim(), department: createForm.department.trim(), stage: '诊断规划', status: '进行中', startDate: new Date().toISOString().slice(0, 10), endDate: '-', budget: createForm.budget, spent: 0, evidenceRate: 0, taxRate: 0, documents: [{ name: '项目立项计划书', category: '立项', status: '待补', updatedAt: new Date().toISOString().slice(0, 10) }, { name: '科技查新报告', category: '立项', status: '待补', updatedAt: new Date().toISOString().slice(0, 10) }, { name: '内部立项审批文件', category: '立项', status: '待补', updatedAt: new Date().toISOString().slice(0, 10) }], costs: [] })
  Object.assign(createForm, { name: '', type: '新产品研发', owner: '', department: '', budget: 0 }); createVisible.value = false; ElMessage.success(`${id} 已登记，进入诊断规划阶段`)
}
</script>

<style scoped>
.research-workbench { min-width: 0; padding: 10px 0 28px; color: var(--zephyr-ink); font-variant-numeric: tabular-nums; }
.page-heading, .heading-actions, .section-title, .panel-heading, .filter-bar, .standard-row { display: flex; align-items: center; }
.page-heading { justify-content: space-between; gap: 20px; margin-bottom: 12px; }
.page-heading h1 { margin: 0; font-size: 20px; font-weight: 680; letter-spacing: 0; }
.page-heading p, .section-title p, .panel-heading p { margin: 4px 0 0; color: var(--zephyr-muted); font-size: 11px; }
.page-heading .demo-notice { color: #a3681c; font-weight: 650; }.year-label { color: #617178; font-size: 11px; white-space: nowrap; }
.heading-actions { gap: 8px; }
.metric-strip { display: grid; grid-template-columns: 1.35fr repeat(3, 1fr); margin-bottom: 10px; border: 1px solid var(--zephyr-border); background: var(--zephyr-surface); }
.metric { position: relative; min-height: 92px; padding: 14px 16px; border-right: 1px solid var(--zephyr-border); }
.metric:last-child { border-right: 0; }.metric-primary { background: var(--zephyr-primary-soft); }
.metric span, .metric small { display: block; color: var(--zephyr-muted); font-size: 10px; }.metric strong { display: block; margin-top: 5px; color: var(--zephyr-ink); font-size: 25px; line-height: 1; }.metric small { margin-top: 7px; }.metric strong.warning, .warning { color: var(--zephyr-warning) !important; }
.metric svg { position: absolute; right: 15px; bottom: 16px; width: 104px; height: 26px; overflow: visible; }.metric svg polyline { fill: none; stroke: var(--zephyr-primary); stroke-linecap: round; stroke-linejoin: round; stroke-width: 2; }
.stage-console, .data-panel { border: 1px solid var(--zephyr-border); background: #fff; }.stage-console { margin-bottom: 10px; padding: 13px 15px 11px; }.section-title { justify-content: space-between; }.section-title h2, .panel-heading h2 { margin: 0; color: #31444a; font-size: 13px; }.stage-progress-label { color: var(--zephyr-primary); font-size: 11px; font-weight: 650; }
.stage-track { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); margin: 12px 0 10px; }.stage-step { position: relative; display: grid; grid-template-columns: 28px minmax(0, 1fr); grid-template-rows: 16px 15px; gap: 0 8px; min-height: 45px; padding: 5px 10px; border: 0; border-right: 1px solid #dfe7e4; background: #f7f9f8; color: #7d898d; font: inherit; text-align: left; cursor: pointer; }.stage-step:last-child { border-right: 0; }.stage-step > span { display: grid; grid-row: 1 / 3; place-items: center; width: 27px; height: 27px; border-radius: 50%; background: #dfe6e4; color: #6e7d80; font-weight: 700; }.stage-step strong { color: #53656a; font-size: 11px; }.stage-step small { font-size: 9px; }.stage-step.done > span, .stage-step.active > span { background: var(--zephyr-primary); color: #fff; }.stage-step.active, .stage-step.selected { background: #e8f3ef; }.stage-step.selected { box-shadow: inset 0 -2px var(--zephyr-primary); }
.standard-row { min-width: 0; gap: 15px; overflow-x: auto; color: #647378; font-size: 10px; scrollbar-gutter: stable; }.standard-label { flex: 0 0 auto; font-weight: 700; }.standard-item { display: inline-flex; flex: 0 0 auto; align-items: center; gap: 5px; }.standard-item i, .status-text i, .boundary-note i, .reconciled i, .indicator-row em i { width: 6px; height: 6px; border-radius: 50%; background: var(--zephyr-primary); }
.domain-tabs { display: flex; min-height: 43px; margin-bottom: 8px; border: 1px solid var(--zephyr-border); background: #fff; overflow-x: auto; }.domain-tabs button { display: inline-flex; align-items: center; gap: 6px; min-width: 128px; min-height: 42px; justify-content: center; padding: 0 14px; border: 0; border-right: 1px solid #e5ebe9; background: #fff; color: #66767b; font: inherit; font-size: 11px; cursor: pointer; }.domain-tabs button.active { background: var(--zephyr-primary-soft); color: var(--zephyr-primary); font-weight: 680; box-shadow: inset 0 -2px var(--zephyr-primary); }.domain-tabs button span { min-width: 18px; padding: 1px 5px; border-radius: 8px; background: var(--zephyr-surface-muted); color: #6e7f83; font-size: 9px; text-align: center; }
.filter-bar { gap: 7px; min-height: 42px; margin-bottom: 8px; }.filter-bar .search-control { width: min(480px, 100%); }.filter-bar > .el-select { width: 130px; }.reset-filter { border: 0; background: transparent; color: var(--zephyr-primary); cursor: pointer; font-size: 11px; }
.project-grid, .two-column-content { display: grid; grid-template-columns: minmax(0, 1fr) 290px; gap: 10px; }.panel-heading { justify-content: space-between; gap: 12px; min-height: 53px; padding: 9px 12px; border-bottom: 1px solid #e5ebe9; }.panel-heading > strong { color: var(--zephyr-warning); font-size: 22px; }.boundary-note, .reconciled { display: inline-flex; align-items: center; gap: 6px; color: #5d716d; font-size: 10px; }.project-panel, .wide-panel { min-width: 0; }.project-name { display: flex; flex-direction: column; gap: 3px; }.project-name strong { color: #33474c; font-size: 12px; }.project-name small { color: #879498; font: 10px 'IBM Plex Mono', Consolas, monospace; }.status-text { display: inline-flex; align-items: center; gap: 6px; white-space: nowrap; }.status-text i.success { background: #3f8d73; }.status-text i.warning { background: #c58a32; }.status-text i.muted { background: #9aa6aa; }.amount-progress { display: grid; gap: 5px; color: #526469; font-size: 10px; }.amount-progress :deep(.el-progress-bar__outer), .hours-cell .bar-track { background: #e4eae8; }.amount-progress :deep(.el-progress-bar__inner) { background: var(--zephyr-primary); }.evidence-value { color: var(--zephyr-primary); font-size: 12px; }
.risk-row { display: grid; grid-template-columns: 7px minmax(0, 1fr) auto; align-items: center; gap: 9px; width: 100%; min-height: 63px; padding: 8px 12px; border: 0; border-bottom: 1px solid #edf1f0; background: #fff; color: inherit; font: inherit; text-align: left; cursor: pointer; }.risk-row:hover { background: #f3f8f6; }.risk-row > i { width: 7px; height: 7px; border-radius: 50%; }.risk-row > i.high { background: var(--zephyr-danger); }.risk-row > i.medium { background: var(--zephyr-warning); }.risk-row span { min-width: 0; }.risk-row strong, .risk-row small { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }.risk-row strong { color: #45585d; font-size: 10px; }.risk-row small { margin-top: 4px; color: #8a969a; font-size: 9px; }.risk-row em { color: #9b6b20; font-size: 9px; font-style: normal; }
.breakdown-panel { padding-bottom: 12px; }.breakdown-row { display: grid; grid-template-columns: minmax(0, 1fr) 38px; gap: 6px; padding: 10px 12px 0; }.breakdown-row > div:first-child { display: flex; grid-column: 1 / 3; justify-content: space-between; color: #607176; font-size: 10px; }.breakdown-row strong { color: #40545a; }.bar-track { height: 5px; overflow: hidden; border-radius: 3px; background: #e3e9e7; }.bar-track i { display: block; height: 100%; border-radius: inherit; background: var(--zephyr-primary); }.breakdown-row small { color: #7f8c90; font-size: 9px; text-align: right; }.validation-note { display: flex; gap: 8px; margin: 14px 12px 0; padding: 10px; background: #fff7e8; color: #786543; font-size: 9px; line-height: 1.45; }.validation-note .el-icon { flex: 0 0 auto; margin-top: 2px; color: var(--zephyr-warning); }.validation-note strong { display: block; font-size: 10px; }.trace-panel { margin-top: 10px; }.hours-cell { display: grid; gap: 5px; color: #56676d; font-size: 10px; }.hours-cell .bar-track { width: 100%; }.document-domain-strip, .collaboration-strip { display: grid; grid-template-columns: repeat(4, 1fr); margin-top: 10px; border: 1px solid var(--zephyr-border); background: #fff; }.document-domain-strip > div { display: grid; grid-template-columns: 30px minmax(0, 1fr) auto; align-items: center; gap: 8px; min-height: 66px; padding: 9px 12px; border-right: 1px solid #e5ebe9; }.document-domain-strip > div:last-child { border-right: 0; }.document-domain-strip .el-icon { font-size: 18px; color: var(--zephyr-primary); }.document-domain-strip strong, .document-domain-strip small { display: block; }.document-domain-strip strong { color: #40545a; font-size: 10px; }.document-domain-strip small { margin-top: 3px; color: #8a989c; font-size: 9px; }.document-domain-strip em { color: var(--zephyr-primary); font-size: 15px; font-style: normal; font-weight: 700; }
.indicator-list { padding: 2px 12px 10px; }.indicator-row { display: grid; grid-template-columns: minmax(0, 1fr) 95px 120px 70px; align-items: center; min-height: 47px; border-bottom: 1px solid #edf1f0; color: #506267; font-size: 10px; }.indicator-row strong { color: #34494e; font-size: 16px; }.indicator-row small { color: #889599; }.indicator-row em { display: inline-flex; align-items: center; gap: 5px; color: #43836f; font-style: normal; }.indicator-row em.attention { color: var(--zephyr-warning); }.indicator-row em.attention i { background: var(--zephyr-warning); }.archive-panel { padding-bottom: 12px; }.archive-row { display: grid; grid-template-columns: 24px minmax(0, 1fr) auto; align-items: center; gap: 8px; width: 100%; min-height: 58px; padding: 8px 12px; border: 0; border-bottom: 1px solid #edf1f0; background: #fff; color: inherit; font: inherit; text-align: left; cursor: pointer; }.archive-row:hover { background: #f3f8f6; }.archive-row .el-icon { color: var(--zephyr-primary); font-size: 17px; }.archive-row strong, .archive-row small { display: block; }.archive-row strong { color: #46595f; font-size: 10px; }.archive-row small { margin-top: 4px; color: #8a979b; font-size: 9px; }.archive-row em { color: var(--zephyr-primary); font-size: 13px; font-style: normal; font-weight: 700; }.archive-panel > .el-button { width: calc(100% - 24px); margin: 12px 12px 0; }.collaboration-strip { grid-template-columns: repeat(3, 1fr); }.collaboration-strip > div { min-height: 68px; padding: 10px 14px; border-right: 1px solid #e5ebe9; }.collaboration-strip > div:last-child { border-right: 0; }.collaboration-strip span { display: block; color: var(--zephyr-primary); font-size: 9px; font-weight: 700; }.collaboration-strip strong, .collaboration-strip small { display: block; }.collaboration-strip strong { margin-top: 4px; color: #40545a; font-size: 11px; }.collaboration-strip small { margin-top: 4px; color: #89969a; font-size: 9px; }
.drawer-summary { display: grid; grid-template-columns: repeat(4, 1fr); border: 1px solid var(--zephyr-border); background: var(--zephyr-surface-muted); }.drawer-summary > div { min-height: 68px; padding: 12px; border-right: 1px solid var(--zephyr-border); }.drawer-summary > div:last-child { border-right: 0; }.drawer-summary span, .drawer-summary strong { display: block; }.drawer-summary span { color: var(--zephyr-muted); font-size: 9px; }.drawer-summary strong { margin-top: 7px; color: #40545a; font-size: 13px; }.drawer-tabs { display: flex; margin-top: 12px; border-bottom: 1px solid var(--zephyr-border); }.drawer-tabs button { min-height: 38px; padding: 0 14px; border: 0; border-bottom: 2px solid transparent; background: transparent; color: #6c7a7f; cursor: pointer; }.drawer-tabs button.active { border-bottom-color: var(--zephyr-primary); color: var(--zephyr-primary); font-weight: 650; }.drawer-section { padding-top: 12px; }.document-list { border: 1px solid var(--zephyr-border); }.document-row { display: grid; grid-template-columns: 52px minmax(0, 1fr) 76px; align-items: center; gap: 10px; min-height: 58px; padding: 8px 12px; border-bottom: 1px solid #edf1f0; }.document-row:last-child { border-bottom: 0; }.document-category { display: grid; width: 42px; min-height: 24px; place-items: center; border-radius: 3px; background: #edf3f1; color: #536c65; font-size: 9px; }.document-row strong, .document-row small { display: block; }.document-row strong { color: #40545a; font-size: 11px; }.document-row small { margin-top: 4px; color: #8a979b; font-size: 9px; }.document-row button { border: 0; background: transparent; color: var(--zephyr-warning); cursor: pointer; font-size: 10px; }.document-row em { color: var(--zephyr-primary); font-size: 10px; font-style: normal; text-align: right; }.summary-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1px; padding: 1px; background: var(--zephyr-border); }.summary-grid > div { min-height: 78px; padding: 14px; background: #fff; }.summary-grid span, .summary-grid strong { display: block; }.summary-grid span { color: var(--zephyr-muted); font-size: 9px; }.summary-grid strong { margin-top: 9px; color: #40545a; font-size: 12px; }
@media (max-width: 980px) { .metric-strip { grid-template-columns: repeat(2, 1fr); }.metric:nth-child(2) { border-right: 0; }.metric:nth-child(-n+2) { border-bottom: 1px solid var(--zephyr-border); }.project-grid, .two-column-content { grid-template-columns: 1fr; }.action-panel, .breakdown-panel, .archive-panel { order: 2; }.document-domain-strip { grid-template-columns: repeat(2, 1fr); }.document-domain-strip > div:nth-child(2) { border-right: 0; }.document-domain-strip > div:nth-child(-n+2) { border-bottom: 1px solid #e5ebe9; } }
@media (max-width: 680px) { .page-heading { align-items: stretch; flex-direction: column; }.heading-actions { justify-content: space-between; }.metric { min-height: 86px; padding: 12px; }.metric strong { font-size: 21px; }.metric svg { display: none; }.stage-track { grid-template-columns: 1fr 1fr; gap: 1px; background: var(--zephyr-border); }.stage-step { border-right: 0; }.filter-bar { align-items: stretch; flex-direction: column; }.filter-bar > .el-select { width: 100%; }.domain-tabs button { min-width: 112px; }.document-domain-strip, .collaboration-strip { grid-template-columns: 1fr; }.document-domain-strip > div, .collaboration-strip > div { border-right: 0; border-bottom: 1px solid #e5ebe9; }.drawer-summary { grid-template-columns: 1fr 1fr; }.drawer-summary > div:nth-child(2) { border-right: 0; }.drawer-summary > div:nth-child(-n+2) { border-bottom: 1px solid var(--zephyr-border); }.summary-grid { grid-template-columns: 1fr; }.indicator-row { grid-template-columns: minmax(0, 1fr) 75px 62px; }.indicator-row small { display: none; } }
@media (prefers-reduced-motion: reduce) { .research-workbench * { scroll-behavior: auto !important; transition-duration: 0.01ms !important; } }
</style>
