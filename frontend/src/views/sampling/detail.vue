<template>
  <div class="sampling-detail-container">
    <el-page-header @back="goBack" title="返回">
      <template #content>
        <span class="page-title">打样任务详情</span>
      </template>
    </el-page-header>

    <div class="content-wrapper" v-loading="loading">
      <!-- 基本信息 -->
      <el-card class="info-card">
        <template #header>
          <div class="card-header">
            <span class="card-title">基本信息</span>
            <el-tag :type="getStatusType(taskDetail.status)" size="large">
              {{ getStatusText(taskDetail.status) }}
            </el-tag>
          </div>
        </template>
        <el-descriptions :column="2" border>
          <el-descriptions-item label="任务编号">{{ taskDetail.taskNo }}</el-descriptions-item>
          <el-descriptions-item label="零件名称">{{ taskDetail.partName }}</el-descriptions-item>
          <el-descriptions-item label="客户名称">{{ taskDetail.customerName }}</el-descriptions-item>
          <el-descriptions-item label="打样数量">{{ taskDetail.quantity }}</el-descriptions-item>
          <el-descriptions-item label="创建人">{{ taskDetail.createdBy }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ taskDetail.createdAt }}</el-descriptions-item>
          <el-descriptions-item label="截止日期">{{ taskDetail.deadline }}</el-descriptions-item>
          <el-descriptions-item label="实际完成时间">
            {{ taskDetail.completedAt || '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="打样要求" :span="2">
            <div class="requirements-text">{{ taskDetail.requirements }}</div>
          </el-descriptions-item>
          <el-descriptions-item label="参考资料" :span="2" v-if="taskDetail.attachments?.length">
            <div class="attachments">
              <el-link
                v-for="file in taskDetail.attachments"
                :key="file.id"
                type="primary"
                :href="file.url"
                target="_blank"
                class="attachment-link"
              >
                <el-icon><Document /></el-icon>
                {{ file.name }}
              </el-link>
            </div>
          </el-descriptions-item>
        </el-descriptions>
      </el-card>

      <!-- 审批记录 -->
      <el-card class="approval-card" v-if="taskDetail.approvalHistory?.length">
        <template #header>
          <span class="card-title">审批记录</span>
        </template>
        <el-timeline>
          <el-timeline-item
            v-for="(item, index) in taskDetail.approvalHistory"
            :key="index"
            :timestamp="item.createdAt"
            placement="top"
            :type="item.approved ? 'success' : 'danger'"
          >
            <el-card>
              <h4>{{ item.approverName }} {{ item.approved ? '批准' : '拒绝' }}</h4>
              <p v-if="item.comment">{{ item.comment }}</p>
            </el-card>
          </el-timeline-item>
        </el-timeline>
      </el-card>

      <!-- 生产进度 -->
      <el-card class="progress-card" v-if="taskDetail.status === 'sampling' || taskDetail.status === 'review_pending'">
        <template #header>
          <span class="card-title">生产进度</span>
        </template>
        <el-descriptions :column="2" border v-if="taskDetail.production">
          <el-descriptions-item label="分配机台">
            {{ taskDetail.production.machineName || '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="操作员">
            {{ taskDetail.production.operatorName || '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="开始时间">
            {{ taskDetail.production.startTime || '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="完成时间">
            {{ taskDetail.production.endTime || '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="实际产量" :span="2">
            {{ taskDetail.production.actualQuantity || 0 }} / {{ taskDetail.quantity }}
          </el-descriptions-item>
        </el-descriptions>
        <el-empty v-else description="暂无生产记录" />
      </el-card>

      <!-- 评审结果 -->
      <el-card class="review-card" v-if="taskDetail.review">
        <template #header>
          <span class="card-title">评审结果</span>
        </template>
        <el-descriptions :column="2" border>
          <el-descriptions-item label="评审人">{{ taskDetail.review.reviewerName }}</el-descriptions-item>
          <el-descriptions-item label="评审时间">{{ taskDetail.review.reviewTime }}</el-descriptions-item>
          <el-descriptions-item label="评审结果" :span="2">
            <el-tag :type="taskDetail.review.passed ? 'success' : 'danger'">
              {{ taskDetail.review.passed ? '通过' : '不通过' }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="评审意见" :span="2">
            {{ taskDetail.review.comment }}
          </el-descriptions-item>
          <el-descriptions-item label="评审照片" :span="2" v-if="taskDetail.review.photos?.length">
            <div class="review-photos">
              <el-image
                v-for="photo in taskDetail.review.photos"
                :key="photo"
                :src="photo"
                :preview-src-list="taskDetail.review.photos"
                fit="cover"
                class="review-photo"
              />
            </div>
          </el-descriptions-item>
        </el-descriptions>
      </el-card>

      <!-- 操作按钮 -->
      <el-card class="actions-card">
        <el-space wrap>
          <el-button
            v-if="taskDetail.status === 'pending' && canApprove"
            type="success"
            @click="handleApprove"
          >
            批准
          </el-button>
          <el-button
            v-if="taskDetail.status === 'pending' && canApprove"
            type="danger"
            @click="handleReject"
          >
            拒绝
          </el-button>
          <el-button
            v-if="taskDetail.status === 'approved' && canAssign"
            type="primary"
            @click="showAssignDialog = true"
          >
            分配机台
          </el-button>
          <el-button
            v-if="taskDetail.status === 'sampling'"
            type="warning"
            @click="handleComplete"
          >
            完成打样
          </el-button>
          <el-button
            v-if="taskDetail.status === 'review_pending' && canReview"
            type="primary"
            @click="goToReview"
          >
            去评审
          </el-button>
          <el-button
            v-if="['pending', 'sampling'].includes(taskDetail.status)"
            type="danger"
            @click="handleCancel"
          >
            取消任务
          </el-button>
        </el-space>
      </el-card>
    </div>

    <!-- 分配机台对话框 -->
    <el-dialog v-model="showAssignDialog" title="分配机台" width="500px">
      <el-form :model="assignForm" label-width="100px">
        <el-form-item label="选择机台">
          <el-select v-model="assignForm.machineId" placeholder="请选择机台" style="width: 100%">
            <el-option
              v-for="machine in machinesList"
              :key="machine.id"
              :label="`${machine.name} (${machine.no})`"
              :value="machine.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="预计开始">
          <el-date-picker
            v-model="assignForm.startTime"
            type="datetime"
            placeholder="选择开始时间"
            style="width: 100%"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAssignDialog = false">取消</el-button>
        <el-button type="primary" @click="submitAssign">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Document } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const loading = ref(false)
const showAssignDialog = ref(false)

// 任务详情
const taskDetail = ref<any>({})

// 机台列表
const machinesList = ref<any[]>([])

// 分配表单
const assignForm = reactive({
  machineId: null,
  startTime: ''
})

// 权限判断
const canApprove = computed(() => {
  // 老板才能审批
  return userStore.user?.roleLevel >= 10
})

const canAssign = computed(() => {
  // 组长才能分配机台
  return userStore.user?.roleLevel >= 5
})

const canReview = computed(() => {
  // 业务、品质、开发可以评审
  return ['business', 'quality', 'tech'].includes(userStore.user?.department)
})

// 加载详情
const loadDetail = async () => {
  loading.value = true
  try {
    const id = route.params.id
    // TODO: 调用 API
    // const response = await api.sampling.detail(id)
    // taskDetail.value = response.data

    // 模拟数据
    taskDetail.value = {
      id,
      taskNo: 'SAMPLE-2026-001',
      partName: '冲压件A',
      customerName: '客户A',
      quantity: 100,
      status: 'pending',
      createdBy: '张三',
      createdAt: '2026-06-20 10:00:00',
      deadline: '2026-06-25',
      requirements: '按图纸要求打样，注意表面质量',
      attachments: [],
      approvalHistory: [],
      production: null,
      review: null
    }
  } catch (error) {
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
}

// 加载机台列表
const loadMachines = async () => {
  try {
    // TODO: 调用 API
    // const response = await api.machines.list({ status: 'available' })
    // machinesList.value = response.data

    // 模拟数据
    machinesList.value = [
      { id: 1, name: '机台1', no: 'M001' },
      { id: 2, name: '机台2', no: 'M002' }
    ]
  } catch (error) {
    ElMessage.error('加载机台列表失败')
  }
}

// 批准
const handleApprove = async () => {
  try {
    await ElMessageBox.confirm('确认批准此打样任务吗？', '提示', {
      confirmButtonText: '确认',
      cancelButtonText: '取消',
      type: 'warning'
    })
    // TODO: 调用 API
    // await api.sampling.approve(taskDetail.value.id)
    ElMessage.success('已批准')
    loadDetail()
  } catch (error) {
    // 用户取消
  }
}

// 拒绝
const handleReject = async () => {
  try {
    const { value } = await ElMessageBox.prompt('请输入拒绝理由', '拒绝打样任务', {
      confirmButtonText: '确认',
      cancelButtonText: '取消',
      inputPattern: /.+/,
      inputErrorMessage: '请输入拒绝理由'
    })
    // TODO: 调用 API
    // await api.sampling.reject(taskDetail.value.id, { reason: value })
    ElMessage.success('已拒绝')
    loadDetail()
  } catch (error) {
    // 用户取消
  }
}

// 提交分配
const submitAssign = async () => {
  if (!assignForm.machineId) {
    ElMessage.warning('请选择机台')
    return
  }
  try {
    // TODO: 调用 API
    // await api.sampling.assign(taskDetail.value.id, assignForm)
    ElMessage.success('分配成功')
    showAssignDialog.value = false
    loadDetail()
  } catch (error) {
    ElMessage.error('分配失败')
  }
}

// 完成打样
const handleComplete = async () => {
  try {
    await ElMessageBox.confirm('确认打样已完成吗？', '提示', {
      confirmButtonText: '确认',
      cancelButtonText: '取消',
      type: 'warning'
    })
    // TODO: 调用 API
    // await api.sampling.complete(taskDetail.value.id)
    ElMessage.success('已标记为待评审')
    loadDetail()
  } catch (error) {
    // 用户取消
  }
}

// 去评审
const goToReview = () => {
  router.push(`/sampling/review/${taskDetail.value.id}`)
}

// 取消任务
const handleCancel = async () => {
  try {
    await ElMessageBox.confirm('确认取消此打样任务吗？', '提示', {
      confirmButtonText: '确认',
      cancelButtonText: '取消',
      type: 'warning'
    })
    // TODO: 调用 API
    // await api.sampling.cancel(taskDetail.value.id)
    ElMessage.success('已取消')
    router.back()
  } catch (error) {
    // 用户取消
  }
}

// 返回
const goBack = () => {
  router.back()
}

// 状态类型和文本
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

onMounted(() => {
  loadDetail()
  loadMachines()
})
</script>

<style scoped lang="scss">
.sampling-detail-container {
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

    .requirements-text {
      white-space: pre-wrap;
      line-height: 1.6;
    }

    .attachments {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;

      .attachment-link {
        display: flex;
        align-items: center;
        gap: 5px;
      }
    }

    .review-photos {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;

      .review-photo {
        width: 120px;
        height: 120px;
        border-radius: 4px;
      }
    }

    .actions-card {
      .el-space {
        width: 100%;
      }
    }
  }
}
</style>
