<template>
  <div class="inventory-workspace">
    <header class="workspace-header">
      <div>
        <span class="eyebrow">WAREHOUSE / FINISHED GOODS</span>
        <h2>成品库存</h2>
        <p>已核验库存进入正式台账，需要仓库确认的原始记录单独保留。</p>
      </div>
      <div class="snapshot-mark">
        <span>最新导入批次</span>
        <strong>{{ summary.batch_id ? `#${summary.batch_id}` : '暂无' }}</strong>
      </div>
    </header>

    <section class="summary-grid" aria-label="成品库存汇总">
      <article class="summary-card"><span>库存记录</span><strong>{{ formatInteger(summary.inventory_rows) }}</strong><small>已关联零件库</small></article>
      <article class="summary-card"><span>现存总数</span><strong>{{ formatInteger(summary.total_stock) }}</strong><small>件</small></article>
      <article class="summary-card"><span>可用库存</span><strong>{{ formatInteger(summary.total_available) }}</strong><small>已扣除预留 {{ formatInteger(summary.total_reserved) }} 件</small></article>
      <article class="summary-card attention"><span>待处理</span><strong>{{ formatInteger(summary.review_rows) }}</strong><small>不计入正式库存</small></article>
    </section>

    <section class="workspace-panel">
      <el-tabs v-model="activeTab" class="inventory-tabs" @tab-change="handleTabChange">
        <el-tab-pane name="formal">
          <template #label><span class="tab-label">正式库存 <b>{{ formatInteger(formalTotal) }}</b></span></template>
          <div class="toolbar">
            <el-select v-model="formalFilters.customer_id" class="customer-filter" clearable filterable placeholder="选择客户" @change="handleCustomerChange">
              <el-option v-for="customer in customers" :key="customer.id" :label="customer.name" :value="customer.id" />
            </el-select>
            <el-autocomplete v-model="formalFilters.customer_part_no" class="part-filter" clearable :fetch-suggestions="queryPartNumbers" value-key="customer_part_no" placeholder="输入客户件号自动补全" @select="handlePartSelect" @clear="handlePartClear" @keyup.enter="searchFormal">
              <template #default="{ item }"><div class="part-suggestion"><strong>{{ item.customer_part_no }}</strong><span>{{ item.part_name || '未维护零件名' }}</span></div></template>
            </el-autocomplete>
            <el-autocomplete v-model="formalFilters.part_name" class="part-name-filter" clearable :fetch-suggestions="queryPartNames" value-key="part_name" placeholder="输入零件名自动补全" @select="handlePartNameSelect" @clear="handlePartNameClear" @keyup.enter="searchFormal">
              <template #default="{ item }"><div class="part-suggestion"><strong>{{ item.part_name }}</strong><span>{{ item.customer_part_no || '未维护客户件号' }}</span></div></template>
            </el-autocomplete>
            <el-input v-model="formalFilters.location" clearable placeholder="库位" @keyup.enter="searchFormal" @clear="searchFormal" />
            <el-button type="primary" @click="searchFormal">查询</el-button>
            <el-button @click="resetFormal">重置</el-button>
          </div>

          <el-table v-loading="formalLoading" :data="formalRows" height="520" stripe table-layout="fixed" empty-text="没有已编客户件号的正式库存">
            <el-table-column label="客户件号" prop="customer_part_no" min-width="180" show-overflow-tooltip />
            <el-table-column label="零件名" min-width="190" show-overflow-tooltip>
              <template #default="{ row }">{{ row.part_name || row.customer_part_name || '' }}</template>
            </el-table-column>
            <el-table-column label="客户" prop="customer_name" min-width="150" show-overflow-tooltip />
            <el-table-column label="库存" prop="stock_qty" width="115" align="right">
              <template #default="{ row }"><div class="stock-cell"><b class="number">{{ formatInteger(row.stock_qty) }}</b><span v-if="row.reserved_qty" class="muted">可用 {{ formatInteger(row.available_qty) }}</span></div></template>
            </el-table-column>
            <el-table-column label="库位" prop="location" min-width="120"><template #default="{ row }"><span>{{ row.location || '' }}</span></template></el-table-column>
            <el-table-column label="近1个月出货" prop="last_month_shipped_qty" width="125" align="right"><template #default="{ row }"><span class="number shipment-number">{{ formatInteger(row.last_month_shipped_qty) }}</span></template></el-table-column>
            <el-table-column label="近3个月出货" prop="last_3_month_shipped_qty" width="125" align="right"><template #default="{ row }"><span class="number shipment-number">{{ formatInteger(row.last_3_month_shipped_qty) }}</span></template></el-table-column>
            <el-table-column label="更新时间" prop="last_update_at" width="165"><template #default="{ row }"><span class="muted">{{ formatDateTime(row.last_update_at) }}</span></template></el-table-column>
            <el-table-column label="操作" width="180" fixed="right"><template #default="{ row }"><el-button link type="primary" @click="openLedger(row)">收支明细</el-button><el-button link type="primary" @click="editLocation(row)">库位</el-button></template></el-table-column>
          </el-table>
          <div class="pagination-row"><span>共 {{ formatInteger(formalTotal) }} 条</span><el-pagination v-model:current-page="formalPage" v-model:page-size="formalPageSize" :page-sizes="[25, 50, 100, 200]" :total="formalTotal" layout="sizes, prev, pager, next" @current-change="loadFormal" @size-change="changeFormalPageSize" /></div>
        </el-tab-pane>

        <el-tab-pane name="review">
          <template #label><span class="tab-label review-tab">待处理 <b>{{ formatInteger(summary.review_rows) }}</b></span></template>
          <div class="review-notice"><div><strong>这些记录尚未进入正式库存</strong><span>仓库人员可按原工作表和 Excel 行号比对；未填库位不作为错误。</span></div></div>
          <div v-if="categoryEntries.length" class="category-strip">
            <button v-for="entry in categoryEntries" :key="entry[0]" type="button" :class="{ active: reviewFilters.category === entry[0] }" @click="toggleCategory(entry[0])">{{ entry[0] }} <b>{{ entry[1] }}</b></button>
          </div>
          <div class="toolbar review-toolbar">
            <el-input v-model="reviewFilters.search" class="search-input" clearable placeholder="搜索工作表、客户件号或零件名" @keyup.enter="searchReview" @clear="searchReview" />
            <el-button type="primary" @click="searchReview">查询</el-button><el-button @click="resetReview">重置</el-button>
          </div>
          <el-table v-loading="reviewLoading" :data="reviewRows" :row-class-name="reviewRowClass" height="480" table-layout="fixed" empty-text="没有待处理记录">
            <el-table-column label="来源" width="170"><template #default="{ row }"><div class="source-cell"><strong>{{ row.source_sheet }}</strong><span>Excel 第 {{ row.source_row }} 行</span></div></template></el-table-column>
            <el-table-column label="客户件号" min-width="190">
              <template #default="{ row }"><el-tooltip :disabled="!row.missing_part" content="零件库没有对应的件号" placement="top"><span :class="['review-part-no', { missing: row.missing_part }]">{{ row.customer_part_no || '无法判定' }}</span></el-tooltip></template>
            </el-table-column>
            <el-table-column label="零件名" prop="customer_part_name" min-width="180" show-overflow-tooltip />
            <el-table-column label="结存" prop="closing_qty" width="105" align="right"><template #default="{ row }"><span class="number">{{ formatOptionalNumber(row.closing_qty) }}</span></template></el-table-column>
            <el-table-column label="库位" prop="location" width="120"><template #default="{ row }"><span>{{ row.location || '' }}</span></template></el-table-column>
            <el-table-column label="待处理原因" min-width="300"><template #default="{ row }"><div class="issue-list"><el-tag v-for="issue in row.validation_errors" :key="issue" :type="row.missing_part && issue.includes('零件') ? 'danger' : 'warning'" effect="plain" size="small">{{ issue }}</el-tag></div></template></el-table-column>
            <el-table-column label="操作" width="120" fixed="right"><template #default="{ row }"><el-button link type="primary" @click="resolveReview(row)">确认入库</el-button></template></el-table-column>
          </el-table>
          <div class="pagination-row"><span>共 {{ formatInteger(reviewTotal) }} 条</span><el-pagination v-model:current-page="reviewPage" v-model:page-size="reviewPageSize" :page-sizes="[25, 50, 100, 200]" :total="reviewTotal" layout="sizes, prev, pager, next" @current-change="loadReview" @size-change="changeReviewPageSize" /></div>
        </el-tab-pane>
      </el-tabs>
    </section>

    <el-dialog v-model="ledgerVisible" title="收支明细" width="900px">
      <div v-if="ledgerRow" class="ledger-heading"><strong>{{ ledgerRow.customer_part_no || '-' }}</strong><span>{{ ledgerRow.part_name || ledgerRow.customer_part_name || '' }}</span><span>{{ ledgerRow.customer_name || '' }}</span></div>
      <el-tabs v-model="ledgerTab" class="ledger-tabs">
        <el-tab-pane label="收支汇总" name="summary">
          <section v-if="ledger" class="ledger-summary">
            <div><span>期初库存</span><b class="number">{{ formatInteger(ledger.summary.opening_stock) }}</b></div>
            <div class="incoming"><span>期间收入</span><b class="number">{{ formatInteger(ledger.summary.total_incoming) }}</b></div>
            <div class="outgoing"><span>期间支出</span><b class="number">{{ formatInteger(ledger.summary.total_outgoing) }}</b></div>
            <div><span>当前库存</span><b class="number">{{ formatInteger(ledger.summary.closing_stock) }}</b></div>
          </section>
          <el-table v-loading="ledgerLoading" :data="ledger?.days || []" max-height="360" stripe empty-text="近90天没有收支流水">
            <el-table-column label="日期" prop="day" width="130" />
            <el-table-column label="收入" prop="incoming_qty" width="140" align="right"><template #default="{ row }"><span class="number incoming-text">{{ formatInteger(row.incoming_qty) }}</span></template></el-table-column>
            <el-table-column label="支出" prop="outgoing_qty" width="140" align="right"><template #default="{ row }"><span class="number outgoing-text">{{ formatInteger(row.outgoing_qty) }}</span></template></el-table-column>
            <el-table-column label="净变化" prop="net_qty" width="140" align="right"><template #default="{ row }"><span class="number">{{ row.net_qty > 0 ? '+' : '' }}{{ formatInteger(row.net_qty) }}</span></template></el-table-column>
            <el-table-column label="结存" prop="closing_qty" min-width="140" align="right"><template #default="{ row }"><b class="number">{{ formatInteger(row.closing_qty) }}</b></template></el-table-column>
          </el-table>
        </el-tab-pane>
        <el-tab-pane label="流水明细" name="entries">
          <el-table v-loading="ledgerLoading" :data="ledger?.entries || []" max-height="430" stripe empty-text="近90天没有逐笔流水">
            <el-table-column label="发生时间" width="145"><template #default="{ row }">{{ formatDateTime(row.occurred_at) }}</template></el-table-column>
            <el-table-column label="类型" width="80"><template #default="{ row }"><el-tag size="small" :type="row.transaction_type === 'incoming' ? 'success' : 'warning'">{{ row.transaction_type === 'incoming' ? '收入' : '支出' }}</el-tag></template></el-table-column>
            <el-table-column label="数量" prop="quantity" width="90" align="right"><template #default="{ row }"><span class="number">{{ formatInteger(row.quantity) }}</span></template></el-table-column>
            <el-table-column label="操作前" prop="stock_before" width="90" align="right" />
            <el-table-column label="操作后" prop="stock_after" width="90" align="right" />
            <el-table-column label="库存影响" width="95"><template #default="{ row }"><span :class="row.affects_stock ? 'incoming-text' : 'muted'">{{ row.affects_stock ? '已更新' : '仅流水' }}</span></template></el-table-column>
            <el-table-column label="原因" prop="reason" min-width="170" show-overflow-tooltip />
            <el-table-column label="来源" width="110"><template #default="{ row }">{{ sourceLabel(row.reference_type) }}</template></el-table-column>
          </el-table>
        </el-tab-pane>
        <el-tab-pane label="补录历史" name="backfill">
          <div class="ledger-form">
            <div class="ledger-form-row"><el-radio-group v-model="ledgerEntryForm.transaction_type"><el-radio-button label="incoming">收入</el-radio-button><el-radio-button label="outgoing">支出</el-radio-button></el-radio-group><el-date-picker v-model="ledgerEntryForm.occurred_on" type="date" value-format="YYYY-MM-DD" placeholder="发生日期" /></div>
            <div class="ledger-form-row"><el-input-number v-model="ledgerEntryForm.quantity" :min="1" controls-position="right" /><el-switch v-model="ledgerEntryForm.affects_stock" active-text="同时影响当前库存" inactive-text="只补历史流水" /></div>
            <el-input v-model="ledgerEntryForm.reason" type="textarea" :rows="3" maxlength="200" show-word-limit placeholder="请输入补录原因或来源单据" />
            <div class="ledger-form-actions"><el-button type="primary" :loading="ledgerSubmitting" @click="submitHistoricalEntry">提交历史补录</el-button><span>历史补录不可直接修改，错误时请新增冲销流水。</span></div>
          </div>
        </el-tab-pane>
        <el-tab-pane label="库存核对" name="reconcile">
          <div class="ledger-form">
            <div class="reconcile-current">系统当前库存：<b class="number">{{ formatInteger(ledger?.summary.closing_stock) }}</b></div>
            <div class="ledger-form-row"><el-input-number v-model="reconcileForm.physical_stock" :min="0" controls-position="right" placeholder="实际盘点库存" /><el-date-picker v-model="reconcileForm.occurred_on" type="date" value-format="YYYY-MM-DD" placeholder="盘点日期" /></div>
            <el-input v-model="reconcileForm.reason" type="textarea" :rows="3" maxlength="200" show-word-limit placeholder="请输入盘点说明" />
            <div class="ledger-form-actions"><el-button type="warning" :loading="ledgerSubmitting" @click="submitReconciliation">提交库存核对</el-button><span>系统会按差异生成盘盈或盘亏流水。</span></div>
          </div>
        </el-tab-pane>
      </el-tabs>
      <template #footer><span class="ledger-footnote">统计范围：{{ ledger ? ledger.summary.from_date + ' 至 ' + ledger.summary.to_date : '近90天' }}；历史补录可选择是否影响当前库存。</span><el-button type="success" plain @click="registerLedgerEntry('incoming')">登记收入</el-button><el-button type="warning" plain @click="registerLedgerEntry('outgoing')">登记支出</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { customersApi } from '@/api/customers'
