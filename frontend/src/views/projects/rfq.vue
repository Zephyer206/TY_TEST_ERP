<template>
  <div class="project-list-page">
    <div class="list-view-toolbar">
      <div class="list-title-block">
        <div><h1>{{ technicalMode ? '技术审核 · 询价' : '询价' }}</h1><p class="list-caption">{{ technicalMode ? '审核客户询价资料，确认工艺可行性后进入报价' : '登记客户询价，跟踪资料和技术评审进度' }}</p></div>
        <el-button type="primary" :icon="Plus" @click="openCreate">登记询价</el-button>
      </div>
      <div class="search-control"><el-icon><Search /></el-icon><el-input v-model="keyword" placeholder="搜索询价单、客户或项目" clearable /></div>
    </div>
    <div class="table-meta"><span>{{ filtered.length }} 条询价</span><span>每个询价可包含多个零件，评审通过后进入报价页</span></div>
    <el-table :data="filtered" stripe v-loading="loading">
      <el-table-column prop="id" label="询价单号" width="150" /><el-table-column prop="customer" label="客户" width="140" /><el-table-column prop="project" label="客户项目" min-width="170" /><el-table-column prop="receivedAt" label="收到日期" width="120" /><el-table-column prop="dueAt" label="报价截止" width="120" /><el-table-column prop="parts" label="零件数" width="90" /><el-table-column prop="owner" label="负责人" width="100" />
      <el-table-column label="技术评审" width="120"><template #default="{ row }"><el-tag size="small" :type="row.technicalReview === '已完成' ? 'success' : row.technicalReview === '待补充' ? 'danger' : 'warning'">{{ row.technicalReview }}</el-tag></template></el-table-column>
      <el-table-column label="附件" width="90"><template #default="{ row }">{{ row.attachments.length }} 个</template></el-table-column>
      <el-table-column label="操作" width="110"><template #default="{ row }"><el-button link type="primary" @click="openDetail(row)">查看询价</el-button></template></el-table-column>
    </el-table>
    <el-dialog v-model="dialog" title="登记客户询价" width="560px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="客户" required>
          <div class="customer-picker">
            <el-select v-model="form.customerId" filterable clearable :loading="customersLoading" placeholder="选择现有客户或新建客户" @change="handleCustomerChange">
              <el-option v-for="customer in customers" :key="customer.id" :label="customer.name" :value="customer.id" />
            </el-select>
            <el-button type="primary" plain @click="customerDialog = true">新建客户</el-button>
          </div>
        </el-form-item>
        <el-form-item label="客户项目（选填）"><el-input v-model="form.project" placeholder="没有项目名也可以先登记询价" /></el-form-item>
        <el-form-item label="报价截止"><el-date-picker v-model="form.dueAt" type="date" value-format="YYYY-MM-DD" style="width:100%" /></el-form-item>
        <el-form-item label="询价文件" required>
          <el-upload v-model:file-list="form.attachments" :auto-upload="false" multiple :limit="10" accept=".pdf,.xls,.xlsx,.doc,.docx,.zip,.rar,.dwg,.jpg,.jpeg,.png" :on-exceed="handleUploadExceed">
            <el-button type="primary" plain>选择文件</el-button>
            <template #tip><div class="upload-tip">请上传客户图纸、技术要求或其他评审资料，最多 10 个文件。</div></template>
          </el-upload>
        </el-form-item>
        <el-form-item label="技术备注"><el-input v-model="form.remark" type="textarea" :rows="3" placeholder="说明技术评审重点、特殊工艺或客户要求" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="dialog = false">取消</el-button><el-button type="primary" :loading="creating" @click="create">保存并提交技术评审</el-button></template>
    </el-dialog>
    <el-dialog v-model="customerDialog" title="新建客户" width="460px">
      <el-form :model="customerForm" label-width="90px">
        <el-form-item label="客户名称" required><el-input v-model="customerForm.name" placeholder="请输入客户全称" /></el-form-item>
        <el-form-item label="客户编码"><el-input v-model="customerForm.sheet_key" placeholder="选填" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="customerDialog = false">取消</el-button><el-button type="primary" :loading="customerSaving" @click="createCustomer">保存客户</el-button></template>
    </el-dialog>
    <el-dialog v-model="detailVisible" :title="selectedRfq ? selectedRfq.id + ' · 技术评审资料' : '技术评审资料'" width="min(960px, 94vw)">
      <template v-if="selectedRfq">
        <div class="review-summary"><span>{{ selectedRfq.customer }} · {{ selectedRfq.project }}</span><el-tag size="small" type="warning">{{ selectedRfq.technicalReview }}</el-tag></div>
        <div class="attachment-heading"><strong>询价附件</strong><span>{{ selectedRfq.attachments.length }} 个文件</span></div>
        <ul v-if="selectedRfq.attachments.length" class="attachment-list"><li v-for="file in selectedRfq.attachments" :key="file.name"><a :href="file.url" target="_blank" rel="noopener">{{ file.name }}</a><small>{{ formatSize(file.size) }}</small></li></ul>
        <el-empty v-else description="暂未上传询价文件" :image-size="64" />
        <section class="technical-sheet">
          <div class="technical-heading">
            <div><strong>技术分析结果</strong><span>按零件填写，作为后续报价的依据</span></div>
            <el-button v-if="selectedRfq.technicalReview !== '已完成'" size="small" type="primary" plain @click="addTechnicalItem">新增零件</el-button>
          </div>
          <div class="technical-legend">TWP：料厚、宽度、步距，单位均为 mm；利用率、冲床吨位、模具费和模具周期由技术分析后提供。</div>
          <div v-for="(item, index) in selectedRfq.technicalItems" :key="item.key" class="technical-item">
            <div class="technical-item-heading"><strong>零件 {{ index + 1 }}</strong><el-button v-if="selectedRfq.technicalReview !== '已完成'" link type="danger" size="small" @click="removeTechnicalItem(index)">移除</el-button></div>
            <div class="technical-grid">
              <label><span>{{ partNoLabel(item) }}</span><el-input v-model="item.customerPartNo" size="small" :placeholder="partNoLabel(item)" :disabled="selectedRfq.technicalReview === '已完成'" /></label>
              <label v-if="item.isLeftRightPair"><span>零件号2</span><el-input v-model="item.customerPartNo2" size="small" placeholder="零件号2" :disabled="selectedRfq.technicalReview === '已完成'" /></label>
              <label><span>零件名称</span><el-input v-model="item.partName" size="small" placeholder="零件名称" :disabled="selectedRfq.technicalReview === '已完成'" /></label>
              <label><span>材料</span><el-input v-model="item.material" size="small" placeholder="如 SUS301" :disabled="selectedRfq.technicalReview === '已完成'" /></label>
              <label><span>料厚 / T (mm)</span><el-input v-model="item.thickness" size="small" placeholder="mm" :disabled="selectedRfq.technicalReview === '已完成'" /></label>
              <label><span>宽度 / W (mm)</span><el-input v-model="item.width" size="small" placeholder="mm" :disabled="selectedRfq.technicalReview === '已完成'" /></label>
              <label><span>步距 / P (mm)</span><el-input v-model="item.pitch" size="small" placeholder="mm" :disabled="selectedRfq.technicalReview === '已完成'" /></label>
              <label><span>材料利用率 (%)</span><el-input v-model="item.utilization" size="small" placeholder="%" :disabled="selectedRfq.technicalReview === '已完成'" /></label>
              <label><span>冲床吨位 (t)</span><el-input v-model="item.pressTonnage" size="small" placeholder="吨" :disabled="selectedRfq.technicalReview === '已完成'" /></label>
              <label><span>穴数</span><el-input v-model="item.cavityCount" size="small" placeholder="如 1、2" :disabled="selectedRfq.technicalReview === '已完成'" /></label>
              <label v-if="Number(item.cavityCount) >= 2"><span>一出二左右件</span><el-switch v-model="item.isLeftRightPair" size="small" :disabled="selectedRfq.technicalReview === '已完成'" @change="handlePairToggle(item)" /></label>
              <label><span>模具费 (元)</span><el-input v-model="item.toolingCost" size="small" placeholder="报价用" :disabled="selectedRfq.technicalReview === '已完成'" /></label>
              <label><span>模具周期 (天)</span><el-input v-model="item.toolingLeadTime" size="small" placeholder="天" :disabled="selectedRfq.technicalReview === '已完成'" /></label>
            </div>
          </div>
          <div class="technical-footer">
            <span>{{ technicalDataCount }} 个零件已填写技术资料<span v-if="leftRightPairCount">，{{ leftRightPairCount }} 件标记为一出二左右件</span><em v-if="leftRightPairInvalid">一出二左右件必须填写零件号1和零件号2</em></span>
            <el-button v-if="selectedRfq.technicalReview !== '已完成'" size="small" type="primary" @click="saveTechnicalData">保存技术资料</el-button>
          </div>
        </section>
        <p class="review-note">资料已随询价单提交给技术评审，技术资料完整后才进入报价组。</p>
        <div class="review-actions" v-if="selectedRfq.technicalReview !== '已完成'">
          <el-button type="danger" plain @click="reviewRfq('待补充')">退回补充资料</el-button>
          <el-button type="primary" :disabled="!canPassTechnicalReview" @click="reviewRfq('已完成')">通过技术评审</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { Plus, Search } from '@element-plus/icons-vue'
