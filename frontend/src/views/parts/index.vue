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
            <el-option v-for="c in customers" :key="c.id" :value="c.id" :label="c.name" />
          </el-select>
        </el-form-item>
        <el-form-item label="材料">
          <el-input v-model="filter.material" placeholder="材料名称" clearable style="width:160px" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filter.part_status" clearable placeholder="全部" style="width:120px">
            <el-option label="草稿" value="DRAFT" />
            <el-option label="打样" value="SAMPLING" />
            <el-option label="量产" value="MASS_PRODUCTION" />
            <el-option label="淘汰" value="OBSOLETE" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="fetchParts">搜索</el-button>
          <el-button @click="resetFilter">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-table :data="parts" v-loading="loading" stripe>
      <el-table-column prop="part_number" label="零件编号" width="120" fixed />
      <el-table-column prop="internal_name" label="零件名称" min-width="140" />
      <el-table-column prop="mold_number" label="模具号" width="120" />
      <el-table-column label="TWP规格" width="140">
        <template #default="{ row }">
          <span v-if="row.thickness || row.width || row.pitch" class="twp-text">
            <span v-if="row.thickness">T{{ row.thickness }}</span>
            <span v-if="row.width">×W{{ row.width }}</span>
            <span v-if="row.pitch">×P{{ row.pitch }}</span>
          </span>
          <span v-else-if="row.spec_twph" class="spec-text">{{ row.spec_twph }}</span>
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
          <el-tag v-if="row.part_position === 'left'" type="info" size="small">左</el-tag>
          <el-tag v-else-if="row.part_position === 'right'" type="info" size="small">右</el-tag>
          <span v-else class="text-muted">-</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="statusType(row.part_status)" size="small">{{ statusLabel(row.part_status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="stock_pcs" label="库存" width="70" align="right" />
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" size="small" @click="viewDetail(row)">详情</el-button>
          <el-button link type="primary" size="small" @click="openEdit(row)">编辑</el-button>
          <el-button link type="danger" size="small" @click="handleDelete(row)"
            v-if="row.part_status !== 'OBSOLETE'">删除</el-button>
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
            <el-option v-for="c in customers" :key="c.id" :value="c.id" :label="c.name" />
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
}
const statusLabel = s => STATUS_MAP[s]?.label || s
const statusType = s => STATUS_MAP[s]?.type || 'info'

const fetchParts = async () => {
  loading.value = true
  try {
    const params = {
      skip: (page.current - 1) * page.size,
      limit: page.size,
      ...(filter.search && { search: filter.search }),
      ...(filter.customer_id && { customer_id: filter.customer_id }),
      ...(filter.part_status && { part_status: filter.part_status }),
      ...(filter.material && { material: filter.material }),
    }
    const data = await get('/parts', params)
    parts.value = Array.isArray(data) ? data : (data.items || [])
    page.total = data.total || parts.value.length
  } catch (e) {
    ElMessage.error(e.message || '获取失败')
  } finally {
    loading.value = false
  }
}

const fetchCustomers = async () => {
  try {
    customers.value = await get('/customers')
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
</style>
