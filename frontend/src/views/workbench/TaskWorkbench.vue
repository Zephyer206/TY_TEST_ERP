<template>
  <div class="my-workbench">
    <header class="workbench-heading">
      <div>
        <div class="heading-overline"><span class="live-dot" />个人工作空间</div>
        <h1>我的工作台</h1>
        <p class="heading-description">{{ identityName }}<span>/</span>{{ data?.identity.position || '当前账号' }}<span>/</span>{{ displayDate }}</p>
      </div>
      <div class="heading-actions">
        <span class="last-updated" aria-live="polite">{{ loading ? '正在更新…' : error ? '更新失败' : lastUpdated }}</span>
        <el-button :icon="Box" @click="router.push('/parts')">零件档案</el-button>
        <el-button :icon="Refresh" :loading="loading" type="primary" @click="load">刷新待办</el-button>
      </div>
    </header>
    <div v-if="data?.identity.acceptance_mode" class="identity-notice" role="note"><el-icon><InfoFilled /></el-icon><span>当前使用统一管理员测试账号，个人事项按此账号归属，岗位待办展示已接入岗位的事项。</span></div>

    <section class="workbench-metrics" aria-label="当前分类的事项统计">
      <button v-for="metric in metrics" :key="metric.filter" type="button" class="metric-card" :class="[metric.className, { selected: query.due === metric.filter }]" :aria-pressed="query.due === metric.filter" @click="changeQuery({ due: metric.filter, page: 1 })">
        <span class="metric-icon"><el-icon><component :is="metric.icon" /></el-icon></span>
        <span class="metric-content"><span class="metric-label">{{ metric.label }}</span><strong>{{ data && !error ? metric.value : '—' }}</strong><small>{{ scopeLabel }}<span> · {{ metric.description }}</span></small></span>
        <el-icon class="metric-arrow"><ArrowRight /></el-icon>
      </button>
    </section>

    <section class="task-panel" aria-labelledby="task-panel-title" :aria-busy="loading">
      <div class="task-panel-heading"><h2 id="task-panel-title">工作事项</h2><span>优先显示逾期、加急及交期临近的事项</span></div>
      <nav class="scope-tabs" aria-label="待办分类">
        <button v-for="tab in scopes" :key="tab.key" type="button" :class="{ active: query.scope === tab.key }" :aria-current="query.scope === tab.key ? 'page' : undefined" @click="changeQuery({ scope: tab.key, due: 'all', page: 1 })">{{ tab.label }}<span>{{ data && !error ? data.counts[tab.key] : '—' }}</span></button>
      </nav>
      <form class="task-filters" role="search" aria-label="筛选工作事项" @submit.prevent="applySearch">
        <el-input v-model="searchText" :prefix-icon="Search" clearable maxlength="120" placeholder="搜索单据编号、客户或零件" aria-label="搜索工作事项" @clear="applySearch" />
        <el-select :model-value="query.module || ''" aria-label="业务类型" placeholder="全部业务" @change="setModule"><el-option label="全部业务" value="" /><el-option label="生产计划" value="production" /><el-option label="发货订单" value="shipping" /></el-select>
        <el-select :model-value="query.due" aria-label="交期筛选" @change="setDue"><el-option label="全部交期" value="all" /><el-option label="今日到期" value="today" /><el-option label="已逾期" value="overdue" /><el-option label="未设置交期" value="undated" /></el-select>
        <el-button native-type="submit">查询</el-button><el-button v-if="hasFilters" text @click="resetFilters">重置</el-button>
      </form>
      <div class="scope-description"><el-icon><InfoFilled /></el-icon><span>{{ scopeDescription }}</span></div>
      <div v-if="error" class="workbench-state error-state" role="alert"><el-icon><WarningFilled /></el-icon><h3>工作事项加载失败</h3><p>{{ error }}</p><el-button :loading="loading" @click="load">重新加载</el-button></div>
      <div v-else v-loading="loading" class="task-table-region">
        <table class="task-table" aria-label="工作事项列表">
          <thead><tr><th scope="col">业务单据 / 客户</th><th scope="col">{{ query.scope === 'created' ? '当前进度 / 业务摘要' : '待办事项 / 业务摘要' }}</th><th scope="col">{{ query.scope === 'created' ? '事项归属' : '处理岗位' }}</th><th scope="col">交期</th><th scope="col">更新时间</th><th scope="col" class="action-column">操作</th></tr></thead>
          <tbody><tr v-for="task in data?.items || []" :key="task.key" class="task-row" :data-task-key="task.key">
            <td><span class="module-label">{{ task.module === 'production' ? '生产计划' : '发货订单' }}</span><router-link class="document-link" :to="task.route">{{ task.document_no }}</router-link><small class="customer-name">{{ task.customer || '未关联客户' }}</small></td>
            <td class="task-summary"><div class="task-title"><strong>{{ task.title }}</strong><span v-if="task.urgent" class="urgency-badge">加急</span></div><small>{{ task.summary }}</small></td>
            <td><span class="role-badge">{{ task.role }}</span></td>
            <td><span class="due-date" :class="dueClass(task)">{{ task.due_date || '未设置' }}</span><small v-if="task.due_date" class="due-description" :class="dueClass(task)">{{ dueDescription(task) }}</small></td>
            <td><span class="update-time">{{ formatTime(task.updated_at) }}</span></td>
            <td class="action-column"><router-link class="task-action" :to="task.route" :aria-label="`${task.action_label}：${task.document_no}，${task.title}`">{{ task.action_label }}<el-icon><ArrowRight /></el-icon></router-link></td>
          </tr></tbody>
        </table>
        <div v-if="!loading && !data?.items.length" class="workbench-state empty-state" role="status">
          <span class="empty-icon"><el-icon><DocumentChecked /></el-icon></span>
          <h3>{{ hasFilters ? '没有符合筛选条件的事项' : query.scope === 'mine' ? '当前没有个人待办' : query.scope === 'team' ? '当前岗位暂无待处理事项' : '暂无进行中的发起记录' }}</h3>
          <p>{{ hasFilters ? '可以调整关键词、业务类型或交期后重新查询。' : query.scope === 'mine' ? '需要岗位协作的事项可以在“岗位待办”中查看。' : '后续业务进入相应流程时，会自动出现在这里。' }}</p>
          <el-button v-if="hasFilters" @click="resetFilters">清除筛选</el-button><el-button v-else-if="query.scope === 'mine'" @click="changeQuery({ scope: 'team', page: 1 })">查看岗位待办</el-button>
        </div>
        <div v-if="loading && !data" class="initial-loading" role="status">正在读取工作事项…</div>
        <footer class="table-footer"><span>共 {{ data?.total || 0 }} 项<span class="footer-note"> · 每项关联原始业务单据</span></span><el-pagination :current-page="data?.page || query.page" :page-size="query.page_size" :total="data?.total || 0" :page-sizes="[15, 30, 50]" :disabled="loading" layout="sizes, prev, pager, next" @current-change="setPage" @size-change="setPageSize" /></footer>
      </div>
    </section>
    <p class="workbench-footnote">已接入：资材确认、生产排产、标签确认、发货确认与本人草稿。业务完成后刷新，相关事项将自动移出待办。</p>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowRight, Box, Calendar, Clock, DocumentChecked, InfoFilled, List, Refresh, Search, WarningFilled } from '@element-plus/icons-vue'