import { partsApi } from '@/api/parts'
import { warehouseApi } from '@/api/warehouse'

interface InventoryRow { id: number; part_id: number; internal_part_no: string | null; part_name: string | null; customer_part_no: string | null; customer_part_name: string | null; customer_name: string | null; stock_qty: number; reserved_qty: number; available_qty: number; last_month_shipped_qty: number; last_3_month_shipped_qty: number; location: string | null; last_update_at: string }
interface InventorySummary { inventory_rows: number; total_stock: number; total_reserved: number; total_available: number; missing_location_rows: number; review_rows: number; batch_id: number | null }
interface InventoryPage { items: InventoryRow[]; total: number; page: number; page_size: number; summary: InventorySummary }
interface ReviewRow { id: number; batch_id: number; source_sheet: string; source_row: number; customer_part_no: string | null; customer_part_name: string | null; closing_qty: number | null; location: string | null; validation_errors: string[]; missing_part: boolean }
interface ReviewPage { items: ReviewRow[]; total: number; page: number; page_size: number; batch_id: number | null; categories: Record<string, number> }
interface LedgerDay { day: string; incoming_qty: number; outgoing_qty: number; net_qty: number; closing_qty: number }
interface LedgerEntry { id: number; occurred_at: string; transaction_type: 'incoming' | 'outgoing'; quantity: number; stock_before: number; stock_after: number; reason: string | null; reference_type: string | null; operator_id: number | null; affects_stock: boolean }
interface Ledger { inventory_id: number; part_id: number; summary: { opening_stock: number; total_incoming: number; total_outgoing: number; closing_stock: number; from_date: string; to_date: string }; days: LedgerDay[]; entries: LedgerEntry[] }
interface CustomerOption { id: number; name: string }
interface CustomerPartOption { key: string; customer_part_no: string; part_name: string }
interface PartNameOption { key: string; part_name: string; customer_part_no: string }

