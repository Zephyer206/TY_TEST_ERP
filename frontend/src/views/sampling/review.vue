<template>
  <div class="sampling-review-container">
    <el-page-header @back="goBack" title="返回">
      <template #content>
        <span class="page-title">打样评审</span>
      </template>
    </el-page-header>

    <div class="content-wrapper" v-loading="loading">
      <!-- 打样任务信息 -->
      <el-card class="task-info-card">
        <template #header>
          <span class="card-title">打样任务信息</span>
        </template>
        <el-descriptions :column="2" border>
          <el-descriptions-item label="任务编号">{{ taskInfo.taskNo }}</el-descriptions-item>
          <el-descriptions-item label="零件名称">{{ taskInfo.partName }}</el-descriptions-item>
          <el-descriptions-item label="客户名称">{{ taskInfo.customerName }}</el-descriptions-item>
          <el-descriptions-item label="打样数量">{{ taskInfo.quantity }}</el-descriptions-item>
          <el-descriptions-item label="打样要求" :span="2">
            <div class="requirements-text">{{ taskInfo.requirements }}</div>
          </el-descriptions-item>
          <el-descriptions-item label="完成时间" :span="2">
            {{ taskInfo.completedAt }}
          </el-descriptions-item>
        </el-descriptions>
      </el-card>

      <!-- 评审表单 -->
      <el-card class="review-form-card">
        <template #header>
          <span class="card-title">评审结果</span>
        </template>
        <el-form
          :model="reviewForm"
          :rules="reviewRules"
          ref="reviewFormRef"
          label-width="120px"
          size="large"
        >
          <el-form-item label="评审结果" prop="passed">
            <el-radio-group v-model="reviewForm.passed">
              <el-radio :label="true" size="large">
                <el-tag type="success" size="large">通过</el-tag>
              </el-radio>
              <el-radio :label="false" size="large">
                <el-tag type="danger" size="large">不通过</el-tag>
              </el-radio>
            </el-radio-group>
            <div class="form-tip">
              <el-text type="info" size="small">
                通过：样件质量合格，可以转为量产<br />
                不通过：样件存在问题，需要重新打样
              </el-text>
            </div>
          </el-form-item>

          <el-form-item label="评审意见" prop="comment">
            <el-input
              v-model="reviewForm.comment"
              type="textarea"
              :rows="6"
              placeholder="请详细描述评审意见，如：尺寸、外观、功能等方面的评价"
              maxlength="500"
              show-word-limit
            />
          </el-form-item>

          <el-form-item label="样件照片" prop="photos">
            <el-upload
              v-model:file-list="reviewForm.photoList"
              action="#"
              list-type="picture-card"
              :auto-upload="false"
              :on-preview="handlePreview"
              :on-remove="handleRemove"
              :on-change="handlePhotoChange"
              accept="image/*"
            >
              <el-icon><Plus /></el-icon>
            </el-upload>
            <div class="form-tip">
              <el-text type="info" size="small">
                请上传样件照片，支持多张上传，用于记录样件质量情况
              </el-text>
            </div>
          </el-form-item>

          <el-form-item label="质量问题" v-if="reviewForm.passed === false">
            <el-checkbox-group v-model="reviewForm.issues">
              <el-checkbox label="dimension">尺寸不符</el-checkbox>
              <el-checkbox label="surface">表面质量问题</el-checkbox>
              <el-checkbox label="function">功能不符</el-checkbox>
              <el-checkbox label="material">材料问题</el-checkbox>
              <el-checkbox label="other">其他问题</el-checkbox>
            </el-checkbox-group>
          </el-form-item>

          <el-form-item label="改进建议" v-if="reviewForm.passed === false">
            <el-input
              v-model="reviewForm.improvement"
              type="textarea"
              :rows="4"
              placeholder="请提供改进建议，帮助下次打样改进"
            />
          </el-form-item>

          <el-form-item>
            <el-space>
              <el-button type="primary" size="large" @click="submitReview" :loading="submitting">
                提交评审
              </el-button>
              <el-button size="large" @click="goBack">取消</el-button>
            </el-space>
          </el-form-item>
        </el-form>
      </el-card>

      <!-- 历史评审记录（如果有） -->
      <el-card class="history-card" v-if="historyReviews.length">
        <template #header>
          <span class="card-title">历史评审记录</span>
        </template>
        <el-timeline>
          <el-timeline-item
            v-for="(item, index) in historyReviews"
            :key="index"
            :timestamp="item.reviewTime"
            placement="top"
            :type="item.passed ? 'success' : 'danger'"
          >
            <el-card>
              <div class="history-header">
                <h4>{{ item.reviewerName }} - {{ item.passed ? '通过' : '不通过' }}</h4>
                <el-tag :type="item.passed ? 'success' : 'danger'">
                  第{{ index + 1 }}次评审
                </el-tag>
              </div>
              <p class="history-comment">{{ item.comment }}</p>
              <div class="history-photos" v-if="item.photos?.length">
                <el-image
                  v-for="photo in item.photos"
                  :key="photo"
                  :src="photo"
                  :preview-src-list="item.photos"
                  fit="cover"
                  class="history-photo"
                />
              </div>
            </el-card>
          </el-timeline-item>
        </el-timeline>
      </el-card>
    </div>

    <!-- 图片预览对话框 -->
    <el-dialog v-model="showPreviewDialog" title="预览">
      <img :src="previewImage" style="width: 100%" />
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import type { FormInstance, FormRules, UploadFile } from 'element-plus'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const submitting = ref(false)
const showPreviewDialog = ref(false)
const previewImage = ref('')

