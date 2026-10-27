<template>
  <div class="my-workbench">
    <header class="workbench-heading">
      <div>
        <div class="heading-overline">岗位协作 · {{ companyLabel }}</div>
        <h1>{{ query.scope === 'team' ? '岗位待办' : query.scope === 'created' ? '我发起的' : '我的工作台' }}</h1>
        <p class="heading-description">{{ identityName }}<span>/</span>{{ data?.identity.department || '当前部门' }} · {{ data?.identity.position || '当前岗位' }}<span>/</span>{{ displayDate }}</p>
      </div>
      <div class="heading-actions">
        <span class="last-updated" aria-live="polite">{{ loading ? '正在更新…' : error ? '更新失败' : lastUpdated }}</span>
        <el-button :icon="Refresh" :loading="loading" @click="load">刷新待办</el-button>
      </div>
    </header>

    <div v-if="data?.identity.is_switched" class="identity-notice" role="note"><el-icon><InfoFilled /></el-icon><span>当前为部门预览，按服务端有效身份展示队列。预览中不能认领或指派事项。</span></div>
    <div v-else-if="data?.identity.acceptance_mode" class="identity-notice" role="note"><el-icon><InfoFilled /></el-icon><span>当前为管理员测试身份，可查看已接入岗位。真实岗位的办理范围由服务端验证。</span></div>

    <section class="workbench-metrics" aria-label="当前分类的事项统计">
      <button v-for="metric in metrics" :key="metric.filter" type="button" class="metric-card" :class="[metric.className, { selected: query.due === metric.filter }]" :aria-pressed="query.due === metric.filter" @click="changeQuery({ due: metric.filter, page: 1 })">
        <span class="metric-content"><span class="metric-label">{{ metric.label }}</span><strong>{{ data && !error ? metric.value : '—' }}</strong><small>{{ metric.description }}</small></span>
        <el-icon class="metric-arrow"><component :is="metric.icon" /></el-icon>
      </button>
    </section>

    <section class="task-panel" aria-labelledby="task-panel-title" :aria-busy="loading">
      <div class="task-panel-heading"><h2 id="task-panel-title">工作事项</h2><span>原单办理成功后，刷新即可更新当前步骤</span></div>
      <nav class="scope-tabs" aria-label="待办分类">
        <button v-for="tab in scopes" :key="tab.key" type="button" :class="{ active: query.scope === tab.key }" :aria-current="query.scope === tab.key ? 'page' : undefined" @click="changeQuery({ scope: tab.key, due: 'all', page: 1 })">{{ tab.label }}<span>{{ data && !error ? data.counts[tab.key] : '—' }}</span></button>
      </nav>
      <form class="task-filters" role="search" aria-label="筛选工作事项" @submit.prevent="applySearch">
        <el-input v-model="searchText" :prefix-icon="Search" clearable maxlength="120" placeholder="搜索单据、客户、零件或事项" aria-label="搜索工作事项" @clear="applySearch" />
        <el-select :model-value="query.module || ''" aria-label="业务类型" placeholder="全部业务" @change="setModule"><el-option label="全部业务" value="" /><el-option v-for="module in modules" :key="module.key" :label="module.label" :value="module.key" /></el-select>
        <el-select :model-value="query.due" aria-label="事项状态与交期" @change="setDue"><el-option label="全部事项" value="all" /><el-option label="今日到期" value="today" /><el-option label="已逾期" value="overdue" /><el-option label="等待前序" value="blocked" /><el-option label="未设置交期" value="undated" /></el-select>
        <el-button native-type="submit">查询</el-button><el-button v-if="hasFilters" text @click="resetFilters">重置</el-button>
      </form>
      <p class="scope-description">{{ scopeDescription }}</p>
      <div v-if="actionNotice" class="action-notice" role="status">{{ actionNotice }}</div>
      <div v-if="actionError && !detailVisible" class="action-notice detail-error" role="alert">{{ actionError }}</div>
      <div v-if="error" class="workbench-state error-state" role="alert"><el-icon><WarningFilled /></el-icon><h3>工作事项加载失败</h3><p>{{ error }}</p><el-button :loading="loading" @click="load">重新加载</el-button></div>
      <div v-else v-loading="loading" class="task-table-region">
        <table class="task-table" aria-label="工作事项列表">
          <thead><tr><th scope="col">业务单据 / 客户</th><th scope="col">当前事项 / 交接</th><th scope="col">主责 / 受理人</th><th scope="col">期限</th><th scope="col">操作</th></tr></thead>
          <tbody><tr v-for="task in data?.items || []" :key="task.key" class="task-row" :data-task-key="task.key">
            <td data-label="业务单据"><span class="module-label">{{ moduleLabel(task.module) }}<span v-if="task.company"> · {{ task.company === 'gaibo' ? '盖博' : '天越' }}</span></span><router-link class="document-link" :to="task.route">{{ task.document_no }}</router-link><small class="customer-name">{{ task.customer || '未关联客户' }}</small></td>
            <td data-label="当前事项" class="task-summary"><div class="task-title"><strong>{{ task.title }}</strong><span v-if="task.urgent" class="urgency-badge">加急</span></div><small>{{ task.summary }}</small><span v-if="task.blocked_reason" class="blocked-note"><el-icon><Clock /></el-icon>等待前序 · {{ task.blocked_reason }}</span><small v-else-if="task.next_role" class="handoff-note">完成后交给 {{ task.next_role }}</small></td>
            <td data-label="主责与受理人"><span class="owner-department">{{ task.owner_department || task.role }}</span><span class="role-name">{{ task.owner_role || task.role }}</span><small class="assignee-name" :class="{ unassigned: !task.assignee_id }">{{ task.assignee_name || (task.scope === 'created' ? '按原单跟进' : task.scope === 'mine' ? '本人事项' : '岗位共享，未指派') }}</small><small v-if="task.source_assignee" class="source-owner">原单执行负责人：{{ task.source_assignee }}</small></td>
            <td data-label="期限"><span class="due-date" :class="dueClass(task)">{{ task.due_date || '未设置交期' }}</span><small v-if="task.due_date" class="due-description" :class="dueClass(task)">{{ dueDescription(task) }}</small><small class="update-time">更新 {{ formatTime(task.updated_at) }}</small></td>
            <td data-label="操作" class="action-column"><button type="button" class="detail-action" :aria-label="'查看事项与交接：' + task.document_no + '，' + task.title" @click="openDetail(task)">事项与交接</button><router-link class="task-action" :to="task.route" :aria-label="task.action_label + '：' + task.document_no + '，' + task.title">{{ task.action_label }}<el-icon><ArrowRight /></el-icon></router-link></td>
          </tr></tbody>
        </table>
        <div v-if="!loading && !data?.items.length" class="workbench-state empty-state" role="status">
          <span class="empty-icon"><el-icon><DocumentChecked /></el-icon></span>
          <h3>{{ hasFilters ? '没有符合筛选条件的事项' : query.scope === 'mine' ? '当前没有个人待办' : query.scope === 'team' ? '已接入岗位暂无待处理事项' : '暂无进行中的发起记录' }}</h3>
          <p>{{ hasFilters ? '调整关键词、业务类型或事项状态后重新查询。' : query.scope === 'mine' ? '在岗位待办中认领可办理事项后，会同步显示在这里。' : '接入范围见下方说明；未接入模块不计入当前数量。' }}</p>
          <el-button v-if="hasFilters" @click="resetFilters">清除筛选</el-button><el-button v-else-if="query.scope === 'mine'" @click="changeQuery({ scope: 'team', page: 1 })">查看岗位待办</el-button>
        </div>
        <div v-if="loading && !data" class="initial-loading" role="status">正在读取工作事项…</div>
        <footer class="table-footer"><span>共 {{ data && !error ? data.total : '—' }} 项<span class="footer-note"> · 等待前序单独统计</span></span><el-pagination :current-page="data?.page || query.page" :page-size="query.page_size" :total="data && !error ? data.total : 0" :page-sizes="[15, 30, 50]" :disabled="loading || !!error" layout="sizes, prev, pager, next" @current-change="setPage" @size-change="setPageSize" /></footer>
      </div>
    </section>

    <details v-if="data && !error" class="coverage-panel">
      <summary>业务接入范围 <span>{{ activeCoverage.length }} 类已接入 · {{ inactiveCoverage.length }} 类未接入</span></summary>
      <p>不良品按当前公司读取；生产、发货和询报价沿用原业务的共享范围，不按公司筛分。此处展示已接入流程，未接入不代表没有工作。</p>
      <ul><li v-for="entry in data.coverage" :key="entry.key"><span class="coverage-state" :class="{ connected: entry.status === 'active' }">{{ entry.status === 'active' ? '已接入' : '未接入' }}</span><strong>{{ entry.label }}</strong><span>{{ entry.description }}</span></li></ul>
    </details>

    <el-drawer v-model="detailVisible" title="事项与交接" size="min(560px, 100vw)" :before-close="closeDetail" class="handoff-drawer">
      <template v-if="selectedTask">
        <span class="module-label">{{ moduleLabel(selectedTask.module) }} · {{ selectedTask.document_no }}</span>
        <h2 class="detail-title">{{ selectedTask.title }}</h2><p class="detail-summary">{{ selectedTask.summary }}</p>
        <dl class="task-facts"><div><dt>主责部门</dt><dd>{{ selectedTask.owner_department || selectedTask.role }}</dd></div><div><dt>处理岗位</dt><dd>{{ selectedTask.owner_role || selectedTask.role }}</dd></div><div><dt>当前受理人</dt><dd>{{ selectedTask.assignee_name || (selectedTask.scope === 'team' ? '岗位共享，未指派' : '原单归属人') }}</dd></div><div><dt>要求完成</dt><dd>{{ selectedTask.due_date || '原单未设置交期' }}</dd></div><div v-if="selectedTask.source_assignee"><dt>原单执行负责人</dt><dd>{{ selectedTask.source_assignee }}</dd></div></dl>
        <p v-if="selectedTask.source_assignee" class="detail-summary">原单执行负责人：{{ selectedTask.source_assignee }}</p>
        <section v-if="selectedTask.blocked_reason" class="detail-blocked"><h3>等待前序</h3><p>{{ selectedTask.blocked_reason }}</p></section>
        <section class="detail-section"><h3>本步完成条件</h3><ul v-if="selectedTask.completion_requirements.length"><li v-for="requirement in selectedTask.completion_requirements" :key="requirement">{{ requirement }}</li></ul><p v-else>请在原业务单据中核对当前步骤要求。</p></section>
        <section class="detail-section next-owner"><h3>下一接收岗位</h3><p>{{ selectedTask.next_role || '按原单后续流程交接' }}</p><small>认领与指派只确定受理人。办理结果以原业务单据为准。</small></section>
        <section v-if="selectedTask.can_assign" class="detail-section assignment-form"><h3>指派处理人</h3><el-button v-if="!assignmentOpen" :loading="loadingAssignees" @click="openAssignment">选择处理人</el-button><template v-else><el-select v-model="assigneeId" aria-label="指派处理人" clearable placeholder="选择同岗位可办理人员"><el-option v-for="person in assignees" :key="person.id" :value="person.id" :label="person.name + ' · ' + (person.position || person.department)" /></el-select><p class="assignment-help">清空处理人后保存，可恢复为岗位共享待认领。</p><el-button :loading="mutating" :disabled="loadingAssignees" @click="assignTask">保存指派</el-button></template></section>
        <div v-if="actionError" class="detail-error" role="alert">{{ actionError }}</div>
      </template>
      <template #footer><div class="detail-footer"><el-button :disabled="mutating" @click="dismissDetail">返回列表</el-button><template v-if="selectedTask"><el-button v-if="selectedTask.can_release" :loading="mutating" @click="mutateAssignment('release')">释放回岗位</el-button><el-button v-if="selectedTask.can_claim" type="primary" :loading="mutating" @click="mutateAssignment('claim')">认领事项</el-button><el-button v-else type="primary" :disabled="mutating" @click="goToSource">进入原单</el-button></template></div></template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowRight, Calendar, Clock, DocumentChecked, InfoFilled, List, Refresh, Search, WarningFilled } from '@element-plus/icons-vue'