const emptySummary = (): InventorySummary => ({ inventory_rows: 0, total_stock: 0, total_reserved: 0, total_available: 0, missing_location_rows: 0, review_rows: 0, batch_id: null })
const activeTab = ref('formal')
const formalLoading = ref(false)
const formalRows = ref<InventoryRow[]>([])
const formalTotal = ref(0)
const formalPage = ref(1)
const formalPageSize = ref(50)
const summary = reactive<InventorySummary>(emptySummary())
const formalFilters = reactive({ customer_id: null as number | null, customer_part_no: '', part_name: '', location: '' })
const customers = ref<CustomerOption[]>([])
const reviewLoading = ref(false)
const reviewLoaded = ref(false)
const reviewRows = ref<ReviewRow[]>([])
const reviewTotal = ref(0)
const reviewPage = ref(1)
const reviewPageSize = ref(50)
const reviewCategories = ref<Record<string, number>>({})
const reviewFilters = reactive({ search: '', category: '' })
const ledgerVisible = ref(false)
const ledgerLoading = ref(false)
const ledger = ref<Ledger | null>(null)
const ledgerRow = ref<InventoryRow | null>(null)
const ledgerTab = ref('summary')
const ledgerSubmitting = ref(false)
const ledgerEntryForm = reactive({ transaction_type: 'incoming' as 'incoming' | 'outgoing', quantity: 1, occurred_on: '', affects_stock: false, reason: '' })
const reconcileForm = reactive({ physical_stock: 0, occurred_on: '', reason: '' })
const categoryEntries = computed(() => Object.entries(reviewCategories.value))
const compactParams = (params: Record<string, unknown>) => Object.fromEntries(Object.entries(params).filter(([, value]) => value !== '' && value !== false && value != null))

