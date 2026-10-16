<template>
  <div class="project-list-page">
    <div class="quote-page-heading">
      <div><h1>报价组</h1><p class="list-caption">技术评审通过后，在这里完成方案和客户报价</p></div>
      <el-popover placement="bottom-end" :width="280" trigger="click" title="报价流程">
        <p class="quote-help">技术评审通过后自动生成报价组，技术资料同步带入。完成材料、费用和产品报价后保存，状态将更新为“已报价”。</p>
        <template #reference><el-button :icon="InfoFilled">报价说明</el-button></template>
      </el-popover>
    </div>
    <div class="quote-toolbar" role="search" aria-label="筛选报价组">
      <div class="search-control"><el-icon aria-hidden="true"><Search /></el-icon><el-input v-model="keyword" aria-label="搜索报价组、客户或零件号" placeholder="搜索报价组、客户或零件号" clearable /></div>
      <el-select v-model="status" aria-label="报价状态" placeholder="全部状态" clearable><el-option v-for="item in quoteStatuses" :key="item" :label="item" :value="item" /></el-select>
      <el-button v-if="hasFilters" text @click="clearFilters">清除筛选</el-button>
    </div>
    <div v-if="!loading && !loadError" class="table-meta" role="status"><span>显示 {{ filtered.length }} / {{ quoteGroups.length }} 个报价组</span><span>{{ pendingCount }} 个待报价 · {{ quoteGroups.length - pendingCount }} 个已报价</span></div>
    <el-table v-if="!loading && !loadError && filtered.length" :data="filtered" stripe>
      <el-table-column label="报价组" width="145"><template #default="{ row }"><span class="mono">{{ row.id }}</span></template></el-table-column>
      <el-table-column label="客户 / 项目" min-width="190"><template #default="{ row }"><div class="stacked"><strong>{{ row.customer }}</strong><small>{{ row.projectName }}</small></div></template></el-table-column>
      <el-table-column label="零件 / 技术资料" min-width="270"><template #default="{ row }"><div v-for="part in row.parts" :key="part.id" class="part-line"><span class="pair-dot"></span><span class="mono">{{ part.customerPartNo }}</span><span>{{ part.name }}</span><small v-if="part.cavityCount">{{ part.cavityCount }}穴<span v-if="part.pairLabel"> · {{ part.pairLabel }}</span></small></div></template></el-table-column>
      <el-table-column label="推荐方案" width="180"><template #default="{ row }"><div class="stacked"><strong>{{ row.toolingType }}</strong><small>{{ row.path }}</small></div></template></el-table-column>
      <el-table-column label="模具费" width="120" align="right"><template #default="{ row }"><span class="mono">¥{{ Number(row.toolingCost || 0).toLocaleString() }}</span></template></el-table-column>
      <el-table-column label="状态" width="125"><template #default="{ row }"><el-tag size="small" :type="row.status === '已报价' ? 'success' : 'warning'">{{ row.status }}</el-tag></template></el-table-column>
      <el-table-column label="操作" width="115" fixed="right"><template #default="{ row }"><el-button link type="primary" @click="openQuote(row)">{{ row.status === '已报价' ? '编辑报价' : '开始报价' }}</el-button></template></el-table-column>
    </el-table>
    <div v-else-if="loadError && !loading" class="quote-state" role="alert"><el-icon><WarningFilled /></el-icon><strong>报价组加载失败</strong><p>{{ loadError }}</p><el-button @click="loadQuoteGroups">重新加载</el-button></div>
    <el-empty v-else-if="!loading" :description="hasFilters ? '没有符合筛选条件的报价组' : '暂无已通过技术评审的报价组'" :image-size="72"><el-button v-if="hasFilters" @click="clearFilters">清除筛选</el-button><p v-else class="empty-hint">技术评审通过后，报价组会自动出现在这里。</p></el-empty>
    <div v-else class="quote-state" role="status" aria-live="polite"><span class="loading-dot" />正在加载报价组…</div>
    <QuoteGroupDialog v-model="quoteDialogVisible" :group="activeGroup" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { InfoFilled, Search, WarningFilled } from '@element-plus/icons-vue'
