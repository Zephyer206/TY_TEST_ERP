<template>
  <div class="installation-kits-container">
    <nav class="kit-subnav" aria-label="安装包子界面">
      <span class="kit-subnav-parent">安装包</span>
      <button class="kit-subnav-item active" type="button" aria-current="page">FMG 墨西哥</button>
    </nav>

    <header class="archive-toolbar">
      <div class="archive-heading">
        <h1>FMG 墨西哥</h1>
        <span>FMG 售后安装包档案</span>
      </div>

      <label class="archive-search">
        <el-icon aria-hidden="true"><Search /></el-icon>
        <el-input
          v-model="filters.search"
          aria-label="搜索安装包"
          placeholder="搜索 FMG CODE、D code、天悦 PN、天越内部组成、IBI 或组成件"
          clearable
          @keyup.enter="applyFilters"
        />
      </label>

      <div class="archive-filters" aria-label="安装包筛选">
        <el-select v-model="filters.priority" aria-label="优先级" placeholder="优先级" clearable @change="applyFilters">
          <el-option label="P1" :value="1" />
          <el-option label="P2" :value="2" />
          <el-option label="P3" :value="3" />
        </el-select>
        <el-select v-model="filters.documentStatus" aria-label="资料状态" placeholder="资料状态" clearable @change="applyFilters">
          <el-option label="资料完整" value="complete" />
          <el-option label="资料待补" value="incomplete" />
        </el-select>
        <el-select v-model="filters.priceStatus" aria-label="价格状态" placeholder="价格状态" clearable @change="applyFilters">
          <el-option label="价格已确认" value="confirmed" />
          <el-option label="价格待确认" value="missing" />
        </el-select>
        <el-button class="icon-button" :loading="loading" aria-label="刷新列表" title="刷新列表" @click="loadData">
          <el-icon><Refresh /></el-icon>
        </el-button>
      </div>
    </header>

    <div class="archive-summary" aria-live="polite">
      <span>当前 <strong>{{ pagination.total }}</strong> 条</span>
      <span>全部 <strong>{{ summary.totalRecords }}</strong> 条</span>
      <span>已确认价格 <strong>{{ summary.pricedRecords }}</strong> 条</span>
      <span class="pending-price">待确认价格 <strong>{{ summary.missingPriceRecords }}</strong> 条</span>
      <span class="status-summary-ok">图纸通过 <strong>{{ summary.drawingOkRecords }}</strong> 款</span>
      <span class="status-summary-ok">样件通过 <strong>{{ summary.sampleOkRecords }}</strong> 款</span>
      <span class="status-summary-ok">PPAP 通过 <strong>{{ summary.ppapOkRecords }}</strong> 款</span>
    </div>

    <div v-if="loadError" class="archive-error" role="alert">
      <span>{{ loadError }}</span>
      <el-button link @click="loadData">重新加载</el-button>
    </div>

    <el-table
      v-else
      class="kit-table desktop-table"
      :data="kits"
      :row-key="(row: InstallationKitListItem) => row.fmg_code"
      v-loading="loading"
      height="calc(100dvh - 258px)"
      @row-click="openDetail"
    >
      <el-table-column label="优先级" width="66" align="center">
        <template #default="{ row }"><span class="priority-text">P{{ row.priority ?? '-' }}</span></template>
      </el-table-column>
      <el-table-column label="FMG CODE" width="118">
        <template #default="{ row }">
          <button class="code-link mono" type="button" @click.stop="openDetail(row)">{{ row.fmg_code }}</button>
        </template>
      </el-table-column>
      <el-table-column label="D code" width="88">
        <template #default="{ row }"><span class="mono">{{ displayValue(row.d_code) }}</span></template>
      </el-table-column>
      <el-table-column label="天悦 PN" width="104">
        <template #default="{ row }"><span class="mono">{{ displayValue(row.tianyue_pn) }}</span></template>
      </el-table-column>
      <el-table-column label="天越内部组成" min-width="224" show-overflow-tooltip>
        <template #default="{ row }">
          <span v-if="row.component_pairs.length" class="component-inline mono" :title="row.internal_kit_spec || '待补充'">
            <template v-for="(token, index) in componentTokens(row.component_pairs, 'internal')" :key="token.key">
              <span v-if="index" class="component-separator"> + </span>
              <span :class="['component-token', `component-token-${token.status || 'unset'}`]">{{ token.label }}</span>
            </template>
          </span>
          <span v-else class="cell-ellipsis mono">{{ displayValue(row.internal_kit_spec) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="IBI" min-width="198">
        <template #default="{ row }">
          <span v-if="row.component_pairs.length" class="component-inline mono" :title="row.ibi_spec || '待补充'">
            <template v-for="(token, index) in componentTokens(row.component_pairs, 'ibi')" :key="token.key">
              <span v-if="index" class="component-separator"> + </span>
              <span :class="['component-token', `component-token-${token.status || 'unset'}`]">{{ token.label }}</span>
            </template>
          </span>
          <span v-else class="cell-ellipsis mono">{{ displayValue(row.ibi_spec) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="安装包状态" width="178">
        <template #default="{ row }">
          <div
            class="document-status package-status"
            :title="installationKitStatusTooltip(row)"
          >
            <span><i :class="`package-status-dot-${documentStatus(row.drawing_status)}`" aria-hidden="true" />图纸</span>
            <span><i :class="`package-status-dot-${documentStatus(row.sample_status)}`" aria-hidden="true" />样件</span>
            <span><i :class="`package-status-dot-${documentStatus(row.ppap_status)}`" aria-hidden="true" />PPAP</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column width="118" align="center">
        <template #header>
          <span class="price-column-heading">
            <span>价格</span>
            <small>（FCA USD）</small>
          </span>
        </template>
        <template #default="{ row }">
          <span v-if="row.price !== null" :class="['numeric', 'price-value', { 'price-mismatch': row.price_mismatch }]">{{ formatPrice(row.price) }}</span>
          <span v-else class="price-pending">待确认</span>
        </template>
      </el-table-column>
      <el-table-column label="备注" min-width="145" show-overflow-tooltip>
        <template #default="{ row }">{{ displayValue(row.remark) }}</template>
      </el-table-column>
    </el-table>

    <div v-if="!loadError" class="mobile-kit-list" v-loading="loading">
      <button v-for="kit in kits" :key="kit.fmg_code" type="button" class="mobile-kit-row" @click="openDetail(kit)">
        <span class="mobile-kit-main">
          <span class="mono">{{ kit.fmg_code }}</span>
          <span class="mono component-inline" :title="kit.internal_kit_spec || '待补充'">
            <span>天越内部组成 </span>
            <template v-for="(token, index) in componentTokens(kit.component_pairs, 'internal')" :key="token.key">
              <span v-if="index" class="component-separator"> + </span>
              <span :class="['component-token', `component-token-${token.status || 'unset'}`]">{{ token.label }}</span>
            </template>
          </span>
        </span>
        <span class="mobile-kit-meta">
          <span>P{{ kit.priority ?? '-' }} · {{ kit.d_code || '无 D code' }}</span>
           <span v-if="kit.price !== null" :class="['numeric', { 'price-mismatch': kit.price_mismatch }]">USD {{ formatPrice(kit.price) }}</span>
          <span v-else class="price-pending">价格待确认</span>
        </span>
        <el-icon aria-hidden="true"><ArrowRight /></el-icon>
      </button>
      <el-empty v-if="!loading && !kits.length" description="没有符合条件的安装包" />
    </div>

    <footer v-if="!loadError" class="archive-pagination">
      <span>第 {{ pagination.page }} / {{ totalPages }} 页</span>
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :page-sizes="[20, 50, 100]"
        :total="pagination.total"
        layout="sizes, prev, pager, next"
        @size-change="handlePageSizeChange"
        @current-change="loadData"
      />
    </footer>

    <el-drawer
      v-model="drawerOpen"
      class="installation-kit-drawer"
      size="min(1180px, 92vw)"
      :with-header="false"
      append-to-body
      destroy-on-close
    >
      <div v-if="detailLoading" class="drawer-loading" aria-label="正在加载安装包详情">
        <el-skeleton :rows="10" animated />
      </div>

      <template v-else-if="selectedKit">
        <header class="dossier-header">
            <div>
              <div class="dossier-kicker">FMG 墨西哥档案</div>
              <h2 class="mono">{{ selectedKit.fmg_code }}</h2>
            <p class="mono">天悦 PN {{ displayValue(selectedKit.tianyue_pn) }}</p>
          </div>
          <div class="dossier-header-meta">
            <span v-if="selectedKit.price !== null" :class="['dossier-price', 'numeric', { mismatch: selectedKit.price_mismatch }]">
              <small>价格（FCA USD）</small>USD {{ formatPrice(selectedKit.price) }}
            </span>
            <span v-else class="dossier-price missing"><small>价格（FCA USD）</small>待确认</span>
            <el-button v-if="!editing" class="dossier-edit-button" :icon="Edit" @click="startEditing">编辑</el-button>
            <template v-else>
              <el-button class="dossier-edit-button" :loading="saving" :icon="Check" type="primary" @click="saveEditing">保存</el-button>
              <el-button class="dossier-edit-button" :disabled="saving" :icon="Close" @click="cancelEditing">取消</el-button>
            </template>
            <el-button class="icon-button" aria-label="关闭详情" title="关闭详情" @click="drawerOpen = false">
              <el-icon><Close /></el-icon>
            </el-button>
          </div>
        </header>

        <div class="dossier-layout">
          <nav class="dossier-section-nav" aria-label="安装包档案章节">
            <button v-for="section in sections" :key="section.id" type="button" @click="scrollToSection(section.id)">
              <span>{{ section.label }}</span><el-icon><ArrowRight /></el-icon>
            </button>
          </nav>

          <main ref="dossierContent" class="dossier-content">
            <section id="kit-overview" class="dossier-section">
              <h3>主信息</h3>
              <dl class="field-grid">
                <div><dt>FMG CODE</dt><dd v-if="!editing" class="mono">{{ selectedKit.fmg_code }}</dd><el-input v-else v-model="editDraft!.fmg_code" size="small" aria-label="FMG CODE" /></div>
                <div><dt>优先级</dt><dd v-if="!editing">P{{ selectedKit.priority ?? '-' }}</dd><el-select v-else v-model="editDraft!.priority" size="small" clearable aria-label="优先级"><el-option label="P1" :value="1" /><el-option label="P2" :value="2" /><el-option label="P3" :value="3" /></el-select></div>
                <div><dt>D code</dt><dd v-if="!editing" class="mono">{{ displayValue(selectedKit.d_code) }}</dd><el-input v-else v-model="editDraft!.d_code" size="small" aria-label="D code" /></div>
                <div><dt>天悦 PN</dt><dd v-if="!editing" class="mono">{{ displayValue(selectedKit.tianyue_pn) }}</dd><el-input v-else v-model="editDraft!.tianyue_pn" size="small" aria-label="天悦 PN" /></div>
                <div><dt>安装包名称</dt><dd v-if="!editing">{{ displayValue(selectedKit.description) }}</dd><el-input v-else v-model="editDraft!.description" size="small" aria-label="安装包名称" /></div>
                <div class="price-field"><dt>价格（FCA USD）</dt><dd v-if="!editing" :class="['numeric', { mismatch: selectedKit.price_mismatch }]">{{ selectedKit.price !== null ? `USD ${formatPrice(selectedKit.price)}` : '待确认' }}</dd><el-input v-else v-model="editDraft!.price" size="small" type="number" min="0" step="0.0001" aria-label="价格" /></div>
                <div v-if="editing"><dt>币种</dt><el-input v-model="editDraft!.currency" size="small" maxlength="3" aria-label="币种" /></div>
              </dl>
            </section>

            <section id="kit-components" class="dossier-section">
              <h3>组成明细</h3>
              <div class="component-pair-toolbar">
                <div class="component-heading"><h4>IBI ↔ 天悦内部组成</h4><span>{{ selectedKit.component_pairs.length }} 对</span></div>
                <span class="annotation-hint">状态标注只作用于一一对应的零件对</span>
              </div>
              <div class="component-pair-table" role="table" aria-label="IBI 与天悦内部组成对应关系">
                <div class="component-pair-head" role="row"><span>#</span><span>IBI</span><span>天悦内部组成</span><span>状态</span></div>
                <div
                  v-for="pair in selectedKit.component_pairs"
                  :key="`pair-${pair.sequence}`"
                  class="component-pair-row"
                  :class="`match-${pair.match_state}`"
                  role="row"
                >
                  <span class="pair-sequence numeric">{{ pair.sequence }}</span>
                  <span class="pair-cell">
                    <template v-if="editing && pair.ibi">
                      <el-input v-model="componentDrafts[`ibi-${pair.sequence}`].part_number" size="small" :aria-label="`第 ${pair.sequence} 对 IBI 件号`" placeholder="IBI 件号" />
                      <el-input v-model="componentDrafts[`ibi-${pair.sequence}`].raw_text" size="small" :aria-label="`第 ${pair.sequence} 对 IBI 原文`" placeholder="IBI 原文" />
                      <div class="component-edit-meta"><el-input v-model="componentDrafts[`ibi-${pair.sequence}`].description" size="small" placeholder="描述" /><el-input v-model="componentDrafts[`ibi-${pair.sequence}`].quantity" size="small" type="number" min="0" placeholder="数量" /></div>
                    </template>
                    <template v-else>
                      <strong class="mono">{{ componentPartLabel(pair.ibi) }}</strong>
                      <small>{{ componentQuantityLabel(pair.ibi) }}</small>
                    </template>
                  </span>
                  <span class="pair-cell">
                    <template v-if="editing && pair.internal">
                      <el-input v-model="componentDrafts[`internal-${pair.sequence}`].part_number" size="small" :aria-label="`第 ${pair.sequence} 对内部件号`" placeholder="内部件号" />
                      <el-input v-model="componentDrafts[`internal-${pair.sequence}`].raw_text" size="small" :aria-label="`第 ${pair.sequence} 对内部原文`" placeholder="内部原文" />
                      <div class="component-edit-meta"><el-input v-model="componentDrafts[`internal-${pair.sequence}`].description" size="small" placeholder="描述" /><el-input v-model="componentDrafts[`internal-${pair.sequence}`].quantity" size="small" type="number" min="0" placeholder="数量" /></div>
                    </template>
                    <template v-else>
                      <strong class="mono">{{ componentPartLabel(pair.internal) }}</strong>
                      <small>{{ componentQuantityLabel(pair.internal) }}</small>
                    </template>
                  </span>
                  <span class="pair-status">
                    <el-select
                      v-if="pair.match_state === 'paired'"
                      :model-value="pair.status"
                      class="component-status-select"
                      size="small"
                      clearable
                      :loading="Boolean(statusSaving[pair.sequence])"
                      placeholder="未标注"
                      :aria-label="`第 ${pair.sequence} 对组成状态`"
                      @change="handleComponentStatusChange(pair, $event)"
                    >
                      <template #label>
                        <span v-if="pair.status" class="status-option"><i :class="`status-dot status-${pair.status}`" />{{ statusLabel(pair.status) }}</span>
                      </template>
                      <el-option v-for="option in componentStatuses" :key="option.value" :label="option.label" :value="option.value">
                        <span class="status-option"><i :class="`status-dot status-${option.value}`" />{{ option.label }}</span>
                      </el-option>
                    </el-select>
                    <span v-else class="match-state-label">{{ pair.match_state === 'non_part' ? '非零件项' : '待匹配' }}</span>
                  </span>
                </div>
                <div v-if="!selectedKit.component_pairs.length" class="component-empty">暂无可展示的组成明细</div>
              </div>
              <div class="raw-spec-pair">
                <p><span>IBI 原文</span><code v-if="!editing">{{ displayValue(selectedKit.ibi_spec) }}</code><el-input v-else v-model="editDraft!.ibi_spec" type="textarea" :rows="2" aria-label="IBI 原文" /></p>
                <p><span>天悦内部组成原文</span><code v-if="!editing">{{ displayValue(selectedKit.internal_kit_spec) }}</code><el-input v-else v-model="editDraft!.internal_kit_spec" type="textarea" :rows="2" aria-label="天悦内部组成原文" /></p>
              </div>
            </section>

            <section id="kit-documents" class="dossier-section">
              <h3>资料状态</h3>
              <dl class="status-list">
                <div><dt><i :class="`package-status-dot-${documentStatus(selectedKit.drawing_status)}`" />图纸</dt><dd v-if="!editing">{{ displayValue(selectedKit.drawing_status) }}</dd><el-input v-else v-model="editDraft!.drawing_status" size="small" aria-label="图纸状态" /></div>
                <div><dt><i :class="`package-status-dot-${documentStatus(selectedKit.sample_status)}`" />样件</dt><dd v-if="!editing">{{ displayValue(selectedKit.sample_status) }}</dd><el-input v-else v-model="editDraft!.sample_status" size="small" aria-label="样件状态" /></div>
                <div><dt><i :class="`package-status-dot-${documentStatus(selectedKit.ppap_status)}`" />PPAP</dt><dd v-if="!editing">{{ displayValue(selectedKit.ppap_status) }}</dd><el-input v-else v-model="editDraft!.ppap_status" size="small" aria-label="PPAP 状态" /></div>
              </dl>
            </section>

            <section id="kit-remark" class="dossier-section">
              <h3>备注</h3>
              <p v-if="!editing" class="remark-content">{{ displayValue(selectedKit.remark) }}</p>
              <el-input v-else v-model="editDraft!.remark" type="textarea" :rows="4" aria-label="备注" />
            </section>
          </main>

          <aside class="change-history-rail">
            <div class="history-heading"><el-icon><Clock /></el-icon><h3>修改历史</h3></div>
            <ol v-if="selectedKit.change_history.length" class="history-list">
              <li v-for="history in selectedKit.change_history" :key="`${history.created_at}-${history.action}`">
                <time>{{ formatDateTime(history.created_at) }}</time>
                <strong>{{ history.summary }}</strong>
                <span>{{ historyMeta(history) }}</span>
              </li>
            </ol>
            <p v-else class="history-empty">暂无修改记录</p>
          </aside>
        </div>
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { ArrowRight, Check, Clock, Close, Edit, Refresh, Search } from '@element-plus/icons-vue'
import { get, put } from '@/utils/request'

interface InstallationKitComponent {
  source_kind: 'ibi' | 'internal'
  sequence: number
  part_number: string | null
  description: string | null
  quantity: string | null
  raw_text: string
}

type EditableComponent = InstallationKitComponent

type ComponentStatus = 'external_purchase' | 'no_mold' | 'developing'
type InstallationKitStatus = 'ok' | 'not_ok' | 'in_progress'

interface InstallationKitComponentPair {
  sequence: number
  ibi: InstallationKitComponent | null
  internal: InstallationKitComponent | null
  status: ComponentStatus | null
  match_state: 'paired' | 'non_part' | 'unmatched'
  status_updated_at: string | null
}

interface InstallationKitHistory {
  action: string
  summary: string
  changed_fields: string[]
  created_at: string
}

interface InstallationKitListItem {
  fmg_code: string
  description: string | null
  priority: number | null
  d_code: string | null
  tianyue_pn: string | null
  ibi_spec: string | null
  internal_kit_spec: string | null
  component_pairs: InstallationKitComponentPair[]
  drawing_status: string | null
  sample_status: string | null
  ppap_status: string | null
  document_complete: boolean
  price: string | number | null
  price_mismatch: boolean
  currency: string
  remark: string | null
}

interface InstallationKitDetail extends InstallationKitListItem {
  internal_kit_spec: string | null
  components: InstallationKitComponent[]
  component_pairs: InstallationKitComponentPair[]
  change_history: InstallationKitHistory[]
  created_at: string
  updated_at: string
}

interface InstallationKitPage {
  items: InstallationKitListItem[]
  total: number
  page: number
  page_size: number
  summary: {
    total_records: number
    priced_records: number
    missing_price_records: number
    drawing_ok_records: number
    sample_ok_records: number
    ppap_ok_records: number
  }
}

const filters = reactive({
  search: '',
  priority: null as number | null,
  documentStatus: '',
  priceStatus: '',
})
const pagination = reactive({ page: 1, pageSize: 50, total: 0 })
const summary = reactive({
  totalRecords: 0,
  pricedRecords: 0,
  missingPriceRecords: 0,
  drawingOkRecords: 0,
  sampleOkRecords: 0,
  ppapOkRecords: 0,
})
const kits = ref<InstallationKitListItem[]>([])
const loading = ref(false)
const loadError = ref('')
const drawerOpen = ref(false)
const detailLoading = ref(false)
const selectedKit = ref<InstallationKitDetail | null>(null)
const editDraft = ref<InstallationKitDetail | null>(null)
const editing = ref(false)
const saving = ref(false)
const componentDrafts = reactive<Record<string, EditableComponent>>({})
const dossierContent = ref<HTMLElement | null>(null)
let searchTimer: ReturnType<typeof setTimeout> | null = null

const sections = [
  { id: 'kit-overview', label: '主信息' },
  { id: 'kit-components', label: '组成明细' },
  { id: 'kit-documents', label: '资料状态' },
  { id: 'kit-remark', label: '备注' },
]

const componentStatuses: Array<{ value: ComponentStatus; label: string }> = [
  { value: 'external_purchase', label: '外购' },
  { value: 'no_mold', label: '暂无模具' },
  { value: 'developing', label: '开发中' },
]

const totalPages = computed(() => Math.max(1, Math.ceil(pagination.total / pagination.pageSize)))
const statusSaving = reactive<Record<number, boolean>>({})

const cloneDetail = (value: InstallationKitDetail): InstallationKitDetail =>
  JSON.parse(JSON.stringify(value)) as InstallationKitDetail

const startEditing = () => {
  if (!selectedKit.value) return
  editDraft.value = cloneDetail(selectedKit.value)
  Object.keys(componentDrafts).forEach(key => delete componentDrafts[key])
  editDraft.value.components.forEach(component => {
    componentDrafts[`${component.source_kind}-${component.sequence}`] = { ...component }
  })
  editing.value = true
}

const cancelEditing = () => {
  if (saving.value) return
  editDraft.value = null
  Object.keys(componentDrafts).forEach(key => delete componentDrafts[key])
  editing.value = false
}

const saveEditing = async () => {
  if (!selectedKit.value || !editDraft.value) return
  saving.value = true
  const original = selectedKit.value
  const draft = editDraft.value
  const mainPayload = {
    fmg_code: draft.fmg_code,
    description: draft.description,
    priority: draft.priority,
    d_code: draft.d_code,
    tianyue_pn: draft.tianyue_pn,
    ibi_spec: draft.ibi_spec,
    internal_kit_spec: draft.internal_kit_spec,
    drawing_status: draft.drawing_status,
    sample_status: draft.sample_status,
    ppap_status: draft.ppap_status,
    price: draft.price,
    currency: draft.currency,
    remark: draft.remark,
  }
  try {
    const updated = await put<InstallationKitDetail>(
      `/after-sales/installation-kits/${encodeURIComponent(original.fmg_code)}`,
      mainPayload,
    )
    const originalComponents = new Map(
      original.components.map(component => [`${component.source_kind}-${component.sequence}`, component]),
    )
    for (const component of Object.values(componentDrafts)) {
      const previous = originalComponents.get(`${component.source_kind}-${component.sequence}`)
      if (!previous) continue
      const componentChanged = component.part_number !== previous.part_number
        || component.description !== previous.description
        || component.quantity !== previous.quantity
        || component.raw_text !== previous.raw_text
      if (!componentChanged) continue
      await put<InstallationKitComponent>(
        `/after-sales/installation-kits/${encodeURIComponent(updated.fmg_code)}/components/${component.source_kind}/${component.sequence}`,
        {
          part_number: component.part_number,
          description: component.description,
          quantity: component.quantity,
          raw_text: component.raw_text,
        },
      )
    }
    selectedKit.value = await get<InstallationKitDetail>(
      `/after-sales/installation-kits/${encodeURIComponent(updated.fmg_code)}`,
    )
    editDraft.value = null
    Object.keys(componentDrafts).forEach(key => delete componentDrafts[key])
    editing.value = false
    await loadData()
    ElMessage.success('安装包信息已保存，修改历史已记录')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '安装包信息保存失败')
  } finally {
    saving.value = false
  }
}

const loadData = async () => {
  loading.value = true
  loadError.value = ''
  try {
    const response = await get<InstallationKitPage>('/after-sales/installation-kits', {
      search: filters.search.trim() || undefined,
      priority: filters.priority || undefined,
      document_status: filters.documentStatus || undefined,
      price_status: filters.priceStatus || undefined,
      page: pagination.page,
      page_size: pagination.pageSize,
    })
    kits.value = response.items
    pagination.total = response.total
    summary.totalRecords = response.summary.total_records
    summary.pricedRecords = response.summary.priced_records
    summary.missingPriceRecords = response.summary.missing_price_records
    summary.drawingOkRecords = response.summary.drawing_ok_records
    summary.sampleOkRecords = response.summary.sample_ok_records
    summary.ppapOkRecords = response.summary.ppap_ok_records
  } catch (error) {
    loadError.value = error instanceof Error ? error.message : '安装包加载失败'
  } finally {
    loading.value = false
  }
}

const applyFilters = () => {
  pagination.page = 1
  void loadData()
}

const handlePageSizeChange = () => {
  pagination.page = 1
  void loadData()
}

const openDetail = async (row: InstallationKitListItem) => {
  drawerOpen.value = true
  detailLoading.value = true
  selectedKit.value = null
  try {
    selectedKit.value = await get<InstallationKitDetail>(
      `/after-sales/installation-kits/${encodeURIComponent(row.fmg_code)}`
    )
  } catch (error) {
    drawerOpen.value = false
    ElMessage.error(error instanceof Error ? error.message : '安装包详情加载失败')
  } finally {
    detailLoading.value = false
  }
}

const componentPartLabel = (component: InstallationKitComponent | null) => {
  if (!component) return '—'
  return component.part_number || component.raw_text || '未填写'
}

type ComponentSide = 'ibi' | 'internal'

const componentTokens = (
  pairs: InstallationKitComponentPair[],
  side: ComponentSide,
) => pairs
  .filter(pair => pair[side])
  .map(pair => ({
    key: `${side}-${pair.sequence}`,
    label: pair[side]!.raw_text || componentPartLabel(pair[side]),
    status: pair.status,
  }))

const componentQuantityLabel = (component: InstallationKitComponent | null) => {
  if (!component) return '—'
  const quantity = formatQuantity(component.quantity)
  return component.description ? `数量 ${quantity} · ${component.description}` : `数量 ${quantity}`
}

const statusLabel = (status: ComponentStatus | null) =>
  componentStatuses.find(item => item.value === status)?.label || '未标注'

const handleComponentStatusChange = (pair: InstallationKitComponentPair, value: unknown) => {
  const status = typeof value === 'string' && componentStatuses.some(item => item.value === value)
    ? value as ComponentStatus
    : null
  void updateComponentStatus(pair, status)
}

const updateComponentStatus = async (pair: InstallationKitComponentPair, value: ComponentStatus | null) => {
  statusSaving[pair.sequence] = true
  try {
    const updated = await put<InstallationKitComponentPair>(
      `/after-sales/installation-kits/${encodeURIComponent(selectedKit.value!.fmg_code)}/component-pairs/${pair.sequence}`,
      { status: value || null },
    )
    Object.assign(pair, updated)
    ElMessage.success(value ? `已标注：${componentStatuses.find(item => item.value === value)?.label}` : '已清除状态标注')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '状态标注保存失败')
  } finally {
    statusSaving[pair.sequence] = false
  }
}

const scrollToSection = (id: string) => {
  dossierContent.value?.querySelector<HTMLElement>(`#${id}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

const hasValue = (value: string | null | undefined) => Boolean(value?.trim())
const displayValue = (value: string | null | undefined) => hasValue(value) ? value! : '-'
const formatPrice = (value: string | number) => Number(value).toFixed(4)
const formatQuantity = (value: string | null) => {
  if (value === null) return '-'
  const numeric = Number(value)
  return Number.isInteger(numeric) ? String(numeric) : numeric.toFixed(3).replace(/0+$/, '').replace(/\.$/, '')
}
const formatDateTime = (value: string) => new Intl.DateTimeFormat('zh-CN', {
  year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false,
}).format(new Date(value))
const historyMeta = (history: InstallationKitHistory) => {
  if (history.action === 'import_created') return '首次建档'
  if (history.action === 'component_status_updated') return '状态标注更新'
  return `${history.changed_fields.length} 个字段变更`
}
const statusTooltip = (row: InstallationKitListItem) => [
  `图纸：${displayValue(row.drawing_status)}`,
  `样件：${displayValue(row.sample_status)}`,
  `PPAP：${displayValue(row.ppap_status)}`,
].join('\n')

const packageStatusValues = (row: InstallationKitListItem) => [
  row.drawing_status,
  row.sample_status,
  row.ppap_status,
]

const isMissingPackageStatus = (value: string | null) => {
  const normalized = value?.trim().toLowerCase()
  return !normalized || ['-', '—', 'n/a', 'na', '待补充', '待确认'].includes(normalized)
}

const isNegativePackageStatus = (value: string | null) =>
  /(^|[\s:：_-])(not\s*ok|nok|ng|fail(?:ed)?|reject(?:ed)?|不通过|未通过|失败|异常)(?=$|[\s:：_-])/i.test(value?.trim() || '')

const isSubmittedPackageStatus = (value: string | null) =>
  /(re[\s_-]*send|re[\s_-]*sent|send(?:ing)?\s+date|sent\s+date|estimated|待补充|待确认|进行中|pending)/i.test(value?.trim() || '')

const isApprovedPackageStatus = (value: string | null) =>
  /(^|[\s:：_-])(ok|approved|approval\s+date|通过|已通过)(?=$|[\s:：_-])/i.test(value?.trim() || '')

const documentStatus = (value: string | null): InstallationKitStatus => {
  if (isNegativePackageStatus(value)) return 'not_ok'
  if (isMissingPackageStatus(value)) return 'in_progress'
  if (isSubmittedPackageStatus(value)) return 'in_progress'
  if (isApprovedPackageStatus(value)) return 'ok'
  // 对 Excel 中未定义的新文本采取保守判断，避免把“有日期”误当成已通过。
  return 'in_progress'
}

const installationKitStatus = (row: InstallationKitListItem): InstallationKitStatus => {
  const statuses = packageStatusValues(row).map(documentStatus)
  if (statuses.some(status => status === 'not_ok')) return 'not_ok'
  if (statuses.every(status => status === 'ok')) return 'ok'
  return 'in_progress'
}

const installationKitStatusLabel = (row: InstallationKitListItem) => ({
  ok: 'OK',
  not_ok: 'NOT OK',
  in_progress: '进行中',
}[installationKitStatus(row)])

const installationKitStatusTooltip = (row: InstallationKitListItem) =>
  `安装包状态：${installationKitStatusLabel(row)}\n${statusTooltip(row)}`

watch(() => filters.search, () => {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(applyFilters, 280)
})

onMounted(loadData)
onBeforeUnmount(() => {
  if (searchTimer) clearTimeout(searchTimer)
})
</script>

<style scoped>
.installation-kits-container {
  min-width: 0;
  padding-top: 12px;
  color: var(--zephyr-ink, #26353a);
  font-size: 13px;
  letter-spacing: 0;
}

.kit-subnav {
  display: flex;
  align-items: center;
  gap: 4px;
  min-height: 30px;
  margin-bottom: 4px;
  border-bottom: 1px solid #e6ebe9;
}
.kit-subnav-parent { margin-right: 8px; color: #718086; font-size: 11px; font-weight: 650; }
.kit-subnav-item { height: 30px; padding: 0 9px; border: 0; border-bottom: 2px solid transparent; background: transparent; color: #68747b; font: inherit; font-size: 12px; cursor: default; }
.kit-subnav-item.active { border-bottom-color: var(--zephyr-primary, #176b5a); color: var(--zephyr-primary, #176b5a); font-weight: 650; }

.archive-toolbar {
  display: grid;
  grid-template-columns: minmax(150px, .55fr) minmax(300px, 1.4fr) auto;
  align-items: center;
  gap: 12px;
  min-height: 52px;
  padding: 4px 0 8px;
}

.archive-heading { min-width: 0; }
.archive-heading h1 { margin: 0; font-size: 20px; font-weight: 650; line-height: 1.25; letter-spacing: 0; }
.archive-heading span { color: #7b898e; font-size: 11px; }
.archive-search { display: flex; align-items: center; min-width: 0; height: 32px; padding: 0 10px; border: 1px solid var(--zephyr-border, #d8e1df); border-radius: 4px; background: #fff; color: #7b898e; }
.archive-search:focus-within { border-color: var(--zephyr-primary, #176b5a); box-shadow: 0 0 0 3px rgba(23, 107, 90, .1); }
.archive-search :deep(.el-input__wrapper) { padding: 0 0 0 7px; box-shadow: none; }
.archive-filters { display: flex; align-items: center; gap: 8px; }
.archive-filters .el-select { width: 112px; }
.archive-filters :deep(.el-select__wrapper) { min-height: 32px; border-radius: 4px; box-shadow: 0 0 0 1px var(--zephyr-border, #d8e1df) inset; }
.icon-button { width: 32px; height: 32px; padding: 0; border-radius: 4px; }

.archive-summary { display: flex; align-items: center; gap: 18px; min-height: 28px; color: #718086; font-size: 11px; font-variant-numeric: tabular-nums; }
.archive-summary strong { color: #435158; font-weight: 650; }
.archive-summary .pending-price, .price-pending { color: #a26b1c; }
.archive-summary .status-summary-ok { color: #2f8768; }
.archive-error { display: flex; align-items: center; justify-content: space-between; min-height: 48px; padding: 0 14px; border: 1px solid #e5c7c4; background: #fff8f7; color: #a54843; }

.kit-table { width: 100%; }
.kit-table :deep(.el-table__header th.el-table__cell) { height: 34px; padding: 0 8px; font-size: 11px; font-weight: 600; letter-spacing: 0; }
.kit-table :deep(.el-table__body td.el-table__cell) { height: 42px; padding: 0 8px; }
.kit-table :deep(.cell) { padding: 0; line-height: 1.35; }
.kit-table :deep(.el-table__row) { cursor: pointer; }
.priority-text { color: #4f5e64; font-weight: 700; font-variant-numeric: tabular-nums; }
.mono { font-family: "IBM Plex Mono", "Cascadia Mono", Consolas, monospace; font-variant-numeric: tabular-nums slashed-zero; }
.numeric { font-variant-numeric: tabular-nums; }
.code-link { padding: 5px 0; border: 0; background: transparent; color: var(--zephyr-primary, #176b5a); font-size: 12px; font-weight: 650; cursor: pointer; text-decoration: none; }
.code-link:focus-visible { outline: 2px solid rgba(23, 107, 90, .45); outline-offset: 2px; }
.cell-ellipsis { display: block; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.component-inline { display: block; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.component-token-external_purchase { color: #2f73b6; }
.component-token-no_mold { color: #cf2f2f; }
.component-token-developing { color: #b27a00; }
.component-separator { color: #89959a; }
.document-status { display: flex; align-items: center; gap: 10px; white-space: nowrap; }
.document-status span, .status-list dt { display: inline-flex; align-items: center; gap: 5px; }
.document-status i, .status-list i { width: 7px; height: 7px; border-radius: 50%; background: #c48b42; }
.document-status i.ready, .status-list i.ready { background: #3f876b; }
.package-status-dot-ok { background: #3f9a76 !important; }
.package-status-dot-not_ok { background: #e53935 !important; }
.package-status-dot-in_progress { background: #d4a017 !important; }
.price-value { display: block; color: #36474e; font-weight: 600; text-align: center; }
.price-value.price-mismatch, .dossier-price.mismatch, .price-field dd.mismatch { color: #d33b35; }
.price-pending { display: block; font-size: 11px; text-align: center; }
.price-column-heading { display: inline-grid; justify-items: center; gap: 1px; line-height: 1.15; white-space: nowrap; text-align: center; }
.price-column-heading small { color: #718086; font-size: 10px; font-weight: 600; }

.archive-pagination { display: flex; align-items: center; justify-content: space-between; min-height: 42px; color: #758389; font-size: 11px; font-variant-numeric: tabular-nums; }
.archive-pagination :deep(.el-pagination) { padding: 0; }
.mobile-kit-list { display: none; }

:global(.installation-kit-drawer .el-drawer__body) { padding: 0; overflow: hidden; background: #f5f7f6; }
.drawer-loading { padding: 24px; }
.dossier-header { display: flex; align-items: center; justify-content: space-between; min-height: 86px; padding: 12px 20px; border-bottom: 1px solid #d8e1df; background: #fff; }
.dossier-kicker { margin-bottom: 2px; color: #718086; font-size: 11px; }
.dossier-header h2 { margin: 0; color: #25363b; font-size: 20px; font-weight: 650; letter-spacing: 0; }
.dossier-header p { margin: 3px 0 0; color: #6f7e84; font-size: 12px; }
.dossier-header-meta { display: flex; align-items: center; gap: 16px; }
.dossier-edit-button { min-height: 30px; padding: 0 10px; border-radius: 4px; }
.dossier-price { display: grid; justify-items: end; color: #25363b; font-size: 17px; font-weight: 650; }
.dossier-price small { color: #7b898e; font-size: 10px; font-weight: 500; }
.dossier-price.missing { color: #a26b1c; }
.dossier-layout { display: grid; grid-template-columns: 148px minmax(0, 1fr) 252px; height: calc(100dvh - 86px); min-height: 0; }
.dossier-section-nav { padding: 16px 10px; border-right: 1px solid #d8e1df; background: #f8faf9; }
.dossier-section-nav button { display: flex; align-items: center; justify-content: space-between; width: 100%; min-height: 34px; padding: 0 9px; border: 0; border-left: 2px solid transparent; background: transparent; color: #637278; font: inherit; font-size: 12px; text-align: left; cursor: pointer; }
.dossier-section-nav button:hover, .dossier-section-nav button:focus-visible { border-left-color: #176b5a; background: #eaf2ef; color: #176b5a; outline: none; }
.dossier-section-nav .el-icon { font-size: 11px; }
.dossier-content { min-width: 0; padding: 16px; overflow-y: auto; scrollbar-gutter: stable; scroll-behavior: smooth; }
.dossier-section { scroll-margin-top: 12px; margin-bottom: 12px; padding: 14px 16px; border: 1px solid #d8e1df; border-radius: 5px; background: #fff; }
.dossier-section h3 { margin: 0 0 12px; color: #2e4046; font-size: 14px; font-weight: 650; letter-spacing: 0; }
.field-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 1px; margin: 0; background: #e0e6e4; }
.field-grid div { min-width: 0; min-height: 62px; padding: 9px 10px; background: #fff; }
.field-grid .wide-field { grid-column: span 2; }
.field-grid .price-field { grid-column: span 3; }
.field-grid dt, .status-list dt { margin-bottom: 5px; color: #7a888d; font-size: 10px; }
.field-grid dd, .status-list dd { margin: 0; overflow-wrap: anywhere; color: #34464c; }
.field-grid :deep(.el-input__wrapper), .field-grid :deep(.el-select__wrapper), .status-list :deep(.el-input__wrapper) { min-height: 28px; padding: 0 7px; border-radius: 3px; box-shadow: 0 0 0 1px #d4dfdc inset; }
.field-grid :deep(.el-textarea__inner), .status-list :deep(.el-textarea__inner) { padding: 6px 7px; border-radius: 3px; }
.component-heading { display: flex; align-items: baseline; justify-content: space-between; margin-bottom: 6px; }
.component-heading h4 { margin: 0; font-size: 12px; font-weight: 650; }
.component-heading span { color: #7b898e; font-size: 10px; font-variant-numeric: tabular-nums; }
.raw-spec { margin: 0 0 8px; padding: 8px 10px; background: #f4f7f6; color: #4d5d63; font-size: 11px; line-height: 1.55; overflow-wrap: anywhere; }
.component-pair-toolbar { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }
.annotation-hint { color: #839095; font-size: 10px; }
.component-pair-table { border-top: 1px solid #dce4e2; }
.component-pair-head, .component-pair-row { display: grid; grid-template-columns: 28px minmax(150px, 1fr) minmax(180px, 1.1fr) 116px; gap: 8px; min-height: 46px; align-items: center; padding: 0 8px; border-bottom: 1px solid #e3e9e7; }
.component-pair-head { min-height: 30px; background: #edf2f1; color: #718086; font-size: 10px; font-weight: 600; }
.component-pair-row { font-size: 12px; }
.component-pair-row > span { min-width: 0; }
.component-pair-row.match-non_part, .component-pair-row.match-unmatched { background: #fafbfa; color: #879398; }
.pair-sequence { color: #7b898e; font-size: 11px; }
.pair-cell { display: grid; min-width: 0; gap: 2px; }
.pair-cell strong { overflow: hidden; color: #33464c; font-size: 11px; font-weight: 550; text-overflow: ellipsis; white-space: nowrap; }
.pair-cell small { overflow: hidden; color: #89959a; font-size: 10px; text-overflow: ellipsis; white-space: nowrap; }
.component-edit-meta { display: grid; grid-template-columns: minmax(0, 1fr) 72px; gap: 4px; }
.component-edit-meta :deep(.el-input__wrapper) { min-height: 26px; padding: 0 6px; border-radius: 3px; box-shadow: 0 0 0 1px #d4dfdc inset; }
.pair-status { display: flex; min-width: 0; justify-content: flex-end; }
.component-status-select { width: 108px; }
.component-status-select :deep(.el-select__wrapper) { min-height: 28px; border-radius: 4px; box-shadow: 0 0 0 1px #d8e1df inset; }
.status-option { display: inline-flex; align-items: center; gap: 6px; }
.status-dot { display: inline-block; width: 7px; height: 7px; border-radius: 50%; }
.status-external_purchase { background: #3e82c4; }
.status-no_mold { background: #e53935; }
.status-developing { background: #d4a017; }
.match-state-label { color: #8a969b; font-size: 10px; white-space: nowrap; }
.raw-spec-pair { display: grid; gap: 4px; margin-top: 10px; }
.raw-spec-pair p { display: grid; grid-template-columns: 114px minmax(0, 1fr); gap: 8px; margin: 0; color: #839095; font-size: 10px; }
.raw-spec-pair code { overflow-wrap: anywhere; color: #4d5d63; font-family: "IBM Plex Mono", "Cascadia Mono", Consolas, monospace; font-size: 10px; }
.component-empty { padding: 12px 8px; color: #8b979b; font-size: 11px; }
.status-list { display: grid; gap: 0; margin: 0; border-top: 1px solid #e1e7e5; }
.status-list div { display: grid; grid-template-columns: 110px minmax(0, 1fr); min-height: 42px; align-items: center; border-bottom: 1px solid #e1e7e5; }
.status-list dt { margin: 0; }
.remark-content { min-height: 32px; margin: 0; color: #44565c; line-height: 1.6; white-space: pre-wrap; }
.change-history-rail { margin: 0; padding: 16px 14px; border: 0; border-left: 1px solid #d8e1df; background: #f8faf9; overflow-y: auto; scrollbar-gutter: stable; }
.history-heading { display: flex; align-items: center; gap: 7px; margin-bottom: 14px; color: #405158; }
.history-heading h3 { margin: 0; font-size: 13px; font-weight: 650; }
.history-list { margin: 0; padding: 0 0 0 13px; list-style: none; border-left: 1px solid #cbd7d4; }
.history-list li { position: relative; display: grid; gap: 3px; padding: 0 0 18px 13px; }
.history-list li::before { position: absolute; top: 3px; left: -4px; width: 7px; height: 7px; border: 2px solid #f8faf9; border-radius: 50%; background: #176b5a; content: ''; }
.history-list time { color: #7d8a8f; font-size: 10px; font-variant-numeric: tabular-nums; }
.history-list strong { color: #405158; font-size: 11px; font-weight: 600; }
.history-list span, .history-empty { color: #829095; font-size: 10px; }

@media (max-width: 1120px) {
  .archive-toolbar { grid-template-columns: minmax(140px, .45fr) minmax(260px, 1fr); }
  .archive-filters { grid-column: 1 / -1; justify-content: flex-end; }
  .kit-table { --kit-table-offset: 302px; }
  .dossier-layout { grid-template-columns: 128px minmax(0, 1fr) 220px; }
  .field-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}

@media (max-width: 760px) {
  .installation-kits-container { padding-top: 8px; }
  .archive-toolbar { grid-template-columns: 1fr; gap: 8px; }
  .archive-heading span { display: none; }
  .archive-search { width: 100%; }
  .archive-filters { grid-column: auto; flex-wrap: wrap; justify-content: flex-start; overflow: visible; }
  .archive-filters .el-select { flex: 0 0 calc(50% - 4px); width: auto; }
  .archive-summary { gap: 12px; overflow-x: auto; white-space: nowrap; }
  .archive-summary span:nth-child(2), .archive-summary span:nth-child(3) { display: none; }
  .desktop-table { display: none; }
  .mobile-kit-list { display: grid; border-top: 1px solid #d8e1df; }
  .mobile-kit-row { display: grid; grid-template-columns: minmax(0, 1fr) auto 18px; align-items: center; gap: 8px; min-height: 66px; padding: 8px 4px; border: 0; border-bottom: 1px solid #dfe6e4; background: transparent; color: #35464c; font: inherit; text-align: left; }
  .mobile-kit-row:focus-visible { outline: 2px solid rgba(23, 107, 90, .5); outline-offset: -2px; }
  .mobile-kit-main, .mobile-kit-meta { display: grid; min-width: 0; gap: 3px; }
  .mobile-kit-main span:first-child { color: #176b5a; font-weight: 650; }
  .mobile-kit-main span:last-child, .mobile-kit-meta span:first-child { overflow: hidden; color: #748288; font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
  .mobile-kit-meta { justify-items: end; font-size: 11px; }
  .archive-pagination { align-items: flex-start; flex-direction: column; gap: 4px; padding: 8px 0; }
  .archive-pagination :deep(.el-pagination__sizes) { display: none; }
  :global(.installation-kit-drawer) { width: 100% !important; }
  .dossier-header { align-items: flex-start; min-height: 106px; padding: 12px; }
  .dossier-header p { max-width: 52vw; }
  .dossier-header-meta { gap: 8px; }
  .dossier-price { font-size: 14px; }
  .dossier-layout { display: block; height: calc(100dvh - 106px); overflow-y: auto; }
  .dossier-section-nav { position: sticky; top: 0; z-index: 2; display: flex; flex-wrap: wrap; gap: 2px; padding: 6px 8px; border-right: 0; border-bottom: 1px solid #d8e1df; overflow: visible; }
  .dossier-section-nav button { flex: 1 1 calc(25% - 2px); justify-content: center; min-height: 36px; border-left: 0; border-bottom: 2px solid transparent; }
  .dossier-section-nav button:hover, .dossier-section-nav button:focus-visible { border-left-color: transparent; border-bottom-color: #176b5a; }
  .dossier-section-nav .el-icon { display: none; }
  .dossier-content { padding: 8px; overflow: visible; }
  .dossier-section { padding: 12px; }
  .field-grid { grid-template-columns: 1fr 1fr; }
  .field-grid .wide-field { grid-column: 1 / -1; }
  .field-grid .price-field { grid-column: 1 / -1; }
  .component-pair-toolbar { align-items: flex-start; flex-direction: column; gap: 2px; }
  .component-pair-head, .component-pair-row { grid-template-columns: 20px minmax(0, 1fr) minmax(0, 1fr) 88px; gap: 4px; padding: 0 4px; }
  .component-pair-row { min-height: 52px; }
  .pair-cell strong { font-size: 10px; }
  .pair-cell small { font-size: 9px; }
  .component-status-select { width: 84px; }
  .component-status-select :deep(.el-select__wrapper) { padding: 0 6px; }
  .raw-spec-pair p { grid-template-columns: 88px minmax(0, 1fr); }
  .change-history-rail { margin: 0 8px 12px; padding: 14px; border: 1px solid #d8e1df; }
}

@media (prefers-reduced-motion: reduce) {
  .dossier-content { scroll-behavior: auto; }
}
</style>