async function loadFormal() {
  formalLoading.value = true
  try {
    const data = await warehouseApi.finishedGoods<InventoryPage>(compactParams({ ...formalFilters, page: formalPage.value, page_size: formalPageSize.value }))
    formalRows.value = data.items; formalTotal.value = data.total; Object.assign(summary, data.summary)
  } catch (error) { console.error(error); ElMessage.error('成品库存加载失败') } finally { formalLoading.value = false }
}
async function loadCustomers() {
  try {
    const data = await customersApi.list<{ items: CustomerOption[] }>({ limit: 200, has_parts: true })
    customers.value = data.items || []
  } catch (error) {
    console.error(error)
    ElMessage.error('客户列表加载失败')
  }
}
function handleCustomerChange() {
  formalFilters.customer_part_no = ''
  formalFilters.part_name = ''
  searchFormal()
}
async function queryPartNumbers(queryString: string, callback: (suggestions: CustomerPartOption[]) => void) {
  const query = queryString.trim()
  if (!query) { callback([]); return }
  try {
    const data = await partsApi.list<any[]>({ search: query, ...(formalFilters.customer_id ? { customer_id: formalFilters.customer_id } : {}), limit: 50 })
    const seen = new Set<string>()
    const suggestions = (data || []).flatMap((part) => {
      const partName = String(part.part_name || part.customer_part_name || '').trim()
      return String(part.customer_part_no || '').split(/\s*\/\s*/).map((customerPartNo: string) => ({
        key: String(part.id) + ':' + customerPartNo.trim(),
        customer_part_no: customerPartNo.trim(),
        part_name: partName,
      }))
    }).filter((part) => {
      if (!part.customer_part_no || seen.has(part.customer_part_no)) return false
      seen.add(part.customer_part_no)
      return true
    }).slice(0, 50)
    callback(suggestions)
  } catch (error) {
    console.error(error)
    callback([])
  }
}
async function queryPartNames(queryString: string, callback: (suggestions: PartNameOption[]) => void) {
  const query = queryString.trim()
  if (!query) { callback([]); return }
  try {
    const data = await partsApi.list<any[]>({ search: query, ...(formalFilters.customer_id ? { customer_id: formalFilters.customer_id } : {}), limit: 50 })
    const seen = new Set<string>()
    const suggestions = (data || []).map((part) => ({
      key: String(part.id) + ':' + String(part.part_name || part.customer_part_name || '').trim(),
      part_name: String(part.part_name || part.customer_part_name || '').trim(),
      customer_part_no: String(part.customer_part_no || '').trim(),
    })).filter((part) => {
      if (!part.part_name || seen.has(part.part_name)) return false
      seen.add(part.part_name)
      return true
    }).slice(0, 50)
    callback(suggestions)
  } catch (error) {
    console.error(error)
    callback([])
  }
}
function handlePartSelect(part: CustomerPartOption) {
  formalFilters.customer_part_no = part.customer_part_no
  formalFilters.part_name = part.part_name || ''
  searchFormal()
}
function handlePartClear() {
  formalFilters.part_name = ''
  searchFormal()
}
function handlePartNameSelect(part: PartNameOption) {
  formalFilters.part_name = part.part_name
  searchFormal()
}
function handlePartNameClear() {
  formalFilters.part_name = ''
  searchFormal()
}
async function loadReview() {
  reviewLoading.value = true
  try {
    const data = await warehouseApi.finishedGoodsReview<ReviewPage>(compactParams({ ...reviewFilters, page: reviewPage.value, page_size: reviewPageSize.value }))
    reviewRows.value = data.items; reviewTotal.value = data.total; reviewCategories.value = data.categories; reviewLoaded.value = true
  } catch (error) { console.error(error); ElMessage.error('待处理库存加载失败') } finally { reviewLoading.value = false }
}
function searchFormal() { formalPage.value = 1; loadFormal() }
function resetFormal() { Object.assign(formalFilters, { customer_id: null, customer_part_no: '', part_name: '', location: '' }); searchFormal() }
function changeFormalPageSize() { formalPage.value = 1; loadFormal() }
function searchReview() { reviewPage.value = 1; loadReview() }
function resetReview() { Object.assign(reviewFilters, { search: '', category: '' }); searchReview() }
function changeReviewPageSize() { reviewPage.value = 1; loadReview() }
function toggleCategory(category: string) { reviewFilters.category = reviewFilters.category === category ? '' : category; searchReview() }
function handleTabChange(name: string | number) { if (name === 'review' && !reviewLoaded.value) loadReview() }
function reviewRowClass({ row }: { row: ReviewRow }) { return row.missing_part ? 'missing-part-row' : '' }
async function openLedger(row: InventoryRow) {
  ledgerRow.value = row
  ledger.value = null
  ledgerTab.value = 'summary'
  Object.assign(ledgerEntryForm, { transaction_type: 'incoming', quantity: 1, occurred_on: '', affects_stock: false, reason: '' })
  Object.assign(reconcileForm, { physical_stock: row.stock_qty, occurred_on: '', reason: '' })
  ledgerVisible.value = true
  ledgerLoading.value = true
  try { ledger.value = await warehouseApi.finishedGoodsLedger<Ledger>(row.id, { days: 90 }) }
  catch (error) { console.error(error); ledgerVisible.value = false; ElMessage.error('收支明细加载失败') }
  finally { ledgerLoading.value = false }
}
function sourceLabel(referenceType: string | null) {
  if (referenceType === 'historical_ledger' || referenceType === 'historical_note') return '历史补录'
  if (referenceType === 'inventory_reconciliation') return '库存核对'
  if (referenceType === 'manual_ledger') return '手工登记'
  if (referenceType === 'shipment') return '确认发货'
  if (referenceType === 'packaging_record') return '合格入库'
  if (referenceType === 'adjustment') return '历史调整'
  return referenceType || '系统流水'
}
async function submitHistoricalEntry() {
  if (!ledgerRow.value || !ledgerEntryForm.occurred_on || !ledgerEntryForm.reason.trim()) {
    ElMessage.warning('请填写发生日期和补录原因')
    return
  }
  ledgerSubmitting.value = true
  try {
    await warehouseApi.createFinishedGoodsLedgerEntry(ledgerRow.value.id, {
      transaction_type: ledgerEntryForm.transaction_type,
      quantity: ledgerEntryForm.quantity,
      reason: ledgerEntryForm.reason.trim(),
      occurred_on: ledgerEntryForm.occurred_on,
      affects_stock: ledgerEntryForm.affects_stock,
    })
    ElMessage.success('历史收支已补录')
    await openLedger(ledgerRow.value)
    await loadFormal()
  } catch (error: any) {
    ElMessage.error(error?.message || '历史补录失败')
  } finally { ledgerSubmitting.value = false }
}
async function submitReconciliation() {
  if (!ledgerRow.value || !reconcileForm.occurred_on || !reconcileForm.reason.trim()) {
    ElMessage.warning('请填写盘点日期和盘点说明')
    return
  }
  ledgerSubmitting.value = true
  try {
    const result = await warehouseApi.reconcileFinishedGoodsLedger<any>(ledgerRow.value.id, {
      physical_stock: reconcileForm.physical_stock,
      occurred_on: reconcileForm.occurred_on,
      reason: reconcileForm.reason.trim(),
    })
    const difference = Number(result.difference || 0)
    ElMessage.success(difference ? ('库存核对完成，已登记' + (difference > 0 ? '盘盈 ' : '盘亏 ') + Math.abs(difference) + ' 件') : '库存核对完成，无差异')
    await openLedger(ledgerRow.value)
    await loadFormal()
  } catch (error: any) {
    ElMessage.error(error?.message || '库存核对失败')
  } finally { ledgerSubmitting.value = false }
}
async function registerLedgerEntry(transactionType: 'incoming' | 'outgoing') {
  if (!ledgerRow.value) return
  const label = transactionType === 'incoming' ? '收入' : '支出'
  try {
    const quantity = await ElMessageBox.prompt('请输入' + label + '数量', '登记' + label, { confirmButtonText: '下一步', cancelButtonText: '取消', inputPattern: /^[1-9]\d*$/, inputErrorMessage: '请输入正整数' })
    const reason = await ElMessageBox.prompt('请输入' + label + '原因', '登记' + label, { confirmButtonText: '提交', cancelButtonText: '取消', inputPattern: /\S+/, inputErrorMessage: '原因不能为空' })
    await warehouseApi.createFinishedGoodsLedgerEntry(ledgerRow.value.id, { transaction_type: transactionType, quantity: Number(quantity.value), reason: reason.value })
    ElMessage.success(label + '已登记，库存已更新')
    await openLedger(ledgerRow.value)
    await loadFormal()
  } catch (error: any) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error(error?.message || (label + '登记失败'))
  }
}
async function editLocation(row: InventoryRow) {
  try {
    const result = await ElMessageBox.prompt('请输入库位；留空表示清除库位', '更新库位', { inputValue: row.location || '', confirmButtonText: '保存', cancelButtonText: '取消' })
    await warehouseApi.updateLocation(row.id, { location: result.value || null })
    ElMessage.success('库位已更新')
    await loadFormal()
  } catch (error: any) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error(error?.message || '库位更新失败')
  }
}
async function resolveReview(row: ReviewRow) {
  try {
    const part = await ElMessageBox.prompt('请输入零件库中的内部零件 ID', '确认待处理库存', { confirmButtonText: '下一步', cancelButtonText: '取消', inputPattern: /^\d+$/, inputErrorMessage: '请输入有效零件 ID' })
    const location = await ElMessageBox.prompt('库位可留空', '确认待处理库存', { inputValue: row.location || '', confirmButtonText: '确认入库', cancelButtonText: '取消' })
    await warehouseApi.resolveReview(row.id, { part_id: Number(part.value), stock_qty: row.closing_qty == null ? null : Math.round(row.closing_qty), location: location.value || null })
    ElMessage.success('记录已转入正式库存')
    reviewLoaded.value = false
    await loadFormal()
    await loadReview()
  } catch (error: any) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error(error?.message || '待处理记录确认失败')
  }
}
const numberFormatter = new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 2 })
function formatInteger(value: number | null | undefined) { return numberFormatter.format(Number(value || 0)) }
function formatOptionalNumber(value: number | null | undefined) { return value == null ? '' : numberFormatter.format(value) }
function formatDateTime(value: string) { if (!value) return ''; const date = new Date(value); return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN', { hour12: false }) }
onMounted(async () => { await loadCustomers(); await loadFormal() })
</script>

<style scoped>
.inventory-workspace { min-width: 0; color: var(--zephyr-ink); }
.workspace-header { display: flex; align-items: flex-end; justify-content: space-between; gap: 24px; margin-bottom: 18px; }
.workspace-header h2 { margin: 4px 0 5px; font-size: 24px; line-height: 1.2; letter-spacing: -.02em; }
.workspace-header p { margin: 0; color: var(--zephyr-muted); font-size: 13px; }
.eyebrow { color: var(--zephyr-primary); font-family: 'IBM Plex Mono', Consolas, monospace; font-size: 11px; font-weight: 700; letter-spacing: .08em; }
.snapshot-mark { display: flex; min-width: 116px; flex-direction: column; align-items: flex-end; padding-left: 18px; border-left: 1px solid var(--zephyr-border); }
.snapshot-mark span { color: #88908d; font-size: 11px; }
.snapshot-mark strong { margin-top: 2px; font-family: 'IBM Plex Mono', Consolas, monospace; font-size: 17px; }
.summary-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 0; margin-bottom: 14px; border: 1px solid var(--zephyr-border); border-radius: 8px; overflow: hidden; background: #fff; }
.summary-card { min-height: 84px; padding: 12px 16px; border: 0; border-right: 1px solid var(--zephyr-border-soft); background: transparent; }.summary-card:first-child { background: var(--zephyr-primary-soft); }.summary-card:last-child { border-right: 0; }
.summary-card > span { display: block; color: var(--zephyr-muted); font-size: 12px; }
.summary-card strong { display: block; margin: 5px 0 2px; font-family: 'IBM Plex Mono', Consolas, monospace; font-size: 25px; line-height: 1.1; font-variant-numeric: tabular-nums; }
.summary-card small { color: #939a97; font-size: 11px; }
.summary-card.attention strong { color: var(--zephyr-warning); }
.workspace-panel { border: 1px solid var(--zephyr-border); border-radius: 5px; background: #fff; overflow: hidden; }
.inventory-tabs :deep(.el-tabs__header) { margin: 0; padding: 0 18px; border-bottom: 1px solid var(--zephyr-border-soft); }
.inventory-tabs :deep(.el-tabs__nav-wrap::after) { display: none; }
.inventory-tabs :deep(.el-tabs__item) { height: 48px; font-size: 13px; }
.inventory-tabs :deep(.el-tabs__content) { overflow: visible; }
.tab-label { display: inline-flex; align-items: center; gap: 7px; }
.tab-label b { min-width: 22px; padding: 1px 6px; border-radius: 10px; background: var(--zephyr-primary-soft); color: var(--zephyr-primary); font-family: 'IBM Plex Mono', Consolas, monospace; font-size: 10px; text-align: center; }
.review-tab b { background: #fff1de; color: #9d651d; }
.toolbar { display: grid; grid-template-columns: minmax(180px, 1fr) minmax(180px, 1fr) minmax(160px, 1fr) 150px auto auto; align-items: center; gap: 8px; padding: 12px 14px; background: var(--zephyr-surface-muted); border-bottom: 1px solid var(--zephyr-border-soft); }
.review-toolbar { grid-template-columns: minmax(280px, 520px) auto auto 1fr; }
.search-input { min-width: 0; }
.customer-filter, .part-filter, .part-name-filter { min-width: 0; }
.part-suggestion { display: flex; align-items: baseline; justify-content: space-between; gap: 16px; }
.part-suggestion strong { font-family: 'IBM Plex Mono', Consolas, monospace; font-size: 12px; }
.part-suggestion span { color: #7b8581; font-size: 11px; }
.review-notice { display: flex; align-items: center; padding: 12px 15px; border-bottom: 1px solid #ead9bf; background: #fff9ef; }
.review-notice div { display: flex; align-items: baseline; gap: 12px; }
.review-notice strong { color: #754e1e; font-size: 13px; }
.review-notice span { color: #8c7458; font-size: 12px; }
.category-strip { display: flex; flex-wrap: wrap; gap: 6px; padding: 10px 14px; border-bottom: 1px solid var(--zephyr-border-soft); }
.category-strip button { padding: 5px 9px; border: 1px solid var(--zephyr-border); border-radius: 3px; background: #fff; color: var(--zephyr-text); font-size: 11px; cursor: pointer; }
.category-strip button:hover, .category-strip button.active { border-color: #4b9a88; background: #eef8f5; color: #216f60; }
.category-strip b { margin-left: 4px; font-family: 'IBM Plex Mono', Consolas, monospace; }
.part-cell, .source-cell, .stock-cell { display: flex; min-width: 0; flex-direction: column; gap: 2px; }
.part-cell strong, .source-cell strong { overflow: hidden; font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
.part-cell span, .source-cell span { overflow: hidden; color: #818a86; font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
.number { font-family: 'IBM Plex Mono', Consolas, monospace; font-variant-numeric: tabular-nums; }
.shipment-number { color: #3c6f64; }
.ledger-heading { display: flex; align-items: baseline; gap: 12px; margin-bottom: 14px; color: #69736f; font-size: 12px; }
.ledger-heading strong { color: var(--zephyr-ink); font-family: 'IBM Plex Mono', Consolas, monospace; font-size: 14px; }
.ledger-tabs :deep(.el-tabs__header) { margin-bottom: 12px; }
.ledger-form { display: grid; gap: 14px; min-height: 300px; padding: 8px 2px; }
.ledger-form-row { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.ledger-form-actions { display: flex; align-items: center; gap: 12px; margin-top: auto; }
.ledger-form-actions span { color: #7b8581; font-size: 11px; }
.reconcile-current { padding: 12px; background: #f4f8f6; color: #68736e; }
.reconcile-current b { margin-left: 6px; color: var(--zephyr-ink); font-size: 18px; }
.ledger-summary { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; margin-bottom: 14px; }
.ledger-summary > div { padding: 10px 12px; border: 1px solid #e1e7e4; background: #fafcfb; }
.ledger-summary span, .ledger-summary b { display: block; }
.ledger-summary span { color: #7a8580; font-size: 11px; }
.ledger-summary b { margin-top: 4px; font-size: 18px; }
.ledger-summary .incoming b, .incoming-text { color: var(--zephyr-primary); }
.ledger-summary .outgoing b, .outgoing-text { color: #b25b42; }
.ledger-footnote { color: #7b8581; font-size: 11px; }
.available { color: #19715f; } .muted { color: #808985; }
.review-part-no { display: inline-block; max-width: 100%; overflow: hidden; font-family: 'IBM Plex Mono', Consolas, monospace; font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
.review-part-no.missing { color: #c83d3d; font-weight: 700; text-decoration: underline dotted; text-underline-offset: 3px; cursor: help; }
.issue-list { display: flex; flex-wrap: wrap; gap: 4px; }
.pagination-row { display: flex; align-items: center; justify-content: space-between; min-height: 54px; padding: 0 14px; border-top: 1px solid var(--zephyr-border-soft); color: #7b8480; font-size: 12px; }
.inventory-tabs :deep(.el-table) { --el-table-border-color: #eaeeec; --el-table-header-bg-color: var(--zephyr-canvas); --el-table-row-hover-bg-color: #f3f8f6; font-size: 12px; }
.inventory-tabs :deep(.el-table th.el-table__cell) { color: #68716d; font-weight: 600; }
.inventory-tabs :deep(.missing-part-row td.el-table__cell) { background: #fff8f7; }
@media (max-width: 1000px) { .summary-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } .toolbar, .review-toolbar { grid-template-columns: 1fr 1fr auto auto; } .toolbar .part-name-filter, .toolbar .part-filter { grid-column: span 1; } }
@media (max-width: 620px) { .workspace-header { align-items: flex-start; } .summary-grid { grid-template-columns: 1fr; } .toolbar, .review-toolbar { display: flex; flex-wrap: wrap; } .toolbar > * { flex: 1 1 140px; } .review-notice div { align-items: flex-start; flex-direction: column; gap: 3px; } }
</style>