import { mapQuoteGroup, quoteGroups, type QuoteGroup } from './data'
import { quoteGroupsApi } from '@/api/quoteGroups'
import QuoteGroupDialog from './QuoteGroupDialog.vue'

const keyword = ref('')
const status = ref('')
const loading = ref(false)
const loadError = ref('')
const quoteDialogVisible = ref(false)
const activeGroup = ref<QuoteGroup | null>(null)
const quoteStatuses = computed(() => [...new Set(quoteGroups.map(row => row.status))])
const pendingCount = computed(() => quoteGroups.filter(row => row.status !== '已报价').length)
const hasFilters = computed(() => Boolean(keyword.value.trim() || status.value))
const clearFilters = () => { keyword.value = ''; status.value = '' }
const filtered = computed(() => quoteGroups.filter(row => {
  const text = `${row.id} ${row.customer} ${row.projectName} ${row.parts.map(part => `${part.customerPartNo} ${part.name}`).join(' ')}`.toLowerCase()
  return (!keyword.value.trim() || text.includes(keyword.value.trim().toLowerCase())) && (!status.value || row.status === status.value)
}))
const openQuote = (group: QuoteGroup) => { activeGroup.value = group; quoteDialogVisible.value = true }
const loadQuoteGroups = async () => {
  loading.value = true
  loadError.value = ''
  quoteGroups.splice(0, quoteGroups.length)
  try {
    const records = await quoteGroupsApi.list()
    quoteGroups.splice(0, quoteGroups.length, ...records.map(mapQuoteGroup))
  } catch (error) {
    const message = error instanceof Error ? error.message : ''
    loadError.value = !message || message === 'Network Error' ? '网络连接异常，请检查连接后重试' : message
  } finally {
    loading.value = false
  }
}
onMounted(loadQuoteGroups)
</script>

<style scoped>
.project-list-page { min-width: 0; padding: 22px 0 30px; color: var(--zephyr-ink); }
.quote-page-heading { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 22px; }
.quote-page-heading h1 { margin: 0; font-size: 22px; font-weight: 650; letter-spacing: -.025em; }
.list-caption { margin: 5px 0 0; }
.quote-toolbar { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; margin-bottom: 18px; }
.quote-toolbar .search-control { flex: 0 1 380px; }
.quote-toolbar > .el-select { width: 150px; }
.quote-toolbar > .el-button { margin-left: 0; }
.stacked { display: flex; flex-direction: column; gap: 3px; }
.stacked strong { font-weight: 600; }
.stacked small, .part-line small { color: var(--zephyr-muted); font-size: 12px; }
.part-line { display: flex; align-items: center; flex-wrap: wrap; gap: 6px; min-height: 27px; font-size: 12px; }
.pair-dot { flex: none; width: 5px; height: 5px; border-radius: 50%; background: var(--zephyr-primary); }
.mono { font-family: var(--zephyr-font-mono); font-size: 12px; }
.quote-state { display: flex; flex-direction: column; align-items: center; gap: 12px; padding: 64px 16px; border: 1px solid var(--zephyr-border); border-radius: 8px; background: var(--zephyr-surface); color: var(--zephyr-muted); text-align: center; }
.quote-state p { margin: 0; max-width: 480px; }
.quote-state > .el-icon { color: var(--zephyr-warning); font-size: 24px; }
.loading-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--zephyr-primary); }
.quote-help, .empty-hint { margin: 0; color: var(--zephyr-muted); font-size: 12px; line-height: 1.7; }
@media (max-width: 600px) {
  .quote-page-heading { align-items: flex-start; gap: 12px; margin-bottom: 18px; }
  .quote-page-heading > .el-button { flex: none; }
  .quote-toolbar .search-control { flex-basis: 100%; }
  .quote-toolbar > .el-select { flex: 1; max-width: 190px; }
}
</style>