import { ElMessage, type UploadUserFile } from 'element-plus'
import { persistWorkspace, projects } from './data'
import { customersApi } from '@/api/customers'
import { customerInquiriesApi, type CustomerInquiryRecord } from '@/api/customerInquiries'

const route = useRoute()
const technicalMode = computed(() => route.query.review === 'technical')
const keyword = ref('')
const dialog = ref(false)
const form = reactive({ customerId: null as number | null, customer: '', project: '', dueAt: '', remark: '', attachments: [] as UploadUserFile[] })
const customers = ref<Array<{ id: number; name: string; sheet_key?: string | null }>>([])
const customersLoading = ref(false)
const customerDialog = ref(false)
const customerSaving = ref(false)
const customerForm = reactive({ name: '', sheet_key: '' })
const detailVisible = ref(false)
const loading = ref(false)
const creating = ref(false)
type InquiryView = {
  backendId: number
  id: string
  projectId?: string
  customer: string
  project: string
  receivedAt: string
  dueAt: string
  parts: number
  status: string
  owner: string
  technicalReview: CustomerInquiryRecord['technical_review']
  technicalReviewNote?: string | null
  attachments: CustomerInquiryRecord['attachments']
  technicalItems: TechnicalReviewItem[]
}
type TechnicalReviewItem = {
  key: string
  customerPartNo: string
  customerPartNo2: string
  partName: string
  material: string
  thickness: string
  width: string
  pitch: string
  utilization: string
  pressTonnage: string
  cavityCount: string
  isLeftRightPair: boolean
  pairGroupKey?: string
  pairIndex?: 1 | 2
  toolingCost: string
  toolingLeadTime: string
}
const inquiries = ref<InquiryView[]>([])
const selectedRfq = ref<InquiryView | null>(null)
const technicalReviewStore = reactive<Record<number, TechnicalReviewItem[]>>({})
const createTechnicalItem = (): TechnicalReviewItem => ({
  key: `technical-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
  customerPartNo: '',
  customerPartNo2: '',
  partName: '',
  material: '',
  thickness: '',
  width: '',
  pitch: '',
  utilization: '',
  pressTonnage: '',
  cavityCount: '',
  isLeftRightPair: false,
  toolingCost: '',
  toolingLeadTime: '',
})
const normalizeTechnicalItem = (item: Partial<TechnicalReviewItem>): TechnicalReviewItem => ({
  ...createTechnicalItem(),
  ...item,
  key: item.key || `technical-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
  isLeftRightPair: Boolean(item.isLeftRightPair),
  pairGroupKey: item.pairGroupKey,
  pairIndex: item.pairIndex === 1 || item.pairIndex === 2 ? item.pairIndex : undefined,
})
const normalizeTechnicalItems = (items: TechnicalReviewItem[]) => {
  const normalized = items.map(normalizeTechnicalItem)
  const collapsed: TechnicalReviewItem[] = []
  normalized.forEach(item => {
    if (!item.pairGroupKey) {
      collapsed.push(item)
      return
    }
    const first = normalized.find(candidate => candidate.pairGroupKey === item.pairGroupKey && candidate.pairIndex === 1) || item
    if (collapsed.includes(first)) return
    const second = normalized.find(candidate => candidate.pairGroupKey === item.pairGroupKey && candidate !== first)
    first.isLeftRightPair = true
    first.pairIndex = undefined
    first.pairGroupKey = undefined
    if (second?.customerPartNo?.trim()) first.customerPartNo2 = second.customerPartNo
    collapsed.push(first)
  })
  return collapsed
}
const restoreTechnicalReviewStore = () => {
  // Technical review data is loaded from the inquiry API.
}
restoreTechnicalReviewStore()
const toView = (record: CustomerInquiryRecord): InquiryView => ({
  backendId: record.id,
  id: record.inquiry_no,
  customer: record.customer,
  project: record.project_name || '待命名项目',
  receivedAt: (record.received_at || record.created_at || '').slice(0, 10) || '-',
  dueAt: record.due_date || '-',
  parts: record.technical_data?.length || 0,
  status: record.status,
  owner: record.owner_name,
  technicalReview: record.technical_review,
  technicalReviewNote: record.technical_review_note,
  attachments: record.attachments || [],
  technicalItems: normalizeTechnicalItems((record.technical_data || []) as TechnicalReviewItem[]),
})
const loadInquiries = async () => {
  loading.value = true
  try {
    const rows = await customerInquiriesApi.list({ search: keyword.value || undefined })
    inquiries.value = rows.map(toView)
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '获取询价列表失败')
  } finally {
    loading.value = false
  }
}
const filtered = computed(() => inquiries.value.filter(row => {
  const text = (row.id + ' ' + row.customer + ' ' + row.project).toLowerCase()
  const matchesTechnicalQueue = !technicalMode.value || row.technicalReview !== '已完成'
  return matchesTechnicalQueue && (!keyword.value || text.includes(keyword.value.toLowerCase()))
}))
const loadCustomers = async () => {
  customersLoading.value = true
  try {
    const response = await customersApi.list<{ items?: Array<{ id: number; name: string; sheet_key?: string | null }> }>({ limit: 200, is_active: true })
    customers.value = response.items || []
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '获取客户列表失败')
  } finally {
    customersLoading.value = false
  }
}
const openCreate = () => { dialog.value = true; void loadCustomers() }
const handleCustomerChange = (id: number | null) => { form.customer = customers.value.find(customer => customer.id === id)?.name || '' }
const createCustomer = async () => {
  const name = customerForm.name.trim()
  if (!name) return ElMessage.warning('请输入客户名称')
  customerSaving.value = true
  try {
    const created = await customersApi.create<{ id: number; name: string; sheet_key?: string | null }>(customerForm)
    customers.value = [...customers.value, created].sort((a, b) => a.name.localeCompare(b.name, 'zh-CN'))
    form.customerId = created.id
    form.customer = created.name
    Object.assign(customerForm, { name: '', sheet_key: '' })
    customerDialog.value = false
    ElMessage.success('客户已创建并已选中')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '创建客户失败')
  } finally {
    customerSaving.value = false
  }
}
const handleUploadExceed = () => ElMessage.warning('最多上传 10 个询价文件')
const formatSize = (size: number) => size >= 1024 * 1024 ? (size / 1024 / 1024).toFixed(1) + ' MB' : Math.max(1, Math.round(size / 1024)) + ' KB'
const technicalDataCount = computed(() => selectedRfq.value?.technicalItems.filter(item => item.partName.trim() || item.customerPartNo.trim() || item.customerPartNo2.trim()).length || 0)
const leftRightPairCount = computed(() => (selectedRfq.value?.technicalItems.filter(item => Number(item.cavityCount) >= 2 && item.isLeftRightPair).length || 0) * 2)
const leftRightPairInvalid = computed(() => selectedRfq.value?.technicalItems.some(item => item.isLeftRightPair && (Number(item.cavityCount) < 2 || !item.customerPartNo2.trim())) || false)
const canPassTechnicalReview = computed(() => technicalDataCount.value > 0 && !leftRightPairInvalid.value)
const partNoLabel = (item: TechnicalReviewItem) => item.isLeftRightPair ? '零件号1' : '客户件号'
const openDetail = (row: InquiryView) => {
  row.technicalItems = row.technicalItems.length ? normalizeTechnicalItems(row.technicalItems) : [createTechnicalItem()]
  technicalReviewStore[row.backendId] = row.technicalItems
  selectedRfq.value = row
  detailVisible.value = true
}
const addTechnicalItem = () => {
  if (!selectedRfq.value) return
  selectedRfq.value.technicalItems.push(createTechnicalItem())
}
const handlePairToggle = (item: TechnicalReviewItem) => {
  if (!selectedRfq.value || !item.isLeftRightPair) {
    item.customerPartNo2 = ''
    item.pairGroupKey = undefined
    item.pairIndex = undefined
    return
  }
  item.pairGroupKey = item.pairGroupKey || `pair-${item.key}`
  item.pairIndex = 1
}
const removeTechnicalItem = (index: number) => {
  if (!selectedRfq.value) return
  const item = selectedRfq.value.technicalItems[index]
  if (selectedRfq.value.technicalItems.length === 1) {
    selectedRfq.value.technicalItems[0] = createTechnicalItem()
  } else if (item.pairGroupKey) {
    for (let cursor = selectedRfq.value.technicalItems.length - 1; cursor >= 0; cursor -= 1) {
      if (selectedRfq.value.technicalItems[cursor].pairGroupKey === item.pairGroupKey) selectedRfq.value.technicalItems.splice(cursor, 1)
    }
  } else {
    selectedRfq.value.technicalItems.splice(index, 1)
  }
}
const saveTechnicalData = () => {
  if (!selectedRfq.value) return false
  if (!technicalDataCount.value) {
    ElMessage.warning('请至少填写一个零件名称或客户件号')
    return false
  }
  if (leftRightPairInvalid.value) {
    ElMessage.warning('一出二左右件需要同时填写零件号1和零件号2')
    return false
  }
  technicalReviewStore[selectedRfq.value.backendId] = selectedRfq.value.technicalItems.map(item => ({ ...item }))
  ElMessage.success('技术资料已保存')
  return true
}
/* Legacy local workspace synchronization is intentionally removed; quote groups are persisted by the API. */
/*
const syncQuoteGroup = (rfq: InquiryView) => {
  const items = rfq.technicalItems.filter(item => item.partName.trim() || item.customerPartNo.trim() || item.customerPartNo2.trim())
  const project = projects.find(item => item.inquiryId === rfq.backendId || (item.customer === rfq.customer && (item.name === rfq.project || item.customerProject === rfq.project || (item.customerProject === '-' && item.name === '待命名项目'))))
  const projectId = project?.id || `P-${new Date().getFullYear()}-${String(projects.length + 1).padStart(3, '0')}`
  const group = project?.quoteGroups.find(item => item.inquiryId === rfq.backendId) || quoteGroups.find(item => item.inquiryId === rfq.backendId)
  let partSequence = 0
  const parts = items.flatMap((item, index) => {
    const partNumbers = [item.customerPartNo.trim() || `待补充-${index + 1}`]
    if (item.isLeftRightPair) partNumbers.push(item.customerPartNo2.trim() || `待补充-${index + 1}-2`)
    return partNumbers.map(customerPartNo => {
      const currentPartIndex = partSequence++
      return {
        id: group?.parts[currentPartIndex]?.id || Date.now() + currentPartIndex,
        customerPartNo,
        name: item.partName.trim() || '待命名零件',
        pairLabel: item.isLeftRightPair ? '左右件 · 一出二' : undefined,
        annualUsage: 0,
        price: 0,
        material: item.material.trim(),
        thickness: item.thickness.trim(),
        width: item.width.trim(),
        pitch: item.pitch.trim(),
        utilization: item.utilization.trim(),
        pressTonnage: item.pressTonnage.trim(),
        cavityCount: item.cavityCount.trim(),
        toolingLeadTime: item.toolingLeadTime.trim(),
      }
    })
  })
  const quoteGroup: QuoteGroup = {
    id: group?.id || nextQuoteGroupId(),
    inquiryId: rfq.backendId,
    customer: rfq.customer,
    vehicle: rfq.project,
    projectName: rfq.project,
    stage: '待启动',
    status: '待报价',
    path: group?.path || '待确定方案',
    toolingType: '待技术确认',
    toolingCost: Number(items[0]?.toolingCost) || 0,
    toolingLife: 0,
    material: items[0]?.material?.trim() || '-',
    parts,
    updatedAt: new Date().toISOString().slice(0, 10),
  }
  if (project) {
    project.inquiryId = rfq.backendId
    const index = project.quoteGroups.findIndex(item => item.inquiryId === rfq.backendId)
    if (index >= 0) project.quoteGroups[index] = quoteGroup
    else project.quoteGroups.push(quoteGroup)
    project.pending = project.pending.filter(item => !item.includes('技术评审') && !item.includes('关联报价组'))
  } else {
    projects.unshift({
      id: projectId,
      inquiryId: rfq.backendId,
      name: rfq.project,
      customer: rfq.customer,
      customerProject: rfq.project,
      owner: rfq.owner,
      stage: '待启动',
      status: '待启动',
      sop: '-',
      nominatedAt: new Date().toISOString().slice(0, 10),
      quoteGroups: [quoteGroup],
      milestones: [{ label: '报价组建立', date: new Date().toISOString().slice(0, 10), state: 'active' }],
      pending: [],
    })
  }
  refreshQuoteGroups()
  persistWorkspace()
}
*/
const reviewRfq = async (status: '待补充' | '已完成') => {
  if (!selectedRfq.value) return
  if (status === '已完成' && !saveTechnicalData()) return
  try {
    const updated = await customerInquiriesApi.technicalReview(selectedRfq.value.backendId, {
      status,
      technical_data: selectedRfq.value.technicalItems as unknown as Record<string, unknown>[],
    })
    const mapped = toView(updated)
    selectedRfq.value = mapped
    const index = inquiries.value.findIndex(row => row.backendId === mapped.backendId)
    if (index >= 0) inquiries.value[index] = mapped
    ElMessage.success(status === '已完成' ? '技术评审已通过，可进入报价组' : '已退回，等待补充技术资料')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '提交技术评审失败')
  }
}
const create = async () => {
  if (!form.customerId || !form.customer) return ElMessage.warning('请选择客户')
  if (!form.attachments.length) return ElMessage.warning('请至少上传一份询价文件供技术评审')
  const files = form.attachments.map(file => file.raw).filter((file): file is NonNullable<UploadUserFile['raw']> => Boolean(file))
  if (!files.length) return ElMessage.warning('请选择有效的本地文件')
  const projectName = form.project.trim() || '待命名项目'
  creating.value = true
  try {
    const createdInquiry = await customerInquiriesApi.create({ customer_id: form.customerId, project_name: projectName, due_date: form.dueAt || undefined, technical_review_note: form.remark, files })
    const projectId = 'P-2026-' + String(projects.length + 1).padStart(3, '0')
    projects.unshift({ inquiryId: createdInquiry.id, id: projectId, name: projectName, customer: form.customer, customerProject: form.project.trim() || '-', owner: '待分配', stage: '待启动', status: '待启动', sop: '-', nominatedAt: new Date().toISOString().slice(0, 10), quoteGroups: [], milestones: [{ label: '项目启动', date: new Date().toISOString().slice(0, 10), state: 'active' }], pending: ['技术评审待完成', '待关联报价组'] })
    persistWorkspace()
    await loadInquiries()
    Object.assign(form, { customerId: null, customer: '', project: '', dueAt: '', remark: '', attachments: [] })
    dialog.value = false
    ElMessage.success(projectName === '待命名项目' ? '询价已登记，已创建待命名项目并提交技术评审' : '询价已登记，已创建项目并提交技术评审')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '登记询价失败')
  } finally {
    creating.value = false
  }
}
onMounted(() => { void loadInquiries() })
</script>

