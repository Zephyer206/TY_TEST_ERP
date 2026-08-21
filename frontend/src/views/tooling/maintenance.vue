<template>
  <div class="maintenance-container">
    <el-page-header @back="goBack" title="返回">
      <template #content>
        <span class="page-title">模具维修管理</span>
      </template>
    </el-page-header>

    <div class="content-wrapper" v-loading="loading">
      <!-- 模具信息 -->
      <el-card class="tooling-info-card">
        <el-descriptions :column="4" border>
          <el-descriptions-item label="模具号">
            <el-text tag="b">{{ toolingInfo.toolingNo }}</el-text>
          </el-descriptions-item>
          <el-descriptions-item label="客户">{{ toolingInfo.customerName }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="getStatusType(toolingInfo.status)">
              {{ getStatusText(toolingInfo.status) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="累计维修">{{ toolingInfo.maintenanceCount || 0 }} 次</el-descriptions-item>
        </el-descriptions>
      </el-card>

      <!-- 报修按钮 -->
      <el-card class="actions-card" v-if="toolingInfo.status !== 'maintenance'">
        <el-button type="warning" size="large" @click="showReportDialog = true">
          <el-icon><Tools /></el-icon>
          报修
        </el-button>
      </el-card>

      <!-- 维修记录列表 -->
      <el-card class="records-card">
        <template #header>
          <div class="card-header">
            <span class="card-title">维修记录</span>
            <el-radio-group v-model="statusFilter" @change="loadRecords">
              <el-radio-button label="">全部</el-radio-button>
              <el-radio-button label="pending">待维修</el-radio-button>
              <el-radio-button label="in_progress">维修中</el-radio-button>
              <el-radio-button label="completed">已完成</el-radio-button>
            </el-radio-group>
          </div>
        </template>

        <el-table :data="maintenanceRecords" border stripe>
          <el-table-column type="expand">
            <template #default="{ row }">
              <div class="expand-content">
                <el-descriptions :column="2" border>
                  <el-descriptions-item label="故障描述" :span="2">
                    {{ row.issue }}
                  </el-descriptions-item>
                  <el-descriptions-item label="维修方案" :span="2" v-if="row.solution">
                    {{ row.solution }}
                  </el-descriptions-item>
                  <el-descriptions-item label="维修说明" :span="2" v-if="row.notes">
                    {{ row.notes }}
                  </el-descriptions-item>
                  <el-descriptions-item label="更换部件" v-if="row.replacedParts">
                    {{ row.replacedParts }}
                  </el-descriptions-item>
                  <el-descriptions-item label="费用明细" v-if="row.costDetail">
                    {{ row.costDetail }}
                  </el-descriptions-item>
                </el-descriptions>
                <div class="photos" v-if="row.photos?.length" style="margin-top: 16px">
                  <div style="margin-bottom: 8px"><strong>故障照片：</strong></div>
                  <el-image
                    v-for="photo in row.photos"
                    :key="photo"
                    :src="photo"
                    :preview-src-list="row.photos"
                    fit="cover"
                    style="width: 100px; height: 100px; margin-right: 10px; border-radius: 4px"
                  />
                </div>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="reportDate" label="报修日期" width="110" />
          <el-table-column prop="reportBy" label="报修人" width="100" />
          <el-table-column prop="issue" label="故障描述" min-width="200" show-overflow-tooltip />
          <el-table-column prop="priority" label="优先级" width="80" align="center">
            <template #default="{ row }">
              <el-tag :type="getPriorityType(row.priority)" size="small">
                {{ getPriorityText(row.priority) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="100" align="center">
            <template #default="{ row }">
              <el-tag :type="getRecordStatusType(row.status)">
                {{ getRecordStatusText(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="maintainedBy" label="维修人" width="100" />
          <el-table-column prop="maintainedAt" label="完成时间" width="160" />
          <el-table-column prop="cost" label="费用" width="100" align="right">
            <template #default="{ row }">
              {{ row.cost ? '¥' + row.cost.toFixed(2) : '-' }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="180" fixed="right">
            <template #default="{ row }">
              <el-button
                v-if="row.status === 'pending'"
                type="primary"
                link
                @click="handleStart(row)"
              >
                开始维修
              </el-button>
              <el-button
                v-if="row.status === 'in_progress'"
                type="success"
                link
                @click="handleComplete(row)"
              >
                完成维修
              </el-button>
              <el-button type="info" link @click="viewDetail(row)">详情</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </div>

    <!-- 报修对话框 -->
    <el-dialog
      v-model="showReportDialog"
      title="报修"
      width="600px"
      :close-on-click-modal="false"
    >
      <el-form :model="reportForm" :rules="reportRules" ref="reportFormRef" label-width="100px">
        <el-form-item label="故障描述" prop="issue">
          <el-input
            v-model="reportForm.issue"
            type="textarea"
            :rows="4"
            placeholder="请详细描述故障现象"
            maxlength="500"
            show-word-limit
          />
        </el-form-item>
        <el-form-item label="优先级" prop="priority">
          <el-radio-group v-model="reportForm.priority">
            <el-radio label="low">低</el-radio>
            <el-radio label="medium">中</el-radio>
            <el-radio label="high">高</el-radio>
            <el-radio label="urgent">紧急</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="故障照片">
          <el-upload
            v-model:file-list="reportForm.photoList"
            action="#"
            list-type="picture-card"
            :auto-upload="false"
            accept="image/*"
          >
            <el-icon><Plus /></el-icon>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showReportDialog = false">取消</el-button>
        <el-button type="primary" @click="submitReport" :loading="submitting">提交报修</el-button>
      </template>
    </el-dialog>

    <!-- 完成维修对话框 -->
    <el-dialog
      v-model="showCompleteDialog"
      title="完成维修"
      width="600px"
      :close-on-click-modal="false"
    >
      <el-form :model="completeForm" :rules="completeRules" ref="completeFormRef" label-width="100px">
        <el-form-item label="维修方案" prop="solution">
          <el-input
            v-model="completeForm.solution"
            type="textarea"
            :rows="3"
            placeholder="请描述维修方案"
          />
        </el-form-item>
        <el-form-item label="维修说明">
          <el-input
            v-model="completeForm.notes"
            type="textarea"
            :rows="3"
            placeholder="维修过程说明、注意事项等"
          />
        </el-form-item>
        <el-form-item label="更换部件">
          <el-input v-model="completeForm.replacedParts" placeholder="如：冲头×2、弹簧×1" />
        </el-form-item>
        <el-form-item label="维修费用" prop="cost">
          <el-input-number v-model="completeForm.cost" :min="0" :precision="2" style="width: 200px" />
          <span style="margin-left: 10px">元</span>
        </el-form-item>
        <el-form-item label="费用明细">
          <el-input v-model="completeForm.costDetail" placeholder="人工费、材料费等" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCompleteDialog = false">取消</el-button>
        <el-button type="primary" @click="submitComplete" :loading="submitting">确认完成</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Tools, Plus } from '@element-plus/icons-vue'
import type { FormInstance, FormRules, UploadFile } from 'element-plus'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const submitting = ref(false)
const showReportDialog = ref(false)
const showCompleteDialog = ref(false)
const statusFilter = ref('')
const currentRecord = ref<any>(null)

// 模具信息
const toolingInfo = ref<any>({})

// 维修记录
const maintenanceRecords = ref<any[]>([])

// 报修表单
const reportFormRef = ref<FormInstance>()
const reportForm = reactive({
  issue: '',
  priority: 'medium',
  photoList: [] as UploadFile[]
})

const reportRules: FormRules = {
  issue: [
    { required: true, message: '请输入故障描述', trigger: 'blur' },
    { min: 10, message: '故障描述至少10个字符', trigger: 'blur' }
  ],
  priority: [{ required: true, message: '请选择优先级', trigger: 'change' }]
}

// 完成维修表单
const completeFormRef = ref<FormInstance>()
const completeForm = reactive({
  solution: '',
  notes: '',
  replacedParts: '',
  cost: 0,
  costDetail: ''
})

const completeRules: FormRules = {
  solution: [{ required: true, message: '请输入维修方案', trigger: 'blur' }],
  cost: [{ required: true, message: '请输入维修费用', trigger: 'blur' }]
}

// 加载模具信息
const loadToolingInfo = async () => {
  try {
    const id = route.params.id
    // TODO: 调用 API
    toolingInfo.value = {
      id,
      toolingNo: 'M-2026-001',
      customerName: '客户A',
      status: 'available',
      maintenanceCount: 3
    }
  } catch (error) {
    ElMessage.error('加载失败')
  }
}

// 加载维修记录
const loadRecords = async () => {
  loading.value = true
  try {
    // TODO: 调用 API
    maintenanceRecords.value = [
      {
        id: 1,
        reportDate: '2026-05-15',
        reportBy: '李四',
        issue: '冲头磨损严重，冲压件有毛刺',
        priority: 'high',
        status: 'completed',
        solution: '更换冲头',
        maintainedBy: '王五',
        maintainedAt: '2026-05-16 15:30',
        cost: 1200,
        notes: '已更换新冲头，测试正常',
        replacedParts: '冲头×2',
        costDetail: '冲头800元 + 人工400元',
        photos: []
      }
    ]
  } catch (error) {
    ElMessage.error('加载记录失败')
  } finally {
    loading.value = false
  }
}

// 提交报修
const submitReport = async () => {
  if (!reportFormRef.value) return
  await reportFormRef.value.validate(async (valid) => {
    if (valid) {
      submitting.value = true
      try {
        // TODO: 上传照片并调用 API
        // await api.tooling.reportMaintenance(toolingInfo.value.id, reportForm)
        ElMessage.success('报修成功')
        showReportDialog.value = false
        loadRecords()
        loadToolingInfo()
      } catch (error) {
        ElMessage.error('报修失败')
      } finally {
        submitting.value = false
      }
    }
  })
}

// 开始维修
const handleStart = async (_record: any) => {
  try {
    // TODO: 调用 API
    // await api.tooling.startMaintenance(record.id)
    ElMessage.success('已开始维修')
    loadRecords()
    loadToolingInfo()
  } catch (error) {
    ElMessage.error('操作失败')
  }
}

// 完成维修
const handleComplete = (record: any) => {
  currentRecord.value = record
  showCompleteDialog.value = true
}

// 提交完成
const submitComplete = async () => {
  if (!completeFormRef.value) return
  await completeFormRef.value.validate(async (valid) => {
    if (valid) {
      submitting.value = true
      try {
        // TODO: 调用 API
        // await api.tooling.completeMaintenance(currentRecord.value.id, completeForm)
        ElMessage.success('维修已完成')
        showCompleteDialog.value = false
        loadRecords()
        loadToolingInfo()
      } catch (error) {
        ElMessage.error('操作失败')
      } finally {
        submitting.value = false
      }
    }
  })
}

// 查看详情
const viewDetail = (_record: any) => {
  ElMessage.info('详情功能')
}

// 辅助函数
const getStatusType = (status: string) => {
  const map: any = { available: 'success', in_use: 'warning', maintenance: 'info', scrapped: 'danger' }
  return map[status] || ''
}

const getStatusText = (status: string) => {
  const map: any = { available: '可用', in_use: '使用中', maintenance: '维修中', scrapped: '报废' }
  return map[status] || status
}

const getPriorityType = (priority: string) => {
  const map: any = { low: 'info', medium: '', high: 'warning', urgent: 'danger' }
  return map[priority] || ''
}

const getPriorityText = (priority: string) => {
  const map: any = { low: '低', medium: '中', high: '高', urgent: '紧急' }
  return map[priority] || priority
}

const getRecordStatusType = (status: string) => {
  const map: any = { pending: 'warning', in_progress: 'primary', completed: 'success' }
  return map[status] || ''
}

const getRecordStatusText = (status: string) => {
  const map: any = { pending: '待维修', in_progress: '维修中', completed: '已完成' }
  return map[status] || status
}

const goBack = () => router.back()

onMounted(() => {
  loadToolingInfo()
  loadRecords()
})
</script>

<style scoped lang="scss">
.maintenance-container {
  padding: 20px;

  .page-title {
    font-size: 18px;
    font-weight: 500;
  }

  .content-wrapper {
    margin-top: 20px;

    .el-card {
      margin-bottom: 20px;

      .card-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
      }

      .card-title {
        font-size: 16px;
        font-weight: 500;
      }
    }

    .actions-card {
      text-align: center;
    }

    .expand-content {
      padding: 16px;
    }
  }
}
</style>
