<template>
  <div class="sampling-container">
    <el-card class="header-card">
      <div class="header-content">
        <h2>打样任务管理</h2>
        <el-button type="primary" @click="showCreateDialog = true">
          <el-icon><Plus /></el-icon>
          创建打样任务
        </el-button>
      </div>
    </el-card>

    <!-- 筛选条件 -->
    <el-card class="filter-card">
      <el-form :inline="true" :model="filters">
        <el-form-item label="状态">
          <el-select v-model="filters.status" placeholder="全部状态" clearable style="width: 150px">
            <el-option label="待启动" value="pending" />
            <el-option label="打样中" value="sampling" />
            <el-option label="待评审" value="review_pending" />
            <el-option label="已通过" value="approved" />
            <el-option label="未通过" value="rejected" />
            <el-option label="已取消" value="cancelled" />
          </el-select>
        </el-form-item>
        <el-form-item label="零件名称">
          <el-input v-model="filters.partName" placeholder="输入零件名称" clearable style="width: 200px" />
        </el-form-item>
        <el-form-item label="创建时间">
          <el-date-picker
            v-model="filters.dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            style="width: 280px"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadData">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 打样任务列表 -->
    <el-card>
      <el-table :data="taskList" v-loading="loading" border stripe>
        <el-table-column prop="taskNo" label="任务编号" width="150" />
        <el-table-column prop="partName" label="零件名称" width="180" />
        <el-table-column prop="customerName" label="客户名称" width="150" />
        <el-table-column prop="quantity" label="打样数量" width="100" align="center" />
        <el-table-column prop="status" label="状态" width="120" align="center">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">
              {{ getStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="createdBy" label="创建人" width="100" />
        <el-table-column prop="createdAt" label="创建时间" width="160" />
        <el-table-column prop="deadline" label="截止日期" width="120" />
        <el-table-column label="操作" width="240" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="viewDetail(row.id)">查看详情</el-button>
            <el-button
              v-if="row.status === 'pending'"
              type="success"
              link
              @click="startSampling(row.id)"
            >
              开始打样
            </el-button>
            <el-button
              v-if="row.status === 'review_pending'"
              type="warning"
              link
              @click="goToReview(row.id)"
            >
              去评审
            </el-button>
            <el-button
              v-if="['pending', 'sampling'].includes(row.status)"
              type="danger"
              link
              @click="cancelTask(row.id)"
            >
              取消
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

    <!-- 创建打样任务对话框 -->
    <el-dialog
      v-model="showCreateDialog"
      title="创建打样任务"
      width="600px"
      :close-on-click-modal="false"
    >
      <el-form :model="createForm" :rules="createRules" ref="createFormRef" label-width="100px">
        <el-form-item label="选择零件" prop="partId">
          <el-select v-model="createForm.partId" placeholder="请选择零件" filterable style="width: 100%">
            <el-option
              v-for="part in partsList"
              :key="part.id"
              :label="`${part.partName} (${part.customerName})`"
              :value="part.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="打样数量" prop="quantity">
          <el-input-number v-model="createForm.quantity" :min="1" :max="10000" style="width: 100%" />
        </el-form-item>
        <el-form-item label="截止日期" prop="deadline">
          <el-date-picker
            v-model="createForm.deadline"
            type="date"
            placeholder="选择截止日期"
            style="width: 100%"
            :disabled-date="disabledDate"
          />
        </el-form-item>
        <el-form-item label="打样要求" prop="requirements">
          <el-input
            v-model="createForm.requirements"
            type="textarea"
            :rows="4"
            placeholder="请输入打样要求"
          />
        </el-form-item>
        <el-form-item label="参考资料">
          <el-upload
            class="upload-demo"
            :action="uploadUrl"
            :on-success="handleUploadSuccess"
            :file-list="createForm.attachments"
            multiple
          >
            <el-button size="small">点击上传</el-button>
            <template #tip>
              <div class="el-upload__tip">支持上传图片、PDF等文件</div>
            </template>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="submitCreate" :loading="submitting">提交</el-button>
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

// 筛选条件
const filters = reactive({
  status: '',
  partName: '',
  dateRange: null as any
})

// 分页
const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

// 打样任务列表
const taskList = ref<any[]>([])

// 零件列表
const partsList = ref<any[]>([])

// 创建表单
const createFormRef = ref<FormInstance>()
const createForm = reactive({
  partId: null as any,
  quantity: 100,
  deadline: '',
  requirements: '',
  attachments: [] as any[]
})

const createRules: FormRules = {
  partId: [{ required: true, message: '请选择零件', trigger: 'change' }],
  quantity: [{ required: true, message: '请输入打样数量', trigger: 'blur' }],
  deadline: [{ required: true, message: '请选择截止日期', trigger: 'change' }],
  requirements: [{ required: true, message: '请输入打样要求', trigger: 'blur' }]
}

// 上传地址
const uploadUrl = ref('/api/v1/upload')

// 加载数据
const loadData = async () => {
  loading.value = true
  try {
    // TODO: 调用 API 获取打样任务列表
    // const response = await api.sampling.list({
    //   ...filters,
    //   page: pagination.page,
    //   pageSize: pagination.pageSize
    // })
    // taskList.value = response.data.items
    // pagination.total = response.data.total

    // 模拟数据
    taskList.value = [
      {
        id: 1,
        taskNo: 'SAMPLE-2026-001',
        partName: '冲压件A',
        customerName: '客户A',
        quantity: 100,
        status: 'pending',
        createdBy: '张三',
        createdAt: '2026-06-20 10:00:00',
        deadline: '2026-06-25'
      }
    ]
    pagination.total = 1
  } catch (error) {
    ElMessage.error('加载数据失败')
  } finally {
    loading.value = false
  }
}

// 加载零件列表
const loadParts = async () => {
  try {
    // TODO: 调用 API 获取零件列表
    // const response = await api.parts.list()
    // partsList.value = response.data

    // 模拟数据
    partsList.value = [
      { id: 1, partName: '冲压件A', customerName: '客户A' },
      { id: 2, partName: '冲压件B', customerName: '客户B' }
    ]
  } catch (error) {
    ElMessage.error('加载零件列表失败')
  }
}

// 重置筛选
const resetFilters = () => {
  filters.status = ''
  filters.partName = ''
  filters.dateRange = null
  loadData()
}

// 状态类型
const getStatusType = (status: string) => {
  const typeMap: any = {
    pending: '',
    sampling: 'warning',
    review_pending: 'info',
    approved: 'success',
    rejected: 'danger',
    cancelled: 'info'
  }
  return typeMap[status] || ''
}

// 状态文本
const getStatusText = (status: string) => {
  const textMap: any = {
    pending: '待启动',
    sampling: '打样中',
    review_pending: '待评审',
    approved: '已通过',
    rejected: '未通过',
    cancelled: '已取消'
  }
  return textMap[status] || status
}

// 查看详情
const viewDetail = (id: number) => {
  router.push(`/sampling/detail/${id}`)
}

// 开始打样
const startSampling = async (id: number) => {
  try {
    await ElMessageBox.confirm('确认开始打样吗？', '提示', {
      confirmButtonText: '确认',
      cancelButtonText: '取消',
      type: 'warning'
    })
    // TODO: 调用 API
    // await api.sampling.start(id)
    ElMessage.success('操作成功')
    loadData()
  } catch (error) {
    // 用户取消
  }
}

// 去评审
const goToReview = (id: number) => {
  router.push(`/sampling/review/${id}`)
}

// 取消任务
const cancelTask = async (id: number) => {
  try {
    await ElMessageBox.confirm('确认取消此打样任务吗？', '提示', {
      confirmButtonText: '确认',
      cancelButtonText: '取消',
      type: 'warning'
    })
    // TODO: 调用 API
    // await api.sampling.cancel(id)
    ElMessage.success('已取消')
    loadData()
  } catch (error) {
    // 用户取消
  }
}

// 提交创建
const submitCreate = async () => {
  if (!createFormRef.value) return
  await createFormRef.value.validate(async (valid) => {
    if (valid) {
      submitting.value = true
      try {
        // TODO: 调用 API
        // await api.sampling.create(createForm)
        ElMessage.success('创建成功，等待老板审批')
        showCreateDialog.value = false
        loadData()
      } catch (error) {
        ElMessage.error('创建失败')
      } finally {
        submitting.value = false
      }
    }
  })
}

// 上传成功
const handleUploadSuccess = (response: any, file: any) => {
  createForm.attachments.push(file)
}

// 禁用过去的日期
const disabledDate = (time: Date) => {
  return time.getTime() < Date.now() - 8.64e7
}

onMounted(() => {
  loadData()
  loadParts()
})
</script>

<style scoped lang="scss">
.sampling-container {
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