<style scoped>
.project-list-page { min-width: 0; padding: 18px 0 30px; color: var(--zephyr-ink); }
.project-list-page h1 { margin: 0; color: var(--zephyr-ink); font-size: 19px; }
.list-caption { margin: 5px 0 0; color: var(--zephyr-muted); font-size: 11px; }
.stacked { display: flex; flex-direction: column; gap: 3px; }
.stacked small { color: var(--zephyr-muted); font-size: 11px; }
.part-line { display: flex; align-items: center; gap: 6px; min-height: 25px; font-size: 11px; }
.part-line small { color: var(--zephyr-muted); font-size: 10px; }
.pair-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--zephyr-primary); }
.mono { font-family: 'IBM Plex Mono', Consolas, monospace; font-size: 10px; }
.quote-loading { padding: 42px 0; text-align: center; color: var(--zephyr-muted); font-size: 12px; }
.customer-picker { display: flex; align-items: center; gap: 8px; width: 100%; }
.customer-picker .el-select { flex: 1; min-width: 0; }
.upload-tip { color: var(--zephyr-muted); font-size: 11px; line-height: 1.5; }
.review-summary, .attachment-heading { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.attachment-heading { margin-top: 20px; padding-bottom: 8px; border-bottom: 1px solid var(--zephyr-border); color: var(--zephyr-ink); font-size: 13px; }
.attachment-heading span, .review-note { color: var(--zephyr-muted); font-size: 11px; }
.attachment-list { display: grid; gap: 6px; margin: 10px 0 0; padding: 0; list-style: none; }
.attachment-list li { display: flex; justify-content: space-between; gap: 10px; padding: 8px 10px; border: 1px solid var(--zephyr-border); background: var(--zephyr-surface-muted); color: var(--zephyr-ink); font-size: 12px; }
.attachment-list small { color: var(--zephyr-muted); }
.technical-sheet { margin-top: 18px; padding: 14px; border: 1px solid var(--zephyr-border); background: var(--zephyr-surface-muted); }
.technical-heading { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.technical-heading > div { display: flex; align-items: baseline; gap: 10px; }
.technical-heading strong { color: var(--zephyr-ink); font-size: 13px; }
.technical-heading span, .technical-legend { color: var(--zephyr-muted); font-size: 11px; }
.technical-legend { margin: 8px 0 12px; line-height: 1.5; }
.technical-item { margin-top: 10px; padding: 11px; border: 1px solid #dfe8e4; background: #fff; }
.technical-item-heading { display: flex; align-items: center; justify-content: space-between; margin-bottom: 9px; color: var(--zephyr-primary); font-size: 12px; }
.technical-grid { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 9px 10px; }
.technical-grid label { display: grid; min-width: 0; gap: 4px; }
.technical-grid label span { color: var(--zephyr-muted); font-size: 10px; }
.technical-grid :deep(.el-input__wrapper) { min-height: 28px; padding: 0 8px; box-shadow: 0 0 0 1px #d5e1dc inset; }
.technical-footer { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-top: 12px; color: var(--zephyr-muted); font-size: 11px; }
.technical-footer em { margin-left: 8px; color: var(--zephyr-danger); font-style: normal; }
.review-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 18px; padding-top: 12px; border-top: 1px solid var(--zephyr-border); }
@media (max-width: 900px) { .technical-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
@media (max-width: 620px) { .technical-heading, .technical-heading > div, .technical-footer { align-items: flex-start; flex-direction: column; }.technical-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
</style>
