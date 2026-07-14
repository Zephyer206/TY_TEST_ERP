<template>
  <div class="parts-container">
    <div class="page-header">
      <h2>零件管理</h2>
      <el-button type="primary" @click="openCreate" v-if="userStore.userInfo?.role_level >= 4">
        <el-icon><Plus /></el-icon>新增零件
      </el-button>
    </div>

    <el-card class="filter-card">
      <el-form :inline="true" :model="filter">
        <el-form-item label="搜索">
          <el-input v-model="filter.search" placeholder="零件编号/名称/模具号" clearable style="width:240px" />
        </el-form-item>
        <el-form-item label="客户">
          <el-select v-model="filter.customer_id" clearable placeholder="全部" style="width:160px" filterable>
            <el-option v-for="c in customers" :key="c.id" :value="c.id"
              :label="c.customer_code ? `${c.customer_code} ${c.name}` : c.name" />
          </el-select>
        </el-form-item>
        <el-form-item label="材料">
          <el-input v-model="filter.material" placeholder="材料名称" clearable style="width:160px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="fetchParts">搜索</el-button>
          <el-button @click="resetFilter">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-table :data="parts" :row-key="row => row._groupKey || row.id" v-loading="loading" stripe>
      <el-table-column prop="part_number" label="零件编号" width="120" fixed />
      <el-table-column prop="internal_name" label="零件名称" min-width="170" />
      <el-table-column prop="mold_number" label="模具号" width="180" />
      <el-table-column label="TWP规格" width="170">
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
      <el-table-column label="材料" width="120">
        <template #default="{ row }">
          <el-tooltip :content="row.material_name_full" placement="top" v-if="row.material_name_full">
            <span>{{ row.material_name || '-' }}</span>
          </el-tooltip>
          <span v-else>{{ row.material_name || '-' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="穴数" width="80" align="center">
        <template #default="{ row }">
          <span v-if="row.cavity_count">{{ row.cavity_count }}</span>
          <span v-else class="text-muted">-</span>
        </template>
      </el-table-column>
      <el-table-column prop="customer_name" label="客户" width="140" />
      <el-table-column prop="mold_type" label="模具类型" width="110" />
      <el-table-column label="位置" width="60" align="center">
        <template #default="{ row }">
          <el-tag v-if="row.part_position === 'both'" type="info" size="small">左右</el-tag>
          <el-tag v-else-if="row.part_position === 'left'" type="info" size="small">左</el-tag>
          <el-tag v-else-if="row.part_position === 'right'" type="info" size="small">右</el-tag>
          <span v-else class="text-muted">-</span>
        </template>
      </el-table-column>
      <el-table-column prop="stock_pcs" label="库存" width="110" align="right" />
      <el-table-column label="操作" width="180" fixed="right">
        <template #default="{ row }">
          <template v-if="row._isPair">
            <el-dropdown trigger="click" @command="viewDetail">
              <el-button link type="primary" size="small">详情</el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item v-for="member in row._members" :key="`detail-${member.id}`" :command="member">
                    {{ positionLabel(member.part_position) }}件详情
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
            <el-dropdown trigger="click" @command="openEdit">
              <el-button link type="primary" size="small">编辑</el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item v-for="member in row._members" :key="`edit-${member.id}`" :command="member">
                    {{ positionLabel(member.part_position) }}件编辑
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
            <el-dropdown trigger="click" @command="handleDelete"
              v-if="row._members.some(member => member.part_status !== 'OBSOLETE')">
              <el-button link type="danger" size="small">删除</el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item v-for="member in row._members" :key="`delete-${member.id}`" :command="member"
                    :disabled="member.part_status === 'OBSOLETE'">
                    删除{{ positionLabel(member.part_position) }}件
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </template>
          <template v-else>
            <el-button link type="primary" size="small" @click="viewDetail(row)">详情</el-button>
            <el-button link type="primary" size="small" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" size="small" @click="handleDelete(row)"
              v-if="row.part_status !== 'OBSOLETE'">删除</el-button>
          </template>
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
        @size-change="fetchParts"
        @current-change="fetchParts"
      />
    </div>

    <!-- 零件详情对话框 -->
    <PartDetailDialog v-model="detailVisible" :detail="detailData" />

    <!-- 新增/编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="editId ? '编辑零件' : '新增零件'" width="520px">
      <el-form :model="form" label-width="90px" :rules="rules" ref="formRef">
        <el-form-item label="零件编号" prop="part_number" v-if="!editId">
          <el-input v-model="form.part_number" placeholder="唯一零件编号" />
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
        <el-form-item label="客户件号">
          <el-input v-model="form.customer_product_no" />
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
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { get, post } from '@/utils/request'
import { useUserStore } from '@/stores/user'
import apiClient from '@/utils/request'
import PartDetailDialog from '@/components/PartDetailDialog.vue'

const userStore = useUserStore()

const parts = ref([])
const customers = ref([])
const loading = ref(false)
const saving = ref(false)
const dialogVisible = ref(false)
const detailVisible = ref(false)
const detailData = ref(null)
const editId = ref(null)
const formRef = ref(null)

const filter = reactive({ search: '', customer_id: null, part_status: '', material: '' })
const page = reactive({ current: 1, size: 20, total: 0 })
const form = reactive({
  part_number: '', internal_name: '', customer_id: null,
  customer_product_no: '', vehicle_model: '', material_name: '', remark: '',
})
const rules = { part_number: [{ required: true, message: '请填写零件编号', trigger: 'blur' }] }

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
  const names = members.map(member => member.internal_name || '').filter(Boolean)
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

  return {
    ...first,
    id: group.key,
    _groupKey: group.key,
    _isPair: true,
    _members: members,
    part_number: uniqueValues(members, 'part_number').join(' / '),
    internal_name: formatPairName(members),
    mold_number: `${baseMoldNumber}（-1/-2）`,
    customer_name: uniqueValues(members, 'customer_name').join(' / '),
    material_name: uniqueValues(members, 'material_name').join(' / '),
    material_name_full: uniqueValues(members, 'material_name_full').join(' / '),
    mold_type: uniqueValues(members, 'mold_type').join(' / '),
    part_status: statuses.length === 1 ? statuses[0] : 'MIXED',
    stock_pcs: stockByPosition,
    spec_twph: firstValue(members, 'spec_twph'),
    thickness: firstValue(members, 'thickness'),
    width: firstValue(members, 'width'),
    pitch: firstValue(members, 'pitch'),
    cavity_count: 2,
    part_position: 'both',
  }
}

const fetchParts = async () => {
  loading.value = true
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
    const data = await get('/parts/grouped', params)
    parts.value = (data.items || []).map(toDisplayRow)
    page.total = data.total || 0
  } catch (e) {
    ElMessage.error(e.message || '获取失败')
  } finally {
    loading.value = false
  }
}

