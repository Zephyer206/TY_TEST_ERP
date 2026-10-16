<template>
  <div class="quotes-container">
    <div class="list-view-toolbar">
      <div class="list-title-block"><el-button type="primary" @click="openCreateDialog" v-if="userStore.isManager"><el-icon><Plus /></el-icon>新建</el-button><h1>报价</h1></div>
      <div class="search-control"><el-icon><Search /></el-icon><el-input v-model="filter.search" placeholder="搜索报价单号、零件或客户" clearable @keyup.enter="fetchQuotes" /></div>
      <div class="filter-controls"><el-select v-model="filter.approval_status" placeholder="状态" clearable><el-option v-for="s in STATUS_LIST" :key="s.value" :label="s.label" :value="s.value" /></el-select><el-button @click="fetchQuotes">筛选</el-button><el-button text @click="resetFilter">重置</el-button><el-button class="view-toggle" text circle aria-label="列表视图" title="列表视图"><el-icon><Menu /></el-icon></el-button></div>
    </div>
    <div class="table-meta"><span>{{ page.total }} 条记录</span><span>从列表进入报价、定价与审批流程</span></div>

    <!-- 列表 -->
    <el-table :data="quotes" v-loading="loading" stripe>
      <el-table-column prop="quote_no" label="报价单号" width="180" />
      <el-table-column prop="part_name" label="零件名称" min-width="140" />
      <el-table-column prop="part_number" label="零件号" width="120" />
      <el-table-column prop="customer_name" label="客户" min-width="120" />
      <el-table-column prop="customer_product_no" label="客户件号" width="120" />
      <el-table-column prop="vehicle_model" label="车型" width="100" />
      <el-table-column label="单价" width="100" align="right">
        <template #default="{ row }">
          <span v-if="row.final_price">¥{{ row.final_price }}</span>
          <span v-else class="text-gray">未定价</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="130">
        <template #default="{ row }">
          <el-tag :type="statusType(row.approval_status)" size="small">
            {{ statusLabel(row.approval_status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" width="160">
        <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="260" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" size="small" @click="openDetail(row)">查看</el-button>
          <el-button link type="primary" size="small" @click="openEditPricing(row)"
            v-if="canEditPricing(row)">定价</el-button>
          <el-button link type="warning" size="small" @click="submitReview(row)"
            v-if="row.approval_status === 'DRAFT' && userStore.isManager">提交技审</el-button>
          <el-button link type="success" size="small" @click="submitBoss(row)"
            v-if="canSubmitBoss(row)">提交审批</el-button>
          <el-button link type="success" size="small" @click="openBossApprove(row)"
            v-if="row.approval_status === 'PENDING_BOSS' && userStore.isBoss">审批</el-button>
          <el-button link type="primary" size="small" @click="openFix(row)"
            v-if="row.approval_status === 'APPROVED' && userStore.isManager">定点</el-button>
          <el-button link type="danger" size="small" @click="openRevoke(row)"
            v-if="row.approval_status === 'FIXED' && userStore.isManager">撤销定点</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="pagination">
      <el-pagination
        v-model:current-page="page.current"
        v-model:page-size="page.size"
        :total="page.total"
        :page-sizes="[20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        @size-change="fetchQuotes"
        @current-change="fetchQuotes"
      />
    </div>

    <!-- ===== 新建报价 ===== -->
    <el-dialog v-model="createVisible" title="新建报价" width="520px">
      <el-form :model="createForm" label-width="100px" :rules="createRules" ref="createRef">
        <el-form-item label="零件名称">
          <div style="display: flex; gap: 8px;">
            <el-cascader
              v-model="createForm.part_name_id"
              :options="partNameCascaderOptions"
              :props="{ value: 'id', label: 'label', children: 'children', emitPath: false }"
              placeholder="选择零件名称"
              filterable
              style="flex: 1"
              clearable
            />
            <el-button @click="openQuickAddPartName" v-if="userStore.userInfo?.role_level >= 4">
              <el-icon><Plus /></el-icon>
            </el-button>
          </div>
        </el-form-item>
        <el-form-item label="客户" prop="customer_id">
          <div style="display: flex; gap: 8px;">
            <el-select v-model="createForm.customer_id" filterable clearable placeholder="选择客户" style="flex: 1">
              <el-option v-for="c in customers" :key="c.id" :value="c.id" :label="c.name" />
            </el-select>
            <el-button @click="openQuickAddCustomer" v-if="userStore.userInfo?.role_level >= 4">
              <el-icon><Plus /></el-icon>
            </el-button>
          </div>
        </el-form-item>
        <el-form-item label="客户件号" prop="customer_product_no">
          <el-input v-model="createForm.customer_product_no" />
        </el-form-item>
        <el-form-item label="车型">
          <el-input v-model="createForm.vehicle_model" />
        </el-form-item>
        <el-form-item label="年用量">
          <el-input-number v-model="createForm.annual_usage" :min="0" style="width:100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="doCreate">创建</el-button>
      </template>
    </el-dialog>

    <!-- ===== 快捷新增零件名称 ===== -->
    <el-dialog v-model="quickAddPartNameVisible" title="快捷新增零件名称" width="480px">
      <el-form :model="quickPartNameForm" label-width="110px" :rules="quickPartNameRules" ref="quickPartNameRef">
        <el-form-item label="一级分类" prop="primary_category">
          <el-select v-model="quickPartNameForm.primary_category" filterable allow-create placeholder="选择或输入新分类" style="width: 100%">
            <el-option v-for="cat in primaryCategories" :key="cat" :value="cat" :label="cat" />
          </el-select>
          <div style="color: #909399; font-size: 12px; margin-top: 4px;">
            * 必填。例如：弹簧片、报警器
          </div>
        </el-form-item>
        <el-form-item label="二级分类">
          <el-input v-model="quickPartNameForm.secondary_category" placeholder="选填。例如：标准型、加强型" />
        </el-form-item>
        <el-form-item label="客户零件名称">
          <el-input v-model="quickPartNameForm.customer_part_name" placeholder="选填。客户定制的零件名称" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="quickPartNameForm.remark" type="textarea" :rows="2" placeholder="选填" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="quickAddPartNameVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="doQuickAddPartName">保存</el-button>
      </template>
    </el-dialog>

    <!-- ===== 快捷新增零件 ===== -->
    <el-dialog v-model="quickAddPartVisible" title="快捷新增零件" width="480px">
      <el-form :model="quickPartForm" label-width="90px" :rules="{ part_number: [{ required: true, message: '请输入零件编号', trigger: 'blur' }] }" ref="quickPartRef">
        <el-form-item label="零件编号" prop="part_number">
          <el-input v-model="quickPartForm.part_number" placeholder="唯一零件编号" />
        </el-form-item>
        <el-form-item label="零件名称">
          <el-input v-model="quickPartForm.internal_name" />
        </el-form-item>
        <el-form-item label="客户">
          <el-select v-model="quickPartForm.customer_id" clearable filterable placeholder="选择客户" style="width:100%">
            <el-option v-for="c in customers" :key="c.id" :value="c.id" :label="c.name" />
          </el-select>
        </el-form-item>
        <el-form-item label="客户件号">
          <el-input v-model="quickPartForm.customer_product_no" />
        </el-form-item>
        <el-form-item label="车型">
          <el-input v-model="quickPartForm.vehicle_model" />
        </el-form-item>
        <el-form-item label="材质">
          <el-input v-model="quickPartForm.material_name" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="quickAddPartVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="doQuickAddPart">保存</el-button>
      </template>
    </el-dialog>

    <!-- ===== 快捷新增客户 ===== -->
    <el-dialog v-model="quickAddCustomerVisible" title="快捷新增客户" width="420px">
      <el-form :model="quickCustomerForm" label-width="90px" :rules="{ name: [{ required: true, message: '请输入客户名称', trigger: 'blur' }] }" ref="quickCustomerRef">
        <el-form-item label="客户名称" prop="name">
          <el-input v-model="quickCustomerForm.name" placeholder="请输入客户名称" />
        </el-form-item>
        <el-form-item label="Sheet Key">
          <el-input v-model="quickCustomerForm.sheet_key" placeholder="选填" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="quickAddCustomerVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="doQuickAddCustomer">保存</el-button>
      </template>
    </el-dialog>


    <!-- ===== 定价 ===== -->
    <el-dialog v-model="pricingVisible" title="定价" width="480px">
      <el-form :model="pricingForm" label-width="110px">
        <el-form-item label="冲压费">
          <el-input-number v-model="pricingForm.stamping_fee" :precision="4" :min="0" style="width:100%" />
        </el-form-item>
        <el-form-item label="表面处理费">
          <el-input-number v-model="pricingForm.surface_fee" :precision="4" :min="0" style="width:100%" />
        </el-form-item>
        <el-form-item label="其他处理费">
          <el-input-number v-model="pricingForm.treatment_fee" :precision="4" :min="0" style="width:100%" />
        </el-form-item>
        <el-form-item label="利润率(%)">
          <el-input-number v-model="pricingForm.profit_margin" :precision="2" :min="0" :max="100" style="width:100%" />
        </el-form-item>
        <el-form-item label="最终单价">
          <el-input-number v-model="pricingForm.final_price" :precision="4" :min="0" style="width:100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="pricingVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="savePricing">保存</el-button>
      </template>
    </el-dialog>

    <!-- ===== 老板审批 ===== -->
    <el-dialog v-model="approveVisible" title="老板审批" width="440px">
      <el-form :model="approveForm" label-width="90px">
        <el-form-item label="审批结果">
          <el-radio-group v-model="approveForm.approved">
            <el-radio :value="true">通过</el-radio>
            <el-radio :value="false">驳回</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="驳回原因" v-if="!approveForm.approved">
          <el-input v-model="approveForm.reject_reason" type="textarea" rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="approveVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="doBossApprove">确认</el-button>
      </template>
    </el-dialog>

    <!-- ===== 定点确认 ===== -->
    <el-dialog v-model="fixVisible" title="定点确认" width="480px">
      <el-form :model="fixForm" label-width="110px">
        <el-form-item label="定点路径">
          <el-radio-group v-model="fixForm.fix_path">
            <el-radio value="direct_production">直接量产</el-radio>
            <el-radio value="sample_first">先做样件</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="成交单价">
          <el-input-number v-model="fixForm.final_price" :precision="4" :min="0" style="width:100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="fixVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="doFix">确认定点</el-button>
      </template>
    </el-dialog>

    <!-- ===== 撤销定点 ===== -->
    <el-dialog v-model="revokeVisible" title="撤销定点" width="440px">
      <el-form :model="revokeForm" label-width="90px">
        <el-form-item label="撤销原因">
          <el-input v-model="revokeForm.revoke_reason" type="textarea" rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="revokeVisible = false">取消</el-button>
        <el-button type="danger" :loading="saving" @click="doRevoke">确认撤销</el-button>
      </template>
    </el-dialog>

    <!-- ===== 详情抽屉 ===== -->
    <el-drawer v-model="detailVisible" title="报价详情" size="500px">
      <el-descriptions :column="1" border v-if="currentQuote">
        <el-descriptions-item label="报价单号">{{ currentQuote.quote_no }}</el-descriptions-item>
        <el-descriptions-item label="零件名称">{{ currentQuote.part_name }}</el-descriptions-item>
        <el-descriptions-item label="零件号">{{ currentQuote.part_number }}</el-descriptions-item>
        <el-descriptions-item label="客户">{{ currentQuote.customer_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="客户件号">{{ currentQuote.customer_product_no || '-' }}</el-descriptions-item>
        <el-descriptions-item label="车型">{{ currentQuote.vehicle_model || '-' }}</el-descriptions-item>
        <el-descriptions-item label="年用量">{{ currentQuote.annual_usage }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="statusType(currentQuote.approval_status)" size="small">
            {{ statusLabel(currentQuote.approval_status) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="厚度T(mm)">{{ currentQuote.thickness || '-' }}</el-descriptions-item>
        <el-descriptions-item label="宽度W(mm)">{{ currentQuote.width || '-' }}</el-descriptions-item>
        <el-descriptions-item label="穴数">{{ currentQuote.cavity_count }}</el-descriptions-item>
        <el-descriptions-item label="吨位">{{ currentQuote.press_tonnage || '-' }}</el-descriptions-item>
        <el-descriptions-item label="模具费">{{ currentQuote.mold_cost ?? '-' }}</el-descriptions-item>
        <el-descriptions-item label="冲压费">{{ currentQuote.stamping_fee ?? '-' }}</el-descriptions-item>
        <el-descriptions-item label="表面处理费">{{ currentQuote.surface_fee ?? '-' }}</el-descriptions-item>
        <el-descriptions-item label="利润率(%)">{{ currentQuote.profit_margin ?? '-' }}</el-descriptions-item>
        <el-descriptions-item label="最终单价">
          <strong v-if="currentQuote.final_price">¥{{ currentQuote.final_price }}</strong>
          <span v-else>未定价</span>
        </el-descriptions-item>
        <el-descriptions-item label="驳回原因" v-if="currentQuote.rejection_reason">
          <span class="text-danger">{{ currentQuote.rejection_reason }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ formatDate(currentQuote.created_at) }}</el-descriptions-item>
      </el-descriptions>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Menu, Plus, Search } from '@element-plus/icons-vue'
import { formatDate } from '@/utils/format'
import { useUserStore } from '@/stores/user'
import { quotesApi } from '@/api/quotes'
import { customersApi } from '@/api/customers'
import { partNamesApi } from '@/api/dictionary'
import { partsApi } from '@/api/parts'

const userStore = useUserStore()

// ---- state ----
const quotes = ref([])
const loading = ref(false)
const saving = ref(false)
const partOptions = ref([])
const partLoading = ref(false)
const customers = ref([])
const partNames = ref([])
const partNameCascaderOptions = ref([])
const primaryCategories = ref([])
const currentQuote = ref(null)
const activeId = ref(null)

const filter = reactive({ approval_status: '', search: '' })
const page = reactive({ current: 1, size: 20, total: 0 })

// dialogs
const createVisible = ref(false)
const pricingVisible = ref(false)
const approveVisible = ref(false)
const fixVisible = ref(false)
const revokeVisible = ref(false)
const detailVisible = ref(false)
const createRef = ref(null)

const createForm = reactive({ part_name_id: null, customer_id: null, customer_product_no: '', vehicle_model: '', annual_usage: 0 })
const pricingForm = reactive({ stamping_fee: 0, surface_fee: 0, treatment_fee: 0, profit_margin: 0, final_price: null })
const approveForm = reactive({ approved: true, reject_reason: '' })
const fixForm = reactive({ fix_path: 'direct_production', final_price: null })
const revokeForm = reactive({ revoke_reason: '' })

const createRules = {
  customer_id: [{ required: true, message: '请选择客户', trigger: 'change' }],
  customer_product_no: [{ required: true, message: '请输入客户件号', trigger: 'blur' }]
}

// ---- status ----
const STATUS_LIST = [
  { value: 'DRAFT', label: '草稿' },
  { value: 'WAITING_FOR_TECH', label: '待技术审核' },
  { value: 'TECH_APPROVED', label: '技术已审核' },
  { value: 'TECH_REJECTED', label: '技术已驳回' },
  { value: 'PENDING_BOSS', label: '待老板审批' },
  { value: 'APPROVED', label: '已审批' },
  { value: 'REJECTED', label: '已驳回' },
  { value: 'FIXED', label: '已定点' },
]
const statusMap = {
  DRAFT: { label: '草稿', type: 'info' },
  WAITING_FOR_TECH: { label: '待技术审核', type: 'warning' },
  TECH_REVIEW: { label: '技术审核中', type: 'warning' },
  TECH_APPROVED: { label: '技术已审核', type: 'success' },
  TECH_REJECTED: { label: '技术已驳回', type: 'danger' },
  PENDING_BOSS: { label: '待老板审批', type: 'warning' },
  APPROVED: { label: '已审批', type: 'success' },
  REJECTED: { label: '已驳回', type: 'danger' },
  FIXED: { label: '已定点', type: 'success' },
}
const statusLabel = (s) => statusMap[s]?.label || s
const statusType = (s) => statusMap[s]?.type || 'info'

// ---- permissions ----
const canEditPricing = (row) =>
  userStore.isManager &&
  ['DRAFT', 'TECH_APPROVED', 'TECH_REJECTED', 'APPROVED', 'REJECTED'].includes(row.approval_status)

const canSubmitBoss = (row) =>
  userStore.isManager &&
  ['DRAFT', 'TECH_APPROVED'].includes(row.approval_status)

// ---- API ----
const fetchQuotes = async () => {
  loading.value = true
  try {
    const params = {
      skip: (page.current - 1) * page.size,
      limit: page.size,
      ...(filter.approval_status && { approval_status: filter.approval_status }),
      ...(filter.search && { search: filter.search }),
    }
    const data = await quotesApi.list(params)
    quotes.value = Array.isArray(data) ? data : (data.items || [])
    page.total = data.total || quotes.value.length
  } catch (e) {
    ElMessage.error(e.message || '获取列表失败')
  } finally {
    loading.value = false
  }
}

const fetchCustomers = async () => {
  try {
    const data = await customersApi.list()
    customers.value = Array.isArray(data) ? data : (data.items || [])
  } catch { /* silent */ }
}

const fetchPartNames = async () => {
  try {
    const data = await partNamesApi.list({ limit: 500 })
    partNames.value = Array.isArray(data) ? data : (data.items || [])

    // 提取一级分类列表
    const categories = new Set()
    partNames.value.forEach(part => {
      if (part.primary_category) {
        categories.add(part.primary_category)
      }
    })
    primaryCategories.value = Array.from(categories).sort()

    // 构建三级级联选择器数据结构
    buildPartNameCascader()
  } catch { /* silent */ }
}

const buildPartNameCascader = () => {
  // 三级结构: 一级分类 -> 二级分类 -> 客户零件名称
  const primaryMap = new Map()

  partNames.value.forEach(part => {
    const primary = part.primary_category
    if (!primary) return

    if (!primaryMap.has(primary)) {
      primaryMap.set(primary, new Map())
    }

    const secondaryMap = primaryMap.get(primary)
    const secondary = part.secondary_category || '直接选择'

    if (!secondaryMap.has(secondary)) {
      secondaryMap.set(secondary, [])
    }

    // 第三级：客户零件名称或标准件
    const label = part.customer_part_name || '标准件'
    secondaryMap.get(secondary).push({
      id: part.id,
      label: label,
      value: part.id,
      remark: part.remark
    })
  })

  // 转换为级联选择器格式
  partNameCascaderOptions.value = Array.from(primaryMap.entries()).map(([primary, secondaryMap]) => ({
    label: primary,  // 第一列：弹簧片、报警器
    value: primary,
    children: Array.from(secondaryMap.entries()).map(([secondary, items]) => ({
      label: secondary,  // 第二列：弹簧片、直接选择
      value: `${primary}-${secondary}`,
      children: items    // 第三列：摩擦片保持、标准件
    }))
  }))
}

const searchParts = async (query) => {
  if (!query) return
  partLoading.value = true
  try {
    const data = await partsApi.list({ search: query, limit: 30 })
    partOptions.value = Array.isArray(data) ? data : (data.items || [])
  } catch { /* silent */ } finally {
    partLoading.value = false
  }
}

const loadDetail = async (id) => {
  try {
    return await quotesApi.detail(id)
  } catch (e) {
    ElMessage.error(e.message)
    return null
  }
}

// ---- handlers ----
const resetFilter = () => { filter.approval_status = ''; filter.search = ''; page.current = 1; fetchQuotes() }

const openCreateDialog = () => {
  Object.assign(createForm, { part_name_id: null, customer_id: null, customer_product_no: '', vehicle_model: '', annual_usage: 0 })
  partOptions.value = []
  createVisible.value = true
}

const doCreate = async () => {
  await createRef.value?.validate()
  saving.value = true
  try {
    await quotesApi.create(createForm)
    ElMessage.success('报价创建成功')
    createVisible.value = false
    fetchQuotes()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    saving.value = false
  }
}

const openDetail = async (row) => {
  currentQuote.value = await loadDetail(row.id)
  detailVisible.value = true
}

const openEditPricing = async (row) => {
  const q = await loadDetail(row.id)
  if (!q) return
  activeId.value = row.id
  Object.assign(pricingForm, {
    stamping_fee: parseFloat(q.stamping_fee) || 0,
    surface_fee: parseFloat(q.surface_fee) || 0,
    treatment_fee: parseFloat(q.treatment_fee) || 0,
    profit_margin: parseFloat(q.profit_margin) || 0,
    final_price: q.final_price ? parseFloat(q.final_price) : null,
  })
  pricingVisible.value = true
}

const savePricing = async () => {
  saving.value = true
  try {
    await quotesApi.pricing(activeId.value, pricingForm)
    ElMessage.success('定价已保存')
    pricingVisible.value = false
    fetchQuotes()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    saving.value = false
  }
}

const submitReview = async (row) => {
  await ElMessageBox.confirm('提交技术审核？', '确认', { type: 'warning' })
  try {
    await quotesApi.submitReview(row.id)
    ElMessage.success('已提交技术审核')
    fetchQuotes()
  } catch (e) {
    ElMessage.error(e.message)
  }
}

const submitBoss = async (row) => {
  await ElMessageBox.confirm('提交老板审批？', '确认', { type: 'warning' })
  try {
    await quotesApi.submitBoss(row.id)
    ElMessage.success('已提交老板审批')
    fetchQuotes()
  } catch (e) {
    ElMessage.error(e.message)
  }
}

const openBossApprove = (row) => {
  activeId.value = row.id
  approveForm.approved = true
  approveForm.reject_reason = ''
  approveVisible.value = true
}

const doBossApprove = async () => {
  saving.value = true
  try {
    await quotesApi.bossApprove(activeId.value, approveForm)
    ElMessage.success(approveForm.approved ? '审批通过' : '已驳回')
    approveVisible.value = false
    fetchQuotes()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    saving.value = false
  }
}

const openFix = (row) => {
  activeId.value = row.id
  fixForm.fix_path = 'direct_production'
  fixForm.final_price = null
  fixVisible.value = true
}

const doFix = async () => {
  saving.value = true
  try {
    await quotesApi.fix(activeId.value, fixForm)
    ElMessage.success('定点完成')
    fixVisible.value = false
    fetchQuotes()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    saving.value = false
  }
}

const openRevoke = (row) => {
  activeId.value = row.id
  revokeForm.revoke_reason = ''
  revokeVisible.value = true
}

const doRevoke = async () => {
  saving.value = true
  try {
    await quotesApi.revokeNomination(activeId.value, revokeForm)
    ElMessage.success('定点已撤销')
    revokeVisible.value = false
    fetchQuotes()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    saving.value = false
  }
}

// ---- Quick add part name ----
const quickAddPartNameVisible = ref(false)
const quickPartNameForm = reactive({
  primary_category: '',
  secondary_category: '',
  customer_part_name: '',
  remark: ''
})
const quickPartNameRef = ref(null)
const quickPartNameRules = {
  primary_category: [{ required: true, message: '请输入一级分类', trigger: 'blur' }]
}

const openQuickAddPartName = () => {
  Object.assign(quickPartNameForm, {
    primary_category: '',
    secondary_category: '',
    customer_part_name: '',
    remark: ''
  })
  quickAddPartNameVisible.value = true
}

const doQuickAddPartName = async () => {
  await quickPartNameRef.value?.validate()
  saving.value = true
  try {
    const newPartName = await partNamesApi.create(quickPartNameForm)
    ElMessage.success('零件名称已添加')
    quickAddPartNameVisible.value = false
    createForm.part_name_id = newPartName.id
    await fetchPartNames()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    saving.value = false
  }
}

// ---- Quick add part ----
const quickAddPartVisible = ref(false)
const quickPartForm = reactive({ part_number: '', internal_name: '', customer_id: null, customer_product_no: '', vehicle_model: '', material_name: '' })
const quickPartRef = ref(null)

const openQuickAddPart = () => {
  Object.assign(quickPartForm, { part_number: '', internal_name: '', customer_id: null, customer_product_no: '', vehicle_model: '', material_name: '' })
  quickAddPartVisible.value = true
}

const doQuickAddPart = async () => {
  await quickPartRef.value?.validate()
  saving.value = true
  try {
    const newPart = await partsApi.create(quickPartForm)
    ElMessage.success('零件已创建')
    quickAddPartVisible.value = false
    createForm.part_id = newPart.id
    partOptions.value = [newPart]
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    saving.value = false
  }
}

// ---- Quick add customer ----
const quickAddCustomerVisible = ref(false)
const quickCustomerForm = reactive({ name: '', sheet_key: '' })
const quickCustomerRef = ref(null)

const openQuickAddCustomer = () => {
  Object.assign(quickCustomerForm, { name: '', sheet_key: '' })
  quickAddCustomerVisible.value = true
}

const doQuickAddCustomer = async () => {
  await quickCustomerRef.value?.validate()
  saving.value = true
  try {
    const newCustomer = await customersApi.create(quickCustomerForm)
    ElMessage.success('客户已创建')
    quickAddCustomerVisible.value = false
    createForm.customer_id = newCustomer.id
    await fetchCustomers()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    saving.value = false
  }
}

onMounted(() => { fetchQuotes(); fetchCustomers(); fetchPartNames() })
</script>

<style scoped>
.quotes-container { min-width: 0; }
.list-view-toolbar { display: grid; grid-template-columns: auto minmax(240px, 1fr) auto; align-items: center; gap: 14px; min-height: 58px; margin-bottom: 10px; padding: 8px 0; }
.list-title-block { display: flex; align-items: center; gap: 10px; min-width: 150px; }.list-title-block h1 { margin: 0; color: #4a4850; font-size: 20px; font-weight: 600; }
.search-control { display: flex; align-items: center; gap: 8px; width: min(500px, 100%); padding: 4px 10px; border: 1px solid #cbc9d1; border-radius: 3px; background: #fff; color: #7a7782; }.search-control :deep(.el-input__wrapper) { padding: 0; box-shadow: none; }
.filter-controls { display: flex; align-items: center; justify-content: flex-end; gap: 6px; }.filter-controls :deep(.el-select) { width: 128px; }.view-toggle { color: #625780; }
.table-meta { display: flex; justify-content: space-between; margin: 0 0 8px; color: var(--zephyr-muted); font-size: 12px; }.table-meta span:last-child { color: #96939e; }
.pagination { display: flex; justify-content: flex-end; margin-top: 16px; }
.text-gray { color: #999; }
.text-danger { color: #f56c6c; }
@media (max-width: 900px) { .list-view-toolbar { grid-template-columns: 1fr; }.filter-controls { justify-content: flex-start; } }
</style>
