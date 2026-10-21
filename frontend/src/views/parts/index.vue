<template>
  <div class="parts-container">
    <div class="list-view-toolbar">
      <div class="list-title-block">
        <div>
          <h1>零件</h1>
          <span class="list-caption">产品档案与工艺关联</span>
        </div>
      </div>
      <div class="search-control">
        <el-icon><Search /></el-icon>
        <el-input v-model="filter.search" aria-label="搜索零件" placeholder="搜索客户、客户件号、零件或模具" clearable @keyup.enter="applyFilters" @clear="handleSearchClear" />
      </div>
      <el-button v-if="isMobile" class="mobile-filter-toggle" :aria-expanded="mobileFiltersOpen" aria-controls="parts-filter-controls" @click="mobileFiltersOpen = !mobileFiltersOpen">筛选{{ activeFilterCount ? ` (${activeFilterCount})` : '' }}</el-button>
      <div v-show="!isMobile || mobileFiltersOpen" id="parts-filter-controls" class="filter-controls">
        <el-select v-model="companyStore.selectedCompany" placeholder="公司" @change="handleCompanyChange">
          <el-option label="天越" value="tianyue" />
          <el-option label="盖博" value="gaibo" />
        </el-select>
        <el-select v-model="filter.customer_id" clearable placeholder="客户" aria-label="按客户筛选" filterable @change="applyFilters">
            <el-option v-for="c in customers" :key="c.id" :value="c.id"
              :label="c.customer_code ? `${c.customer_code} ${c.name}` : c.name" />
        </el-select>
        <el-input v-model="filter.material" placeholder="材料" aria-label="按材料筛选" clearable @keyup.enter="applyFilters" />
        <el-select v-model="filter.part_status" clearable placeholder="状态" aria-label="按状态筛选" @change="applyFilters">
          <el-option label="草稿" value="DRAFT" />
          <el-option label="打样" value="SAMPLING" />
          <el-option label="量产" value="MASS_PRODUCTION" />
          <el-option label="淘汰" value="OBSOLETE" />
        </el-select>
        <el-button type="primary" @click="applyFilters">筛选</el-button>
        <el-button text @click="resetFilter">重置</el-button>
        <el-button type="primary" @click="openCreate" v-if="userStore.userInfo?.role_level >= 4">
          <el-icon><Plus /></el-icon>新建
        </el-button>
      </div>
    </div>

    <div class="table-meta">
      <span>{{ page.total }} 条记录 <span v-if="visibleParts.length !== parts.length">· 当前筛选 {{ visibleParts.length }} 条</span></span>
      <span>{{ isMobile ? '点击零件查看详情' : '选择一行打开零件档案' }}</span>
    </div>

    <el-alert v-if="listError" :title="listError" type="error" :closable="false" show-icon><el-button text @click="fetchParts">重新加载</el-button></el-alert>

    <div v-if="!isMobile" class="batch-bar" aria-live="polite">
      <span v-if="selectedParts.length">已选 {{ selectedParts.length }} 条</span>
      <span v-else>列表优先：选择行后可批量处理</span>
      <el-button v-if="selectedParts.length" text type="primary" size="small" @click="markSelectedForReview">批量标记复核</el-button>
    </div>

    <section v-if="isMobile" class="mobile-parts-list" aria-label="零件档案列表" :aria-busy="loading" v-loading="loading">
      <button v-for="row in visibleParts" :key="row._groupKey || row.id" type="button" class="mobile-part-card" :aria-label="`查看零件 ${row.customer_part_no || row.part_name || '未命名零件'} 的详情`" @click="openEdit(row)">
        <span class="mobile-part-fields">
          <span class="mobile-part-field"><span class="mobile-part-label">零件编号</span><span class="mobile-part-value mobile-part-number">{{ row.customer_part_no || '—' }}</span></span>
          <span class="mobile-part-field"><span class="mobile-part-label">零件名称</span><span class="mobile-part-value">{{ row.part_name || '—' }}</span></span>
          <span class="mobile-part-field"><span class="mobile-part-label">客户</span><span class="mobile-part-value">{{ row.customer_name || '—' }}</span></span>
          <span class="mobile-part-field"><span class="mobile-part-label">模具类型</span><span class="mobile-part-value">{{ row.tooling_type || '—' }}</span></span>
        </span>
      </button>
      <el-empty v-if="!loading && !visibleParts.length && !listError" description="没有符合条件的零件，请调整筛选条件" :image-size="72" />
      <el-skeleton v-if="loading && !visibleParts.length" :rows="8" animated />
    </section>

    <el-table v-else class="parts-table" :data="visibleParts" :row-key="row => row._groupKey || row.id" v-loading="loading" :span-method="spanMethod" :row-class-name="tableRowClassName" @selection-change="handleSelectionChange" @row-click="openEdit">
      <el-table-column type="selection" width="32" fixed="left" />
      <el-table-column label="零件编号" width="96" fixed>
        <template #default="{ row }">
          <span v-if="row.customer_part_no">
            <span v-for="(segment, index) in highlightSegments(row.customer_part_no)" :key="`part-no-${index}`" :class="{ 'search-hit': segment.highlighted }">{{ segment.text }}</span>
          </span>
          <span v-else class="text-muted">暂无记录</span>
        </template>
      </el-table-column>
      <el-table-column label="零件名称" min-width="110">
        <template #default="{ row }">
          <span v-if="row.part_name">
            <span v-for="(segment, index) in highlightSegments(row.part_name)" :key="`part-name-${index}`" :class="{ 'search-hit': segment.highlighted }">{{ segment.text }}</span>
          </span>
          <span v-else class="text-muted">暂无记录</span>
        </template>
      </el-table-column>
      <el-table-column label="模具号" width="100">
        <template #default="{ row }">
          <span v-for="(segment, index) in highlightSegments(row.tooling_number)" :key="`tooling-${index}`" :class="{ 'search-hit': segment.highlighted }">{{ segment.text }}</span>
        </template>
      </el-table-column>
      <el-table-column label="TWP规格" width="115">
        <template #default="{ row }">
          <span v-if="row.thickness || row.width || row.pitch" class="twp-text">
            {{ formatTWP(row.thickness, row.width, row.pitch) }}<span v-if="row._isPair">（一出二）</span>
          </span>
          <span v-else-if="row.spec_twph" class="spec-text">
            {{ row.spec_twph }}<span v-if="row._isPair">（一出二）</span>
          </span>
          <span v-else-if="row._isPair" class="twp-text">一出二</span>
          <span v-else class="text-muted">-</span>
        </template>
      </el-table-column>
      <el-table-column label="材料" width="82">
        <template #default="{ row }">
          <el-tooltip :content="row.material_name_full" placement="top" v-if="row.material_name_full">
            <span>{{ row.material_name || '-' }}</span>
          </el-tooltip>
          <span v-else>{{ row.material_name || '-' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="穴数" width="45" align="center">
        <template #default="{ row }">
          <span v-if="row.cavity_count">{{ row.cavity_count }}</span>
          <span v-else class="text-muted">-</span>
        </template>
      </el-table-column>
      <el-table-column label="客户" width="96">
        <template #default="{ row }">
          <span v-for="(segment, index) in highlightSegments(row.customer_name)" :key="`customer-${index}`" :class="{ 'search-hit': segment.highlighted }">{{ segment.text }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="tooling_type" label="模具类型" width="78" />
      <el-table-column prop="press_tonnage" label="冲床吨位" width="92" />
      <el-table-column prop="stock_pcs" label="库存" width="64" align="right" />
      <!-- 整件删除入口待可访问的回收与恢复流程完善后再开放。 -->
      <el-table-column label="操作" width="100" fixed="right">
        <template #default="{ row }">
          <template v-if="row._isPair">
            <el-dropdown trigger="click" @click.stop @command="openPairMember">
              <el-button link type="primary" size="small">选择件</el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item v-for="member in row._members" :key="`detail-${member.id}`" :command="member">
                    {{ positionLabel(member.part_position) }}件详情
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </template>
          <template v-else>
            <el-button link type="primary" size="small" @click.stop="openEdit(row)">查看详情</el-button>
          </template>
        </template>
      </el-table-column>
    </el-table>

    <div class="pagination">
      <div v-if="isMobile" class="mobile-page-summary"><span>第 {{ page.current }} / {{ Math.max(1, Math.ceil(page.total / page.size)) }} 页</span><el-select :model-value="page.size" aria-label="每页记录数" @change="changePageSize"><el-option v-for="size in [20, 50, 100]" :key="size" :label="`每页 ${size} 条`" :value="size" /></el-select></div>
      <el-pagination
        v-model:current-page="page.current"
        v-model:page-size="page.size"
        :total="page.total"
        :page-sizes="[20, 50, 100]"
        :layout="isMobile ? 'prev, pager, next' : 'total, sizes, prev, pager, next'"
        :pager-count="isMobile ? 5 : 7"
        @size-change="changePageSize"
        @current-change="fetchParts"
      />
    </div>

    <!-- 新增对话框 (简单版) -->
    <el-dialog v-model="dialogVisible" title="新增零件" width="520px">
      <el-form :model="form" label-width="90px" :rules="rules" ref="formRef">
        <el-form-item label="客户件号" prop="customer_part_no">
          <el-input v-model="form.customer_part_no" placeholder="客户件号" />
        </el-form-item>
        <el-form-item label="零件名称">
          <el-input v-model="form.internal_name" />
        </el-form-item>
        <el-form-item label="客户">
          <el-select v-model="form.customer_id" clearable filterable placeholder="选择客户" style="width:100%">
            <el-option v-for="c in customers" :key="c.id" :value="c.id"
              :label="c.customer_code ? `${c.customer_code} ${c.name}` : c.name" />
          </el-select>
        </el-form-item>
        <el-form-item label="车型">
          <el-input v-model="form.vehicle_model" />
        </el-form-item>
        <el-form-item label="材质">
          <el-input v-model="form.material_name" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="doSave">保存</el-button>
      </template>
    </el-dialog>

    <!-- 既有零件的完整编辑器；新增仍保留上方的简化建档流程。 -->
    <PartEditorDialog
      v-model="editorVisible"
      :part-id="editPartId"
      @saved="handleEditorSaved"
    />
  </div>
</template>

<script setup>
import { computed, ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus, Search } from '@element-plus/icons-vue'
import { useMobileViewport } from '@/composables/useMobileViewport'
import { useRouter } from 'vue-router'
import { useCompanyStore } from '@/stores/company'
import { useUserStore } from '@/stores/user'
import { partsApi } from '@/api/parts'
import { customersApi } from '@/api/customers'
import PartEditorDialog from '@/components/PartEditorDialog.vue'

const userStore = useUserStore()
const router = useRouter()
const companyStore = useCompanyStore()
const isMobile = useMobileViewport()
const mobileFiltersOpen = ref(false)
const listError = ref('')

const parts = ref([])
const customers = ref([])
const loading = ref(false)
const saving = ref(false)
const dialogVisible = ref(false)
const formRef = ref(null)
const editorVisible = ref(false)
const editPartId = ref(null)
const selectedParts = ref([])
const appliedSearch = ref('')

const filter = reactive({ search: '', customer_id: null, part_status: '', material: '' })
const activeFilterCount = computed(() => [filter.customer_id, filter.part_status, filter.material].filter(Boolean).length)
const page = reactive({ current: 1, size: 20, total: 0 })
const form = reactive({
  customer_part_no: '', internal_name: '', customer_id: null,
  vehicle_model: '', material_name: '', remark: '',
})
const rules = { internal_name: [{ required: true, message: '请填写零件名称', trigger: 'blur' }] }

const STATUS_MAP = {
  DRAFT: { label: '草稿', type: 'info' },
  SAMPLING: { label: '打样', type: 'warning' },
  MASS_PRODUCTION: { label: '量产', type: 'success' },
  OBSOLETE: { label: '淘汰', type: 'danger' },
  MIXED: { label: '状态不一致', type: 'warning' },
}
const statusLabel = s => STATUS_MAP[s]?.label || s
const statusType = s => STATUS_MAP[s]?.type || 'info'
const positionLabel = position => position === 'left' ? '左' : position === 'right' ? '右' : ''

const highlightSegments = value => {
  const text = value === null || value === undefined ? '' : String(value)
  const query = appliedSearch.value
  if (!text || !query) return [{ text, highlighted: false }]

  const lowerText = text.toLocaleLowerCase()
  const lowerQuery = query.toLocaleLowerCase()
  const segments = []
  let cursor = 0
  let matchIndex = lowerText.indexOf(lowerQuery, cursor)
  while (matchIndex !== -1) {
    if (matchIndex > cursor) {
      segments.push({ text: text.slice(cursor, matchIndex), highlighted: false })
    }
    segments.push({ text: text.slice(matchIndex, matchIndex + query.length), highlighted: true })
    cursor = matchIndex + query.length
    matchIndex = lowerText.indexOf(lowerQuery, cursor)
  }
  if (cursor < text.length) {
    segments.push({ text: text.slice(cursor), highlighted: false })
  }
  return segments.length ? segments : [{ text, highlighted: false }]
}

const formatTWP = (t, w, p) => {
  // Format T/W/P without letters, using × as separator
  // Examples:
  //   T=0.8, W=34, P=34.5 -> "0.8×34×34.5"
  //   T=0.4, W=null, P=null -> "0.4"
  //   T=0.4, W=92, P=null -> "0.4×92"
  //   T=0.4, W=null, P=53 -> "0.4×-×53" (preserve position with -)

  if (!t && !w && !p) return '-'

  const parts = []

  if (t !== null && t !== undefined) {
    parts.push(String(t))
  }

  if (w !== null && w !== undefined) {
    parts.push(String(w))
  } else if (p !== null && p !== undefined) {
    // Middle dimension missing but pitch exists - use placeholder
    parts.push('-')
  }

  if (p !== null && p !== undefined) {
    parts.push(String(p))
  }

  return parts.join('×')
}

const firstValue = (members, field) => {
  const member = members.find(item => item[field] !== null && item[field] !== undefined && item[field] !== '')
  return member?.[field] ?? null
}

const uniqueValues = (members, field) => [
  ...new Set(members.map(item => item[field]).filter(value => value !== null && value !== undefined && value !== ''))
]

const formatPairName = members => {
  const names = members.map(member => {
    return member.part_name || ''
  }).filter(Boolean)
  const normalized = names.map(name => name.replace(/^[左右]\s*/, '').trim()).filter(Boolean)
  if (normalized.length && normalized.every(name => name === normalized[0])) {
    return `${normalized[0]}（左右件）`
  }
  return names.join(' / ') || '左右件'
}

const toDisplayRow = group => {
  const members = [...(group.members || [])].sort((a, b) => {
    const order = { left: 0, right: 1 }
    return (order[a.part_position] ?? 2) - (order[b.part_position] ?? 2)
  })
  const first = members[0] || {}

  if (!group.is_left_right_pair || members.length !== 2) {
    return { ...first, _groupKey: group.key, _isPair: false, _members: members }
  }

  const statuses = uniqueValues(members, 'part_status')
  const baseMoldNumber = group.key.replace(/^pair:/, '')
  const stockByPosition = members
    .map(member => `${positionLabel(member.part_position)}${member.stock_pcs ?? 0}`)
    .join(' / ')

  const customerPartNos = uniqueValues(members, 'customer_part_no')

  return {
    ...first,
    id: group.key,
    _groupKey: group.key,
    _isPair: true,
    _members: members,
    customer_part_no: customerPartNos.length > 0 ? customerPartNos.join(' / ') : null,
    part_name: formatPairName(members),
    tooling_number: `${baseMoldNumber}（-1/-2）`,
    customer_name: uniqueValues(members, 'customer_name').join(' / '),
    material_name: uniqueValues(members, 'material_name').join(' / '),
    material_name_full: uniqueValues(members, 'material_name_full').join(' / '),
    tooling_type: uniqueValues(members, 'tooling_type').join(' / '),
    part_status: statuses.length === 1 ? statuses[0] : 'MIXED',
    stock_pcs: stockByPosition,
    spec_twph: firstValue(members, 'spec_twph'),
    thickness: firstValue(members, 'thickness'),
    width: firstValue(members, 'width'),
    pitch: firstValue(members, 'pitch'),
    cavity_count: firstValue(members, 'cavity_count'),
    part_position: 'both',
  }
}

const nonEmptyUnique = values => [
  ...new Set(values
    .map(value => typeof value === 'string' ? value.trim() : value)
    .filter(value => value !== null && value !== undefined && value !== ''))
]

const memberTwpText = member => {
  if (member.thickness !== null && member.thickness !== undefined
    || member.width !== null && member.width !== undefined
    || member.pitch !== null && member.pitch !== undefined) {
    return formatTWP(member.thickness, member.width, member.pitch)
  }
  return member.spec_twph || null
}

const formatCavityCount = value => {
  if (value === null || value === undefined || value === '') return null
  return String(value)
    .split('/')
    .map(item => item.trim())
    .filter(Boolean)
    .map(item => `一出${item}`)
    .join(' / ')
}

const partIdentity = member => {
  const identity = member.customer_part_no || member.part_name
  return identity ? String(identity).trim().toLowerCase() : `id:${member.id}`
}

const toDisplayRows = group => {
  const members = [...(group.members || [])].sort((a, b) => {
    const order = { left: 0, right: 1 }
    return (order[a.part_position] ?? 2) - (order[b.part_position] ?? 2)
  })
  if (!members.length) return []

  const hasDifferentParts = new Set(members.map(partIdentity)).size > 1
  const shouldMergeTwpAndCavity = (group.is_left_right_pair || group.is_shared_source_group)
    && members.length > 1
    && hasDifferentParts
  const mergedTwpText = nonEmptyUnique(members.map(memberTwpText)).join(' / ') || null
  return members.map((member, index) => {
    // Never infer cavity count from a pair or from a -1/-2 identifier.
    const cavity = member.cavity_count || null
    const displayTwp = shouldMergeTwpAndCavity
      ? mergedTwpText
      : memberTwpText(member)

    return {
      ...member,
      _groupKey: `${group.key}:${member.id}`,
      _isPair: false,
      _members: [member],
      // The display row is intentionally flat; only the shared output columns use rowspan.
      thickness: null,
      width: null,
      pitch: null,
      spec_twph: displayTwp,
      material_name: shouldMergeTwpAndCavity
        ? nonEmptyUnique(members.map(item => item.material_name)).join(' / ') || null
        : member.material_name,
      material_name_full: shouldMergeTwpAndCavity
        ? nonEmptyUnique(members.map(item => item.material_name_full)).join(' / ') || null
        : member.material_name_full,
      cavity_count: formatCavityCount(cavity),
      _mergeTwpAndCavity: shouldMergeTwpAndCavity,
      _mergeIndex: index,
      _mergeSize: shouldMergeTwpAndCavity ? members.length : 1,
    }
  })
}

const spanMethod = ({ row, columnIndex }) => {
  if (!row._mergeTwpAndCavity || ![3, 4, 5].includes(columnIndex)) return [1, 1]
  if (row._mergeIndex === 0) return [row._mergeSize, 1]
  return [0, 0]
}

const tableRowClassName = ({ row }) => {
  if (!row._mergeTwpAndCavity) return 'parts-single-row'
  return row._mergeIndex === 0 ? 'parts-group-start' : 'parts-group-member'
}

const visibleParts = computed(() => parts.value)

const handleCompanyChange = (company) => {
  companyStore.setCompany(company)
  if (company === 'gaibo') router.push('/after-sales')
}

const fetchParts = async () => {
  loading.value = true
  listError.value = ''
  try {
    const filterParams = {
      ...(filter.search && { search: filter.search }),
      ...(filter.customer_id && { customer_id: filter.customer_id }),
      ...(filter.part_status && { part_status: filter.part_status }),
      ...(filter.material && { material: filter.material }),
    }
    const params = {
      skip: (page.current - 1) * page.size,
      limit: page.size,
      ...filterParams,
    }
    const data = await partsApi.listGrouped(params)
    appliedSearch.value = String(filter.search || '').trim()
    parts.value = (data.items || []).flatMap(toDisplayRows)
    page.total = data.total || 0
  } catch (e) {
    listError.value = e.message || '零件加载失败，请重试'
    ElMessage.error(e.message || '获取失败')
  } finally {
    loading.value = false
  }
}

const applyFilters = () => {
  page.current = 1
  if (isMobile.value) mobileFiltersOpen.value = false
  fetchParts()
}
const changePageSize = size => {
  page.size = size
  applyFilters()
}

const fetchCustomers = async () => {
  try {
    const data = await customersApi.list({ limit: 200 })
    // API returns CustomerListResponse{items, total}, extract items
    customers.value = data.items || []
  } catch { /* silent */ }
}

const resetFilter = () => {
  appliedSearch.value = ''
  companyStore.setCompany('tianyue'); filter.search = ''; filter.customer_id = null; filter.part_status = ''; filter.material = ''
  page.current = 1; fetchParts()
}

const handleSearchClear = () => {
  appliedSearch.value = ''
  page.current = 1
  fetchParts()
}

const openCreate = () => {
  Object.assign(form, { customer_part_no: '', internal_name: '', customer_id: null, vehicle_model: '', material_name: '', remark: '' })
  dialogVisible.value = true
}

const openEdit = (row) => {
  editPartId.value = row.id
  editorVisible.value = true
}

const handleSelectionChange = (rows) => {
  selectedParts.value = rows
}

const markSelectedForReview = () => {
  ElMessage.info('已标记所选零件，后续可在档案中继续处理')
}

const openPairMember = (row) => {
  if (!row?.id) return
  editPartId.value = row.id
  editorVisible.value = true
}

const handleEditorSaved = async () => {
  await fetchParts()
}

const doSave = async () => {
  await formRef.value?.validate()
  saving.value = true
  try {
    await partsApi.create(form)
    ElMessage.success('已创建')
    dialogVisible.value = false
    fetchParts()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  if (companyStore.selectedCompany === 'gaibo') {
    router.replace('/after-sales')
    return
  }
  fetchParts(); fetchCustomers()
})
</script>

<style scoped>
.parts-container { min-width: 0; overflow-x: hidden; }
.list-view-toolbar { display: grid; grid-template-columns: minmax(150px, .6fr) minmax(260px, 1.6fr) auto; align-items: center; gap: 14px; min-height: 64px; margin-bottom: 10px; padding: 8px 0; }
.list-title-block { display: flex; align-items: center; gap: 10px; min-width: 150px; }
.list-title-block h1 { margin: 0; color: var(--zephyr-ink); font-size: 20px; font-weight: 650; }
.list-caption { display: block; margin-top: 2px; color: #6c7980; font-size: 12px; }
.search-control { width: min(520px, 100%); display: flex; align-items: center; gap: 8px; padding: 4px 10px; border: 1px solid #cbd4d6; border-radius: 4px; background: #fff; color: var(--zephyr-muted); }
.search-control :deep(.el-input__wrapper) { box-shadow: none; padding: 0; }
.filter-controls { display: flex; align-items: center; justify-content: flex-end; gap: 6px; }
.filter-controls :deep(.el-select), .filter-controls :deep(.el-input) { width: 145px; }
.table-meta { display: flex; justify-content: space-between; margin: 0 2px 8px; color: var(--zephyr-muted); font-size: 12px; }
.batch-bar { display: flex; align-items: center; gap: 8px; min-height: 30px; margin: 0 0 6px; padding: 0 2px; color: #7a888c; font-size: 11px; }
.batch-bar .el-button { margin-left: auto; }
.pagination { display: flex; justify-content: flex-end; margin-top: 16px; }
.twp-text { color: var(--zephyr-primary); font-weight: 600; }
.spec-text { color: #909399; font-size: 13px; }
.text-muted { color: #c0c4cc; }
.customer-part-no { color: var(--el-color-success); font-style: italic; }
.customer-part-name { color: var(--el-color-success); font-style: italic; }
.search-hit { background: #fff0a8; color: #5b4300; border-radius: 2px; padding: 0 1px; box-shadow: 0 0 0 1px rgba(184, 134, 11, .15); }
.twp-tag { margin-right: 8px; }
:deep(.el-dropdown + .el-dropdown) { margin-left: 10px; }
:deep(.parts-table) {
  --el-table-border-color: var(--zephyr-border);
  --el-table-header-bg-color: var(--zephyr-surface-muted);
  --el-table-row-hover-bg-color: var(--zephyr-primary-soft);
  --el-table-tr-bg-color: #ffffff;
  border: 1px solid var(--zephyr-border);
  border-radius: 3px;
  overflow: hidden;
  cursor: pointer;
}

/*
 * Keep every row on the same visual grid.  The TWP/material/cavity cells may
 * use rowspan, so Element Plus correctly omits the internal line inside a
 * merged cell; the remaining cells still use this same one-pixel separator.
 */
:deep(.parts-table td.el-table__cell) {
  background-color: #ffffff;
  border-bottom: 1px solid #e7e7ea;
}

/* Desktop density: keep every business column visible within the workbench. */
:deep(.parts-table .cell) { padding: 0 4px; font-size: 11px; line-height: 1.2; }
:deep(.parts-table th.el-table__cell .cell) { padding: 0 4px; font-size: 10px; white-space: nowrap; }
:deep(.parts-table .el-table__header-wrapper col:nth-child(1)),
:deep(.parts-table .el-table__body-wrapper col:nth-child(1)) { width: 36px !important; }
:deep(.parts-table .el-table__header-wrapper col:nth-child(2)),
:deep(.parts-table .el-table__body-wrapper col:nth-child(2)) { width: 96px !important; }
:deep(.parts-table .el-table__header-wrapper col:nth-child(3)),
:deep(.parts-table .el-table__body-wrapper col:nth-child(3)) { width: 126px !important; }
:deep(.parts-table .el-table__header-wrapper col:nth-child(4)),
:deep(.parts-table .el-table__body-wrapper col:nth-child(4)) { width: 96px !important; }
:deep(.parts-table .el-table__header-wrapper col:nth-child(5)),
:deep(.parts-table .el-table__body-wrapper col:nth-child(5)) { width: 108px !important; }
:deep(.parts-table .el-table__header-wrapper col:nth-child(6)),
:deep(.parts-table .el-table__body-wrapper col:nth-child(6)) { width: 78px !important; }
:deep(.parts-table .el-table__header-wrapper col:nth-child(7)),
:deep(.parts-table .el-table__body-wrapper col:nth-child(7)) { width: 48px !important; }
:deep(.parts-table .el-table__header-wrapper col:nth-child(8)),
:deep(.parts-table .el-table__body-wrapper col:nth-child(8)) { width: 92px !important; }
:deep(.parts-table .el-table__header-wrapper col:nth-child(9)),
:deep(.parts-table .el-table__body-wrapper col:nth-child(9)) { width: 78px !important; }
:deep(.parts-table .el-table__header-wrapper col:nth-child(10)),
:deep(.parts-table .el-table__body-wrapper col:nth-child(10)) { width: 92px !important; }
:deep(.parts-table .el-table__header-wrapper col:nth-child(11)),
:deep(.parts-table .el-table__body-wrapper col:nth-child(11)) { width: 64px !important; }
:deep(.parts-table .el-table__header-wrapper col:nth-child(12)),
:deep(.parts-table .el-table__body-wrapper col:nth-child(12)) { width: 100px !important; }
:deep(.parts-table .el-table__header-wrapper),
:deep(.parts-table .el-table__body-wrapper) { overflow-x: auto; }

/* Group boundaries use the same color and width as ordinary row separators. */
:deep(.parts-table tr.parts-group-start > td.el-table__cell),
:deep(.parts-table tr.parts-group-member > td.el-table__cell),
:deep(.parts-table tr.parts-single-row > td.el-table__cell) {
  border-top: 0;
  border-bottom: 1px solid #e7e7ea;
}

@media (max-width: 1200px) {
  .list-view-toolbar { grid-template-columns: minmax(150px, .6fr) minmax(260px, 1.6fr); }
  .filter-controls { grid-column: 1 / -1; justify-content: flex-start; flex-wrap: wrap; }
}
@media (max-width: 900px) {
  .list-view-toolbar { grid-template-columns: 1fr; align-items: stretch; }
  .list-title-block, .filter-controls { justify-content: flex-start; }
  .search-control { width: 100%; }
  .filter-controls { grid-column: auto; flex-wrap: wrap; }
  .filter-controls :deep(.el-select), .filter-controls :deep(.el-input) { width: calc(50% - 4px); }
  .table-meta { gap: 6px; flex-direction: column; }
}
@media (max-width: 620px) {
  .filter-controls :deep(.el-select), .filter-controls :deep(.el-input) { width: 100%; }
}
@media (max-width: 767px) {
  .parts-container .list-view-toolbar { grid-template-columns: minmax(0, 1fr) auto; min-height: 0; gap: 8px; margin-bottom: 8px; }
  .parts-container .list-title-block, .parts-container .filter-controls { grid-column: 1 / -1; }
  .parts-container .list-caption { display: none; }
  .parts-container .table-meta { flex-direction: row; align-items: center; margin-bottom: 8px; font-size: 12px; }
  .mobile-filter-toggle { margin-left: 0; }
  .mobile-parts-list { display: grid; gap: 6px; min-height: 120px; }
  .mobile-part-card { display: block; width: 100%; min-width: 0; padding: 10px 12px; border: 1px solid var(--zephyr-border); border-radius: 6px; background: var(--zephyr-surface); color: var(--zephyr-text); font: inherit; text-align: left; cursor: pointer; }
  .mobile-part-card:active { background: var(--zephyr-primary-soft); }
  .mobile-part-fields { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 6px 16px; }
  .mobile-part-field { min-width: 0; }
  .mobile-part-label { display: block; margin-bottom: 2px; color: var(--zephyr-muted); font-size: 11px; line-height: 14px; }
  .mobile-part-value { display: -webkit-box; overflow: hidden; -webkit-box-orient: vertical; -webkit-line-clamp: 2; color: var(--zephyr-text); font-size: 13px; line-height: 18px; overflow-wrap: anywhere; }
  .mobile-part-number { color: var(--zephyr-primary); font-weight: 600; }
  .pagination { flex-direction: column; gap: 12px; padding-bottom: 12px; }
  .mobile-page-summary { display: flex; align-items: center; justify-content: space-between; width: 100%; gap: 12px; color: var(--zephyr-muted); font-size: 13px; }
  .mobile-page-summary .el-select { width: 130px; }
}
</style>