const fetchCustomers = async () => {
  try {
    customers.value = await get('/customers', { limit: 200, has_parts: true })
  } catch { /* silent */ }
}

const resetFilter = () => {
  filter.search = ''; filter.customer_id = null; filter.part_status = ''; filter.material = ''
  page.current = 1; fetchParts()
}

const viewDetail = async (row) => {
  try {
    // Fetch full detail with relationships from new API
    const detail = await get(`/parts/${row.id}/detail`)
    detailData.value = detail
    detailVisible.value = true
  } catch (e) {
    ElMessage.error('获取详情失败: ' + (e.message || '未知错误'))
  }
}

const openEditFromDetail = () => {
  detailVisible.value = false
  openEdit(detailData.value)
}

const openCreate = () => {
  editId.value = null
  Object.assign(form, { part_number: '', internal_name: '', customer_id: null, customer_product_no: '', vehicle_model: '', material_name: '', remark: '' })
  dialogVisible.value = true
}

const openEdit = (row) => {
  editId.value = row.id
  Object.assign(form, {
    part_number: row.part_number,
    internal_name: row.internal_name || '',
    customer_id: row.customer_id,
    customer_product_no: row.customer_product_no || '',
    vehicle_model: row.vehicle_model || '',
    material_name: row.material_name || '',
    remark: row.remark || '',
  })
  dialogVisible.value = true
}

const doSave = async () => {
  await formRef.value?.validate()
  saving.value = true
  try {
    if (editId.value) {
      await apiClient.patch(`/parts/${editId.value}`, form)
      ElMessage.success('已更新')
    } else {
      await post('/parts', form)
      ElMessage.success('已创建')
    }
    dialogVisible.value = false
    fetchParts()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    saving.value = false
  }
}

const handleDelete = async (row) => {
  await ElMessageBox.confirm(`确认删除零件「${row.internal_name || row.part_number}」？删除后状态改为淘汰。`, '确认', { type: 'warning' })
  try {
    await apiClient.delete(`/parts/${row.id}`)
    ElMessage.success('已删除')
    fetchParts()
  } catch (e) {
    ElMessage.error(e.message)
  }
}

onMounted(() => { fetchParts(); fetchCustomers() })
</script>

<style scoped>
.parts-container { padding: 20px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.page-header h2 { margin: 0; }
.filter-card { margin-bottom: 16px; }
.pagination { display: flex; justify-content: flex-end; margin-top: 16px; }
.twp-text { color: #409eff; font-weight: 500; }
.spec-text { color: #909399; font-size: 13px; }
.text-muted { color: #c0c4cc; }
.twp-tag { margin-right: 8px; }
:deep(.el-dropdown + .el-dropdown) { margin-left: 10px; }
</style>