import { workbenchApi, type DueFilter, type TaskAssignee, type TaskAssignmentInput, type TaskModule, type TaskScope, type WorkbenchPage, type WorkbenchQuery, type WorkbenchTask } from '@/api/workbench'
import { useUserStore } from '@/stores/user'
import { useCompanyStore } from '@/stores/company'
import { usePermissionStore } from '@/stores/permission'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const companyStore = useCompanyStore()
const permissionStore = usePermissionStore()
const data = ref<WorkbenchPage | null>(null)
const loading = ref(false)
const error = ref('')
const searchText = ref('')
const actionNotice = ref('')
const detailVisible = ref(false)
const selectedTask = ref<WorkbenchTask | null>(null)
const actionError = ref('')
const mutating = ref(false)
const loadingAssignees = ref(false)
const assignmentOpen = ref(false)
const assignees = ref<TaskAssignee[]>([])
const assigneeId = ref<number | undefined>()
const scopes: { key: TaskScope; label: string }[] = [{ key: 'mine', label: '我的待办' }, { key: 'team', label: '岗位待办' }, { key: 'created', label: '我发起的' }]
const modules: { key: TaskModule; label: string }[] = [{ key: 'inquiry', label: '询价评审' }, { key: 'quote', label: '报价' }, { key: 'production', label: '生产计划' }, { key: 'shipping', label: '发货订单' }, { key: 'nonconforming', label: '不良品处置' }]
const moduleLabel = (module: TaskModule) => modules.find(item => item.key === module)?.label || module
const query = computed<WorkbenchQuery>(() => ({
  scope: scopes.some(item => item.key === route.query.scope) ? route.query.scope as TaskScope : 'mine',
  module: modules.some(item => item.key === route.query.module) ? route.query.module as TaskModule : undefined,
  search: typeof route.query.search === 'string' ? route.query.search.slice(0, 120) : '',
  due: ['today', 'overdue', 'undated', 'blocked'].includes(String(route.query.due)) ? route.query.due as DueFilter : 'all',
  page: Math.max(1, Math.floor(Number(route.query.page) || 1)),
  page_size: [15, 30, 50].includes(Number(route.query.page_size)) ? Number(route.query.page_size) : 15,
  company: companyStore.selectedCompany,
}))
const companyLabel = computed(() => companyStore.selectedCompany === 'gaibo' ? '盖博' : '天越')
const scopeDescription = computed(() => ({
  mine: '本人原单事项与已认领、已指派给本人的任务。岗位共享事项可先在岗位待办中认领。',
  team: '按服务端有效岗位展示共享队列，受理人和等待前序原因随原单更新。进入原单办理。',
  created: '跟进本人发起流程的当前步骤与责任岗位；办理权限仍由原业务服务验证。',
}[query.value.scope]))
const identityName = computed(() => data.value?.identity.name || userStore.userInfo?.real_name || '当前用户')
const displayDate = computed(() => new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Shanghai', month: 'long', day: 'numeric', weekday: 'long' }).format(data.value ? new Date(data.value.today + 'T12:00:00+08:00') : new Date()))
const lastUpdated = computed(() => data.value ? new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Shanghai', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }).format(new Date(data.value.generated_at)) + ' 已更新' : '')
const metrics = computed(() => [
  { label: query.value.scope === 'created' ? '可推进事项' : '待处理事项', value: data.value?.stats.pending, filter: 'all' as DueFilter, icon: List, className: 'pending', description: '当前可办理，不含等待前序' },
  { label: '今日到期', value: data.value?.stats.today, filter: 'today' as DueFilter, icon: Calendar, className: 'today', description: '可办理事项 · 今天需要关注' },
  { label: '已逾期', value: data.value?.stats.overdue, filter: 'overdue' as DueFilter, icon: Clock, className: 'overdue', description: '可办理事项 · 优先处理' },
  { label: '等待前序', value: data.value?.stats.blocked, filter: 'blocked' as DueFilter, icon: InfoFilled, className: 'blocked', description: '核对阻塞原因与责任岗位' },
])
const activeCoverage = computed(() => data.value?.coverage.filter(item => item.status === 'active') || [])
const inactiveCoverage = computed(() => data.value?.coverage.filter(item => item.status === 'not_connected') || [])
const hasFilters = computed(() => !!query.value.search || !!query.value.module || query.value.due !== 'all')
let requestSequence = 0
let detailSequence = 0
let assigneeSequence = 0
let mutationSequence = 0
const contextKey = () => JSON.stringify([companyStore.selectedCompany, permissionStore.contextSwitch, userStore.userInfo?.id])
const invalidateDetail = () => {
  ++detailSequence
  ++assigneeSequence
  ++mutationSequence
  selectedTask.value = null
  detailVisible.value = false
  actionError.value = ''
  actionNotice.value = ''
  assignmentOpen.value = false
  loadingAssignees.value = false
  mutating.value = false
}
const load = async () => {
  const sequence = ++requestSequence
  loading.value = true
  error.value = ''
  try {
    const response = await workbenchApi.list(query.value)
    if (sequence !== requestSequence) return
    data.value = response
    if (selectedTask.value) {
      const updated = response.items.find(item => item.key === selectedTask.value?.key)
      if (updated) selectedTask.value = updated
      else { selectedTask.value = null; detailVisible.value = false }
    }
  } catch (reason) {
    if (sequence === requestSequence) error.value = reason instanceof Error ? reason.message : '请稍后重试。'
  } finally { if (sequence === requestSequence) loading.value = false }
}
const changeQuery = (changes: Partial<WorkbenchQuery>) => {
  const next = { ...query.value, ...changes }
  actionError.value = ''
  actionNotice.value = ''
  void router.push({ path: '/workbench', query: { view: 'tasks', scope: next.scope, module: next.module || undefined, search: next.search || undefined, due: next.due === 'all' ? undefined : next.due, page: next.page > 1 ? String(next.page) : undefined, page_size: next.page_size !== 15 ? String(next.page_size) : undefined } })
}
const applySearch = () => changeQuery({ search: searchText.value.trim(), page: 1 })
const setModule = (module: TaskModule | '') => changeQuery({ module: module || undefined, page: 1 })
const setDue = (due: DueFilter) => changeQuery({ due, page: 1 })
const setPage = (page: number) => changeQuery({ page })
const setPageSize = (page_size: number) => changeQuery({ page_size, page: 1 })
const resetFilters = () => { searchText.value = ''; changeQuery({ search: '', module: undefined, due: 'all', page: 1 }) }
const dueClass = (task: WorkbenchTask) => task.due_date && data.value ? task.due_date < data.value.today ? 'is-overdue' : task.due_date === data.value.today ? 'is-today' : '' : ''
const dueDescription = (task: WorkbenchTask) => {
  if (!task.due_date || !data.value) return ''
  const days = Math.round((Date.parse(task.due_date + 'T00:00:00+08:00') - Date.parse(data.value.today + 'T00:00:00+08:00')) / 86400000)
  return days < 0 ? '已逾期 ' + -days + ' 天' : days === 0 ? '今天到期' : '还有 ' + days + ' 天'
}
const formatTime = (value: string | null) => {
  if (!value) return '—'
  const timestamp = /(?:Z|[+-]\d\d:\d\d)$/.test(value) ? value : value + 'Z'
  return new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Shanghai', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false }).format(new Date(timestamp))
}
const openDetail = (task: WorkbenchTask) => {
  ++detailSequence
  ++assigneeSequence
  loadingAssignees.value = false
  selectedTask.value = task
  actionError.value = ''
  assignmentOpen.value = false
  assignees.value = []
  detailVisible.value = true
}
const dismissDetail = () => { if (!mutating.value) { actionError.value = ''; detailVisible.value = false } }
const closeDetail = (done: () => void) => { if (!mutating.value) { actionError.value = ''; done() } }
const assignmentInput = (task: WorkbenchTask): TaskAssignmentInput => ({ task_key: task.key, source_revision: task.source_revision, expected_version: task.assignment_version, company: task.company || companyStore.selectedCompany })
const openAssignment = async () => {
  const task = selectedTask.value
  if (!task || !task.can_assign) return
  const sequence = ++assigneeSequence
  const detail = detailSequence
  const context = contextKey()
  const isCurrent = () => sequence === assigneeSequence && detail === detailSequence && context === contextKey() && selectedTask.value?.key === task.key && detailVisible.value
  actionError.value = ''
  loadingAssignees.value = true
  try {
    const response = await workbenchApi.assignees(task.key, task.company || companyStore.selectedCompany)
    if (!isCurrent()) return
    assignees.value = response.items
    assigneeId.value = task.assignee_id || undefined
    assignmentOpen.value = true
  } catch (reason) { if (isCurrent()) actionError.value = reason instanceof Error ? reason.message : '可指派人员加载失败。' }
  finally { if (sequence === assigneeSequence) loadingAssignees.value = false }
}
const mutateAssignment = async (action: 'claim' | 'release' | 'assign') => {
  const task = selectedTask.value
  if (!task || mutating.value) return
  const sequence = ++mutationSequence
  const detail = detailSequence
  const context = contextKey()
  const isCurrent = () => sequence === mutationSequence && context === contextKey()
  mutating.value = true
  actionError.value = ''
  actionNotice.value = ''
  try {
    const input = assignmentInput(task)
    if (action === 'assign') await workbenchApi.assign({ ...input, assignee_id: assigneeId.value ?? null })
    else await workbenchApi[action](input)
    if (!isCurrent()) return
    actionNotice.value = action === 'claim' ? '已认领，事项已同步到我的待办。' : action === 'release' ? '已释放，事项恢复为岗位共享待认领。' : '已保存指派，受理人的个人待办同步更新。'
    assignmentOpen.value = false
    await load()
  } catch (reason) {
    if (!isCurrent()) return
    if (detail === detailSequence && selectedTask.value?.key === task.key) actionError.value = reason instanceof Error ? reason.message : '操作失败，请刷新后重试。'
    await load()
  } finally { if (sequence === mutationSequence) mutating.value = false }
}
const assignTask = () => mutateAssignment('assign')
const goToSource = () => { if (selectedTask.value) void router.push(selectedTask.value.route) }
watch(query, (next, previous) => {
  if (previous && next.company !== previous.company) { data.value = null; invalidateDetail() }
  searchText.value = next.search
  void load()
}, { immediate: true })
watch(() => permissionStore.contextSwitch, () => { data.value = null; invalidateDetail(); void load() })
watch(detailVisible, visible => { if (!visible) { ++detailSequence; ++assigneeSequence; loadingAssignees.value = false } })
onBeforeUnmount(() => { ++requestSequence; invalidateDetail() })
</script>

<style scoped>

.my-workbench { min-width: 0; padding-top: 25px; color: var(--zephyr-text); }
.workbench-heading { display: flex; align-items: center; justify-content: space-between; gap: 24px; margin-bottom: 20px; }
.heading-overline { display: flex; align-items: center; gap: 7px; color: var(--zephyr-muted); font-size: 12px; }
.live-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--zephyr-primary); }
h1 { margin: 7px 0; color: var(--zephyr-ink); font-size: 26px; font-weight: 650; letter-spacing: -.5px; }
.heading-description { margin: 0; color: var(--zephyr-muted); font-size: 13px; }.heading-description > span { margin: 0 11px; color: var(--zephyr-border); }
.heading-actions { display: flex; align-items: center; flex-shrink: 0; gap: 12px; }.heading-actions .el-button + .el-button { margin-left: 0; }
.last-updated { margin-right: 4px; color: var(--zephyr-muted); font-size: 12px; font-variant-numeric: tabular-nums; }
.identity-notice { display: flex; align-items: center; gap: 8px; margin-bottom: 18px; padding: 10px 13px; border: 1px solid var(--zephyr-primary-border); border-radius: 6px; background: var(--zephyr-primary-soft); color: var(--zephyr-primary-hover); font-size: 12px; line-height: 1.6; }.identity-notice .el-icon { flex-shrink: 0; font-size: 15px; }
.workbench-metrics { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; margin-bottom: 22px; }
.metric-card { position: relative; display: flex; align-items: flex-start; gap: 16px; min-height: 126px; padding: 21px 22px; border: 1px solid var(--zephyr-border); border-radius: 8px; background: var(--zephyr-surface); color: var(--zephyr-text); font: inherit; text-align: left; cursor: pointer; transition: border-color .15s, background-color .15s; }.metric-card:hover, .metric-card.selected { border-color: var(--zephyr-primary); background: #fcfcff; }
.metric-icon { display: grid; width: 40px; height: 40px; flex-shrink: 0; place-items: center; border-radius: 9px; background: var(--zephyr-primary-soft); color: var(--zephyr-primary); font-size: 20px; }.today .metric-icon { background: #fff5e5; color: #936012; }.overdue .metric-icon { background: #fff0f0; color: #b33a43; }
.metric-content { display: flex; flex-direction: column; align-items: flex-start; }.metric-label { color: var(--zephyr-muted); font-size: 13px; }.metric-content strong { margin-top: 2px; color: var(--zephyr-ink); font-size: 30px; font-weight: 650; font-variant-numeric: tabular-nums; line-height: 1.3; }.overdue .metric-content strong { color: #b33a43; }.metric-content small { margin-top: 5px; color: var(--zephyr-muted); font-size: 12px; }.metric-arrow { position: absolute; right: 18px; top: 23px; color: var(--zephyr-subtle); font-size: 16px; }
.task-panel { overflow: hidden; border: 1px solid var(--zephyr-border); border-radius: 8px; background: var(--zephyr-surface); }.task-panel-heading { display: flex; align-items: center; justify-content: space-between; gap: 18px; padding: 18px 22px 10px; }h2 { margin: 0; color: var(--zephyr-ink); font-size: 16px; font-weight: 650; }.task-panel-heading > span { color: var(--zephyr-muted); font-size: 12px; }
.scope-tabs { display: flex; gap: 24px; padding: 0 22px; border-bottom: 1px solid var(--zephyr-border-soft); }.scope-tabs button { display: flex; align-items: center; gap: 8px; min-height: 48px; padding: 0 2px; border: 0; border-bottom: 2px solid transparent; background: transparent; color: var(--zephyr-muted); font: inherit; font-size: 14px; cursor: pointer; }.scope-tabs button:hover { color: var(--zephyr-primary); }.scope-tabs button.active { border-bottom-color: var(--zephyr-primary); color: var(--zephyr-primary-hover); font-weight: 600; }.scope-tabs button span { min-width: 20px; padding: 1px 6px; border-radius: 4px; background: var(--zephyr-surface-muted); color: var(--zephyr-muted); font-size: 11px; font-weight: 500; text-align: center; }.scope-tabs button.active span { background: var(--zephyr-primary-soft); color: var(--zephyr-primary-hover); }
.task-filters { display: flex; align-items: center; gap: 10px; padding: 18px 22px 12px; }.task-filters > .el-input { width: 310px; }.task-filters > .el-select { width: 145px; }.task-filters .el-button + .el-button { margin-left: 0; }.scope-description { display: flex; align-items: center; gap: 6px; padding: 0 22px 15px; color: var(--zephyr-muted); font-size: 12px; }
.task-table-region { min-height: 235px; }.task-table { width: 100%; border-collapse: collapse; table-layout: fixed; text-align: left; }.task-table th { height: 40px; padding: 0 20px; border-top: 1px solid var(--zephyr-border-soft); border-bottom: 1px solid var(--zephyr-border-soft); background: var(--zephyr-surface-muted); color: var(--zephyr-muted); font-size: 12px; font-weight: 500; }.task-table th:first-child { width: 24%; }.task-table th:nth-child(2) { width: 31%; }.task-table th:nth-child(3) { width: 11%; }.task-table th:nth-child(4) { width: 12%; }.task-table th:nth-child(5) { width: 12%; }.task-table th:last-child { width: 10%; }.task-table td { padding: 13px 20px; border-bottom: 1px solid var(--zephyr-border-soft); font-size: 13px; vertical-align: middle; overflow-wrap: anywhere; }.task-row:hover { background: #fafbfe; }
.module-label { display: block; margin-bottom: 4px; color: var(--zephyr-muted); font-size: 11px; }.document-link { display: block; color: var(--zephyr-ink); font-weight: 600; text-decoration: none; }.document-link:hover { color: var(--zephyr-primary); text-decoration: underline; }.customer-name { display: block; margin-top: 4px; color: var(--zephyr-muted); font-size: 12px; }.task-title { display: flex; align-items: center; gap: 8px; }.task-title strong { color: var(--zephyr-ink); font-size: 14px; font-weight: 550; }.task-summary small { display: block; margin-top: 7px; color: var(--zephyr-muted); font-size: 12px; line-height: 1.6; }
.urgency-badge { padding: 1px 5px; border: 1px solid #efc6c8; border-radius: 3px; background: #fff1f2; color: #aa303c; font-size: 11px; }.role-badge { display: inline-block; padding: 3px 7px; border: 1px solid var(--zephyr-border); border-radius: 4px; color: var(--zephyr-text); font-size: 12px; white-space: nowrap; }.due-date { font-size: 12px; font-variant-numeric: tabular-nums; }.due-description { display: block; margin-top: 5px; color: var(--zephyr-muted); font-size: 11px; }.is-overdue { color: #b33a43; }.is-today { color: #936012; }.update-time { color: var(--zephyr-muted); font-size: 12px; font-variant-numeric: tabular-nums; }.action-column { text-align: right; }.task-action { display: inline-flex; align-items: center; justify-content: flex-end; gap: 4px; min-height: 32px; color: var(--zephyr-primary-hover); font-size: 12px; text-decoration: none; white-space: nowrap; }.task-action:hover { text-decoration: underline; }
.table-footer { display: flex; align-items: center; justify-content: space-between; gap: 16px; min-height: 66px; padding: 0 22px; color: var(--zephyr-muted); font-size: 12px; }.workbench-state { display: flex; min-height: 250px; flex-direction: column; align-items: center; justify-content: center; padding: 26px; text-align: center; }.workbench-state h3 { margin: 12px 0 4px; color: var(--zephyr-text); font-size: 15px; font-weight: 550; }.workbench-state p { margin: 3px 0 15px; color: var(--zephyr-muted); font-size: 13px; }.empty-icon { display: grid; width: 46px; height: 46px; place-items: center; border-radius: 12px; background: var(--zephyr-primary-soft); color: var(--zephyr-primary); font-size: 24px; }.error-state > .el-icon { color: var(--zephyr-danger); font-size: 28px; }.initial-loading { display: grid; min-height: 200px; place-items: center; color: var(--zephyr-muted); font-size: 13px; }.workbench-footnote { margin: 14px 0 0; color: var(--zephyr-muted); font-size: 12px; line-height: 1.8; }button:focus-visible, a:focus-visible { outline: 2px solid var(--zephyr-primary); outline-offset: 3px; }
@media (min-width: 768px) and (max-width: 1200px) { .heading-actions { flex-wrap: wrap; justify-content: flex-end; }.last-updated { width: 100%; text-align: right; }.metric-card { padding: 18px 16px; gap: 12px; }.metric-content small span { display: none; }.task-table td, .task-table th { padding-right: 12px; padding-left: 12px; }.task-table th:first-child { width: 23%; }.task-table th:nth-child(2) { width: 29%; }.task-table th:nth-child(3) { width: 12%; }.task-table th:nth-child(4) { width: 13%; }.task-table th:nth-child(5) { width: 12%; }.task-table th:last-child { width: 11%; }.footer-note { display: none; } }
@media (prefers-reduced-motion: reduce) { .metric-card { transition: none; } }

.workbench-metrics{grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin-bottom:18px}.metric-card{min-height:106px;padding:16px 18px}.metric-card.pending{background:var(--zephyr-primary-soft)}.metric-arrow{right:16px;top:18px}.metric-content small{font-size:11px}.metric-content strong{font-size:28px}
.scope-description{margin:0;line-height:1.7}.action-notice{margin:0 22px 14px;padding:8px 12px;background:var(--zephyr-primary-soft);color:var(--zephyr-primary-hover);font-size:12px;line-height:1.6}
.task-table th:first-child{width:22%}.task-table th:nth-child(2){width:31%}.task-table th:nth-child(3){width:19%}.task-table th:nth-child(4){width:15%}.task-table th:last-child{width:13%}.task-table td{padding:14px 18px}
.task-row:hover{background:var(--zephyr-surface-muted);box-shadow:inset 3px 0 var(--zephyr-primary)}
.owner-department,.role-name,.assignee-name{display:block;line-height:1.7}.owner-department{font-size:12px;color:var(--zephyr-muted)}.role-name{font-size:13px;color:var(--zephyr-text)}.assignee-name{margin-top:3px;color:var(--zephyr-primary-hover);font-size:12px}.assignee-name.unassigned{color:var(--zephyr-muted)}
.source-owner{display:block;margin-top:5px;font-size:11px;line-height:1.7;color:var(--zephyr-muted)}
.blocked-note{display:flex;align-items:flex-start;gap:5px;margin-top:7px;color:#936012;font-size:12px;line-height:1.6}.blocked-note .el-icon{margin-top:3px;flex-shrink:0}.handoff-note{color:var(--zephyr-subtle)}.update-time{display:block;margin-top:7px;font-size:11px}.detail-action{display:block;margin-left:auto;min-height:32px;padding:0;border:0;background:none;font:inherit;font-size:12px;color:var(--zephyr-text);cursor:pointer}.detail-action:hover{color:var(--zephyr-primary-hover)}
.coverage-panel{margin-top:18px;padding:14px 18px;border:1px solid var(--zephyr-border);border-radius:8px;background:var(--zephyr-surface);font-size:12px;color:var(--zephyr-muted)}.coverage-panel summary{min-height:24px;cursor:pointer;color:var(--zephyr-text)}.coverage-panel summary>span{margin-left:12px;color:var(--zephyr-muted)}.coverage-panel p{line-height:1.8}.coverage-panel ul{display:grid;grid-template-columns:1fr 1fr;gap:12px 24px;padding:0;list-style:none}.coverage-panel li{display:grid;grid-template-columns:48px auto;gap:4px 10px;align-items:start;line-height:1.7}.coverage-panel li>span:last-child{grid-column:2}.coverage-panel strong{font-weight:550;color:var(--zephyr-text)}.coverage-state{color:var(--zephyr-subtle)}.coverage-state.connected{color:var(--zephyr-primary-hover)}
.detail-title{margin:8px 0 12px;font-size:23px}.detail-summary{margin:0 0 22px;color:var(--zephyr-muted);font-size:13px;line-height:1.8}.task-facts{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin:0 0 24px}.task-facts dt{margin-bottom:5px;color:var(--zephyr-muted);font-size:12px}.task-facts dd{margin:0;color:var(--zephyr-text);font-size:14px;overflow-wrap:anywhere}.detail-section{margin-top:22px;padding-top:20px;border-top:1px solid var(--zephyr-border-soft)}.detail-section h3,.detail-blocked h3{margin:0 0 10px;color:var(--zephyr-ink);font-size:14px}.detail-section ul{padding-left:18px;line-height:1.9;font-size:13px;color:var(--zephyr-text)}.detail-section p,.detail-blocked p{font-size:13px;line-height:1.8;margin:0}.detail-section small{display:block;margin-top:8px;color:var(--zephyr-muted);font-size:12px;line-height:1.7}.detail-blocked{padding:14px;background:#fff7e8;border:1px solid #ead8b7;border-radius:6px;color:#80571a}.detail-footer{display:flex;justify-content:flex-end;flex-wrap:wrap;gap:8px}.detail-footer .el-button+.el-button{margin-left:0}.assignment-form .el-select{width:100%}.assignment-help{margin:8px 0!important;color:var(--zephyr-muted);font-size:12px!important}.detail-error{margin-top:18px;padding:10px 12px;border:1px solid #efc6c8;border-radius:6px;background:#fff1f2;color:#aa303c;font-size:13px;line-height:1.8}
@media(max-width:900px){.workbench-metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.task-filters{flex-wrap:wrap}.task-filters>.el-input{width:100%}.task-filters>.el-select{flex:1;min-width:130px}.task-panel-heading>span{display:none}.coverage-panel ul{grid-template-columns:1fr}.heading-description>span{margin:0 5px}}
@media(max-width:600px){.my-workbench{padding-top:18px}.workbench-heading{align-items:flex-start;gap:12px;margin-bottom:16px}.workbench-heading h1{font-size:23px}.heading-description{font-size:11px;line-height:1.8}.heading-actions{flex-direction:column;align-items:flex-end;gap:8px}.last-updated{margin:0;font-size:10px}.workbench-metrics{gap:8px}.metric-card{min-height:96px;padding:13px 12px}.metric-content strong{font-size:26px}.metric-content small{font-size:10px;line-height:1.6}.metric-arrow{right:12px;top:15px}.scope-tabs{gap:18px;padding:0 14px}.scope-tabs button{font-size:13px}.task-panel-heading{padding:16px 14px 8px}.task-filters{padding:14px;gap:8px}.task-filters>.el-select{min-width:110px}.scope-description{padding:0 14px 14px}.action-notice{margin:0 14px 14px}.task-table,.task-table tbody,.task-table tr,.task-table td{display:block;width:auto}.task-table thead{display:none}.task-table tr{padding:14px;border-top:1px solid var(--zephyr-border-soft)}.task-table td{padding:5px 0;border:0}.task-table td:before{content:attr(data-label);display:block;margin-bottom:4px;font-size:10px;color:var(--zephyr-subtle)}.task-table td.action-column{display:flex;align-items:center;gap:18px;text-align:left}.task-table td.action-column:before{display:none}.detail-action{margin:0}.task-table td:nth-child(3),.task-table td:nth-child(4){display:inline-block;width:50%;vertical-align:top}.table-footer{flex-direction:column;gap:10px;align-items:flex-start;padding:16px 14px}.footer-note{display:none}.workbench-state{min-height:200px;padding:18px}.coverage-panel{padding:12px 14px}.coverage-panel summary>span{display:block;margin:5px 0 0}.task-facts{gap:14px}.detail-footer{justify-content:flex-start}}
</style>
