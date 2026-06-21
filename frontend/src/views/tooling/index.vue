<template>
  <div class="tooling-container">
    <el-card class="header-card">
      <div class="header-content">
        <h2>模具管理</h2>
        <el-button type="primary" @click="showCreateDialog = true">
          <el-icon><Plus /></el-icon>
          新增模具
        </el-button>
      </div>
    </el-card>

    <!-- 筛选条件 -->
    <el-card class="filter-card">
      <el-form :inline="true" :model="filters">
        <el-form-item label="模具状态">
          <el-select v-model="filters.status" placeholder="全部状态" clearable style="width: 150px">
            <el-option label="可用" value="available" />
            <el-option label="使用中" value="in_use" />
            <el-option label="维修中" value="maintenance" />
            <el-option label="报废" value="scrapped" />
          </el-select>
        </el-form-item>
        <el-form-item label="客户">
          <el-input v-model="filters.customer" placeholder="客户名称" clearable style="width: 150px" />
        </el-form-item>
        <el-form-item label="模具号">
          <el-input v-model="filters.toolingNo" placeholder="模具号" clearable style="width: 150px" />
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="filters.type" placeholder="全部类型" clearable style="width: 120px">
            <el-option label="单工序" value="single" />
            <el-option label="连续模" value="progressive" />
            <el-option label="复合模" value="compound" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadData">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 模具列表 -->
    <el-card>
      <el-table :data="toolingList" v-loading="loading" border stripe>
        <el-table-column prop="toolingNo" label="模具号" width="140" fixed="left" />
        <el-table-column prop="customerName" label="客户" width="150" />
        <el-table-column prop="customerPartNo" label="客户产品号" width="150" />
        <el-table-column prop="type" label="类型" width="100" align="center">
          <template #default="{ row }">
            {{ getTypeText(row.type) }}
          </template>
        </el-table-column>
        <el-table-column prop="cavities" label="穴数" width="80" align="center" />
        <el-table-column prop="tonnage" label="吨位" width="80" align="center">
          <template #default="{ row }">
            {{ row.tonnage }}T
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">
              {{ getStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="totalShots" label="累计冲次" width="120" align="center">
          <template #default="{ row }">
            {{ formatNumber(row.totalShots) }}
          </template>
        </el-table-column>
        <el-table-column prop="maintenanceCount" label="维修次数" width="100" align="center" />
        <el-table-column prop="location" label="存放位置" width="120" />
        <el-table-column prop="createdAt" label="入库日期" width="110" />
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="viewDetail(row.id)">详情</el-button>
            <el-button type="warning" link @click="goToMaintenance(row.id)">维修</el-button>
            <el-button type="success" link @click="handleEdit(row)">编辑</el-button>
            <el-button
              v-if="row.status !== 'scrapped'"
              type="danger"
              link
              @click="handleScrap(row.id)"
            >
              报废
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="pagination-container">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :page-sizes="[10, 20, 50, 100]"
          :total="pagination.total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="loadData"
          @current-change="loadData"
        />
      </div>
    </el-card>

    <!-- 新增/编辑模具对话框 -->
    <el-dialog
      v-model="showCreateDialog"
      :title="editMode ? '编辑模具' : '新增模具'"
      width="700px"
      :close-on-click-modal="false"
    >
      <el-form :model="toolingForm" :rules="toolingRules" ref="toolingFormRef" label-width="120px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="模具号" prop="toolingNo">
              <el-input v-model="toolingForm.toolingNo" placeholder="如：M-2026-001" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="客户" prop="customerId">
              <el-select v-model="toolingForm.customerId" placeholder="选择客户" style="width: 100%">
                <el-option
                  v-for="customer in customersList"
                  :key="customer.id"
                  :label="customer.name"
                  :value="customer.id"
                />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="客户产品号" prop="customerPartNo">
              <el-input v-model="toolingForm.customerPartNo" placeholder="客户提供的产品号" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="模具类型" prop="type">
              <el-select v-model="toolingForm.type" placeholder="选择类型" style="width: 100%">
                <el-option label="单工序" value="single" />
                <el-option label="连续模" value="progressive" />
                <el-option label="复合模" value="compound" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="穴数" prop="cavities">
              <el-input-number v-model="toolingForm.cavities" :min="1" :max="100" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="吨位(T)" prop="tonnage">
              <el-input-number v-model="toolingForm.tonnage" :min="10" :max="2000" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="存放位置" prop="location">
              <el-input v-model="toolingForm.location" placeholder="如：A区01" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="模具尺寸">
              <el-input v-model="toolingForm.size" placeholder="长×宽×高(mm)" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="理论寿命">
              <el-input-number v-model="toolingForm.designedLife" :min="0" style="width: 100%" />
              <span style="margin-left: 8px">万次</span>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="备注">
          <el-input v-model="toolingForm.notes" type="textarea" :rows="3" placeholder="其他说明信息" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="submitTooling" :loading="submitting">
          {{ editMode ? '保存' : '创建' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import type { FormInstance, FormRules } from 'element-plus'

const router = useRouter()

// 状态
const loading = ref(false)
const showCreateDialog = ref(false)
const submitting = ref(false)
const editMode = ref(false)

// 筛选条件
const filters = reactive({
  status: '',
  customer: '',
  toolingNo: '',
  type: ''
})

// 分页
const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

// 模具列表
const toolingList = ref<any[]>([])

// 客户列表
const customersList = ref<any[]>([])

// 模具表单
const toolingFormRef = ref<FormInstance>()
const toolingForm = reactive({
  id: null as any,
  toolingNo: '',
  customerId: null as any,
  customerPartNo: '',
  type: '',
  cavities: 1,
  tonnage: 100,
  location: '',
  size: '',
  designedLife: 1000000,
  notes: ''
})

const toolingRules: FormRules = {
  toolingNo: [{ required: true, message: '请输入模具号', trigger: 'blur' }],
  customerId: [{ required: true, message: '请选择客户', trigger: 'change' }],
  customerPartNo: [{ required: true, message: '请输入客户产品号', trigger: 'blur' }],
  type: [{ required: true, message: '请选择模具类型', trigger: 'change' }],
  cavities: [{ required: true, message: '请输入穴数', trigger: 'blur' }],
  tonnage: [{ required: true, message: '请输入吨位', trigger: 'blur' }],
  location: [{ required: true, message: '请输入存放位置', trigger: 'blur' }]
}

// 加载数据
const loadData = async () => {
  loading.value = true
  try {
    // TODO: 调用 API
    // const response = await api.tooling.list({...filters, ...pagination})

    // 模拟数据
    toolingList.value = [
      {
        id: 1,
        toolingNo: 'M-2026-001',
        customerName: '客户A',
        customerPartNo: 'PA-001',
        type: 'progressive',
        cavities: 2,
        tonnage: 150,
        status: 'available',
        totalShots: 1500000,
        maintenanceCount: 3,
        location: 'A区01',
        createdAt: '2026-01-15'
      }
    ]
    pagination.total = 1
  } catch (error) {
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
}

// 加载客户列表
const loadCustomers = async () => {
  try {
    // TODO: 调用 API
    customersList.value = [
      { id: 1, name: '客户A' },
      { id: 2, name: '客户B' }
    ]
  } catch (error) {
    ElMessage.error('加载客户列表失败')
  }
}

// 重置筛选
const resetFilters = () => {
  filters.status = ''
  filters.customer = ''
  filters.toolingNo = ''
  filters.type = ''
  loadData()
}

// 类型文本
const getTypeText = (type: string) => {
  const typeMap: any = {
    single: '单工序',
    progressive: '连续模',
    compound: '复合模'
  }
  return typeMap[type] || type
}

// 状态类型和文本
const getStatusType = (status: string) => {
  const typeMap: any = {
    available: 'success',
    in_use: 'warning',
    maintenance: 'info',
    scrapped: 'danger'
  }
  return typeMap[status] || ''
}

const getStatusText = (status: string) => {
  const textMap: any = {
    available: '可用',
    in_use: '使用中',
    maintenance: '维修中',
    scrapped: '报废'
  }
  return textMap[status] || status
}

// 格式化数字
const formatNumber = (num: number) => {
  return num?.toLocaleString() || '0'
}

// 查看详情
const viewDetail = (id: number) => {
  router.push(`/tooling/detail/${id}`)
}

// 去维修
const goToMaintenance = (id: number) => {
  router.push(`/tooling/maintenance/${id}`)
}

// 编辑
const handleEdit = (row: any) => {
  editMode.value = true
  Object.assign(toolingForm, row)
  showCreateDialog.value = true
}

// 报废
const handleScrap = async (id: number) => {
  try {
    await ElMessageBox.confirm('确认报废此模具吗？报废后将无法恢复。', '确认报废', {
      confirmButtonText: '确认',
      cancelButtonText: '取消',
      type: 'warning'
    })
    // TODO: 调用 API
    // await api.tooling.scrap(id)
    ElMessage.success('已报废')
    loadData()
  } catch (error) {
    // 用户取消
  }
}

// 提交
const submitTooling = async () => {
  if (!toolingFormRef.value) return
  await toolingFormRef.value.validate(async (valid) => {
    if (valid) {
      submitting.value = true
      try {
        // TODO: 调用 API
        // if (editMode.value) {
        //   await api.tooling.update(toolingForm.id, toolingForm)
        // } else {
        //   await api.tooling.create(toolingForm)
        // }
        ElMessage.success(editMode.value ? '保存成功' : '创建成功')
        showCreateDialog.value = false
        loadData()
      } catch (error) {
        ElMessage.error(editMode.value ? '保存失败' : '创建失败')
      } finally {
        submitting.value = false
      }
    }
  })
}

onMounted(() => {
  loadData()
  loadCustomers()
})
</script>

<style scoped lang="scss">
.tooling-container {
  padding: 20px;

  .header-card {
    margin-bottom: 20px;
  }

  .header-content {
    display: flex;
    justify-content: space-between;
    align-items: center;

    h2 {
      margin: 0;
      font-size: 20px;
      font-weight: 500;
    }
  }

  .filter-card {
    margin-bottom: 20px;
  }

  .pagination-container {
    margin-top: 20px;
    display: flex;
    justify-content: flex-end;
  }
}
</style>