import { workbenchApi, type DueFilter, type TaskModule, type TaskScope, type WorkbenchPage, type WorkbenchQuery, type WorkbenchTask } from '@/api/workbench'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const data = ref<WorkbenchPage | null>(null)
const loading = ref(false)
const error = ref('')
const searchText = ref('')
const scopes: { key: TaskScope; label: string }[] = [{ key: 'mine', label: '我的待办' }, { key: 'team', label: '岗位待办' }, { key: 'created', label: '我发起的' }]
const query = computed<WorkbenchQuery>(() => ({
  scope: ['mine', 'team', 'created'].includes(String(route.query.scope)) ? route.query.scope as TaskScope : 'mine',
  module: ['production', 'shipping'].includes(String(route.query.module)) ? route.query.module as WorkbenchQuery['module'] : undefined,
  search: typeof route.query.search === 'string' ? route.query.search.slice(0, 120) : '',
  due: ['today', 'overdue', 'undated'].includes(String(route.query.due)) ? route.query.due as DueFilter : 'all',
  page: Math.max(1, Math.floor(Number(route.query.page) || 1)),
  page_size: [15, 30, 50].includes(Number(route.query.page_size)) ? Number(route.query.page_size) : 15,
}))
const scopeLabel = computed(() => scopes.find(tab => tab.key === query.value.scope)?.label || '')
const scopeDescription = computed(() => ({ mine: '显示明确归属于当前账号的草稿和待确认事项。', team: data.value?.identity.administrator ? '管理员可查看已接入岗位的处理队列。各事项仍在原业务页面办理。' : '根据当前账号的部门、岗位和权限显示处理事项。同岗位人员共享此队列。', created: '跟进由当前账号创建、尚未结束的生产计划和已提交发货订单。' }[query.value.scope]))
const identityName = computed(() => data.value?.identity.name || userStore.userInfo?.real_name || '当前用户')
const displayDate = computed(() => new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Shanghai', month: 'long', day: 'numeric', weekday: 'long' }).format(data.value ? new Date(`${data.value.today}T12:00:00+08:00`) : new Date()))
const lastUpdated = computed(() => data.value ? `${new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Shanghai', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }).format(new Date(data.value.generated_at))} 已更新` : '')
const metrics = computed(() => [
  { label: query.value.scope === 'created' ? '进行中事项' : '待处理事项', value: data.value?.stats.pending, filter: 'all' as DueFilter, icon: List, className: 'pending', description: '全部事项' },
  { label: '今日到期', value: data.value?.stats.today, filter: 'today' as DueFilter, icon: Calendar, className: 'today', description: '今天需要关注' },
  { label: '已逾期', value: data.value?.stats.overdue, filter: 'overdue' as DueFilter, icon: Clock, className: 'overdue', description: '优先处理' },
])
const hasFilters = computed(() => !!query.value.search || !!query.value.module || query.value.due !== 'all')
let requestSequence = 0
const load = async () => {
  const sequence = ++requestSequence
  loading.value = true
  error.value = ''
  try { const response = await workbenchApi.list(query.value); if (sequence === requestSequence) data.value = response }
  catch (reason) { if (sequence === requestSequence) error.value = reason instanceof Error ? reason.message : '请稍后重试。' }
  finally { if (sequence === requestSequence) loading.value = false }
}
const changeQuery = (changes: Partial<WorkbenchQuery>) => {
  const next = { ...query.value, ...changes }
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
  const days = Math.round((Date.parse(`${task.due_date}T00:00:00+08:00`) - Date.parse(`${data.value.today}T00:00:00+08:00`)) / 86400000)
  return days < 0 ? `已逾期 ${-days} 天` : days === 0 ? '今天到期' : `还有 ${days} 天`
}
const formatTime = (value: string | null) => {
  if (!value) return '—'
  // Existing business timestamps are UTC without an offset.
  const timestamp = /(?:Z|[+-]\d\d:\d\d)$/.test(value) ? value : `${value}Z`
  return new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Shanghai', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false }).format(new Date(timestamp))
}
watch(query, () => { searchText.value = query.value.search; void load() }, { immediate: true })
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
</style>