// 任务信息
const taskInfo = ref<any>({})

// 历史评审记录
const historyReviews = ref<any[]>([])

// 评审表单
const reviewFormRef = ref<FormInstance>()
const reviewForm = reactive({
  passed: undefined as boolean | undefined,
  comment: '',
  photoList: [] as UploadFile[],
  photos: [] as string[],
  issues: [] as string[],
  improvement: ''
})

const reviewRules: FormRules = {
  passed: [{ required: true, message: '请选择评审结果', trigger: 'change' }],
  comment: [
    { required: true, message: '请输入评审意见', trigger: 'blur' },
    { min: 10, message: '评审意见至少10个字符', trigger: 'blur' }
  ]
}

// 加载任务信息
const loadTaskInfo = async () => {
  loading.value = true
  try {
    const id = route.params.id
    // TODO: 调用 API
    // const response = await api.sampling.detail(id)
    // taskInfo.value = response.data

    // 模拟数据
    taskInfo.value = {
      id,
      taskNo: 'SAMPLE-2026-001',
      partName: '冲压件A',
      customerName: '客户A',
      quantity: 100,
      requirements: '按图纸要求打样，注意表面质量',
      completedAt: '2026-06-22 15:30:00'
    }

    // 加载历史评审记录（如果有多次打样）
    // const historyResponse = await api.sampling.reviewHistory(id)
    // historyReviews.value = historyResponse.data
    historyReviews.value = []
  } catch (error) {
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
}

// 照片变化
const handlePhotoChange = (_file: UploadFile) => {
  // 这里可以实现即时上传到服务器
  // 或者在提交时统一上传
}

// 预览照片
const handlePreview = (file: UploadFile) => {
  previewImage.value = file.url || ''
  showPreviewDialog.value = true
}

// 移除照片
const handleRemove = (file: UploadFile) => {
  const index = reviewForm.photoList.findIndex(f => f.uid === file.uid)
  if (index > -1) {
    reviewForm.photoList.splice(index, 1)
  }
}

// 提交评审
const submitReview = async () => {
  if (!reviewFormRef.value) return

  await reviewFormRef.value.validate(async (valid) => {
    if (!valid) return

    try {
      await ElMessageBox.confirm(
        `确认提交评审结果为"${reviewForm.passed ? '通过' : '不通过'}"吗？`,
        '确认提交',
        {
          confirmButtonText: '确认提交',
          cancelButtonText: '取消',
          type: 'warning'
        }
      )

      submitting.value = true

      // TODO: 先上传照片
      // const photoUrls = []
      // for (const file of reviewForm.photoList) {
      //   const url = await uploadFile(file.raw)
      //   photoUrls.push(url)
      // }

      // TODO: 提交评审
      // await api.sampling.submitReview(taskInfo.value.id, {
      //   passed: reviewForm.passed,
      //   comment: reviewForm.comment,
      //   photos: photoUrls,
      //   issues: reviewForm.issues,
      //   improvement: reviewForm.improvement
      // })

      ElMessage.success('评审提交成功')

      // 如果评审通过，提示零件状态已更新
      if (reviewForm.passed) {
        ElMessage.info('零件状态已更新为"量产"')
      }

      // 返回详情页
      router.push(`/sampling/detail/${taskInfo.value.id}`)
    } catch (error: any) {
      if (error !== 'cancel') {
        ElMessage.error('提交失败')
      }
    } finally {
      submitting.value = false
    }
  })
}

// 返回
const goBack = () => {
  router.back()
}

onMounted(() => {
  loadTaskInfo()
})
</script>

<style scoped lang="scss">
.sampling-review-container {
  padding: 20px;

  .page-title {
    font-size: 18px;
    font-weight: 500;
  }

  .content-wrapper {
    margin-top: 20px;

    .el-card {
      margin-bottom: 20px;

      .card-title {
        font-size: 16px;
        font-weight: 500;
      }
    }

    .requirements-text {
      white-space: pre-wrap;
      line-height: 1.6;
    }

    .form-tip {
      margin-top: 8px;
      line-height: 1.6;
    }

    .history-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 10px;

      h4 {
        margin: 0;
      }
    }

    .history-comment {
      margin: 10px 0;
      line-height: 1.6;
    }

    .history-photos {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 10px;

      .history-photo {
        width: 100px;
        height: 100px;
        border-radius: 4px;
      }
    }
  }
}
</style>
