<template>
  <div class="inspect-container">
    <el-page-header @back="goBack" title="返回">
      <template #content>
        <span class="page-title">全检入库</span>
      </template>
    </el-page-header>

    <div class="content-wrapper" v-loading="loading">
      <!-- 包装信息 -->
      <el-card class="packaging-info-card">
        <template #header>
          <span class="card-title">包装信息</span>
        </template>
        <el-descriptions :column="3" border>
          <el-descriptions-item label="包装号" :span="1">
            <div style="display: flex; align-items: center; gap: 8px">
          <el-icon><Tickets /></el-icon>
              <el-text tag="b" size="large">{{ packagingInfo.packagingNo }}</el-text>
            </div>
          </el-descriptions-item>
          <el-descriptions-item label="零件">{{ packagingInfo.partName }}</el-descriptions-item>
          <el-descriptions-item label="零件号">{{ packagingInfo.partNo }}</el-descriptions-item>
          <el-descriptions-item label="包装数量">
            <el-text type="primary" tag="b">{{ packagingInfo.quantity }} 个</el-text>
          </el-descriptions-item>
          <el-descriptions-item label="包装员">{{ packagingInfo.packedBy }}</el-descriptions-item>
          <el-descriptions-item label="包装时间">{{ packagingInfo.packagingTime }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag type="warning">待入库</el-tag>
          </el-descriptions-item>
        </el-descriptions>
      </el-card>

      <!-- 全检表单 -->
      <el-card class="inspect-form-card">
        <template #header>
          <span class="card-title">全检信息</span>
        </template>
        <el-form :model="inspectForm" :rules="inspectRules" ref="inspectFormRef" label-width="140px">
          <el-form-item label="抽检数量" prop="sampleQuantity">
            <el-input-number v-model="inspectForm.sampleQuantity" :min="1" :max="packagingInfo.quantity" style="width: 200px" />
            <span style="margin-left: 10px">/ {{ packagingInfo.quantity }} 个</span>
            <div class="form-tip">
              <el-text type="info" size="small">
                建议抽检比例: 10-20%
              </el-text>
            </div>
          </el-form-item>

          <el-form-item label="合格数量" prop="qualifiedQuantity">
            <el-input-number v-model="inspectForm.qualifiedQuantity" :min="0" :max="inspectForm.sampleQuantity" style="width: 200px" />
            <span style="margin-left: 10px">/ {{ inspectForm.sampleQuantity }} 个</span>
          </el-form-item>

          <el-form-item label="不合格数量">
            <el-text type="danger" tag="b">{{ inspectForm.sampleQuantity - inspectForm.qualifiedQuantity }} 个</el-text>
          </el-form-item>

          <el-form-item label="检验结果" prop="result">
            <el-radio-group v-model="inspectForm.result">
              <el-radio label="pass">
                <el-tag type="success" size="large">合格 - 入库</el-tag>
              </el-radio>
              <el-radio label="reject">
                <el-tag type="danger" size="large">不合格 - 拒绝入库</el-tag>
              </el-radio>
            </el-radio-group>
            <div class="form-tip">
              <el-text type="info" size="small">
                合格率 {{ getPassRate() }}% {{ getPassRate() >= 95 ? '(建议入库)' : '(建议拒绝)' }}
              </el-text>
            </div>
          </el-form-item>

          <el-form-item label="检验项目" prop="inspectionItems">
            <el-checkbox-group v-model="inspectForm.inspectionItems">
              <el-checkbox label="appearance">外观检查</el-checkbox>
              <el-checkbox label="dimension">尺寸检查</el-checkbox>
              <el-checkbox label="function">功能检查</el-checkbox>
              <el-checkbox label="quantity">数量核对</el-checkbox>
            </el-checkbox-group>
          </el-form-item>

          <el-form-item label="不合格项" v-if="inspectForm.result === 'reject'">
            <el-checkbox-group v-model="inspectForm.defects">
              <el-checkbox label="scratch">划伤</el-checkbox>
              <el-checkbox label="deformation">变形</el-checkbox>
              <el-checkbox label="burr">毛刺</el-checkbox>
              <el-checkbox label="dimension">尺寸不符</el-checkbox>
              <el-checkbox label="other">其他</el-checkbox>
            </el-checkbox-group>
          </el-form-item>

          <el-form-item label="检验意见" prop="comment">
            <el-input
              v-model="inspectForm.comment"
              type="textarea"
              :rows="4"
              placeholder="请详细描述检验情况"
              maxlength="500"
              show-word-limit
            />
          </el-form-item>

          <el-form-item label="检验照片">
            <el-upload
              v-model:file-list="inspectForm.photoList"
              action="#"
              list-type="picture-card"
              :auto-upload="false"
              accept="image/*"
            >
              <el-icon><Plus /></el-icon>
            </el-upload>
            <div class="form-tip">
              <el-text type="info" size="small">
                如有不合格品，请上传照片记录
              </el-text>
            </div>
          </el-form-item>

          <el-form-item label="存放位置" prop="storageLocation" v-if="inspectForm.result === 'pass'">
            <el-select v-model="inspectForm.storageLocation" placeholder="选择存放位置" style="width: 200px">
              <el-option label="成品区A01" value="成品区A01" />
              <el-option label="成品区A02" value="成品区A02" />
              <el-option label="成品区B01" value="成品区B01" />
              <el-option label="成品区B02" value="成品区B02" />
            </el-select>
          </el-form-item>

          <el-form-item label="全检员" prop="inspectorId">
            <el-select v-model="inspectForm.inspectorId" placeholder="选择全检员" style="width: 200px">
              <el-option
                v-for="inspector in inspectorsList"
                :key="inspector.id"
                :label="inspector.name"
                :value="inspector.id"
              />
            </el-select>
          </el-form-item>

          <el-form-item>
            <el-button type="primary" size="large" @click="submitInspect" :loading="submitting">
              <el-icon><Check /></el-icon>
              确认{{ inspectForm.result === 'pass' ? '入库' : '拒绝入库' }}
            </el-button>
            <el-button size="large" @click="goBack">取消</el-button>
          </el-form-item>
        </el-form>
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Tickets, Plus, Check } from '@element-plus/icons-vue'
import type { FormInstance, FormRules, UploadFile } from 'element-plus'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const submitting = ref(false)

const packagingInfo = ref<any>({})
const inspectorsList = ref<any[]>([])

const inspectFormRef = ref<FormInstance>()
const inspectForm = reactive({
  sampleQuantity: 0,
  qualifiedQuantity: 0,
  result: 'pass',
  inspectionItems: [] as string[],
  defects: [] as string[],
  comment: '',
  photoList: [] as UploadFile[],
  storageLocation: '',
  inspectorId: null as any
})

const inspectRules: FormRules = {
  sampleQuantity: [{ required: true, message: '请输入抽检数量', trigger: 'blur' }],
  qualifiedQuantity: [{ required: true, message: '请输入合格数量', trigger: 'blur' }],
  result: [{ required: true, message: '请选择检验结果', trigger: 'change' }],
  inspectionItems: [{ required: true, message: '请选择检验项目', trigger: 'change', type: 'array', min: 1 }],
  comment: [
    { required: true, message: '请输入检验意见', trigger: 'blur' },
    { min: 10, message: '检验意见至少10个字符', trigger: 'blur' }
  ],
  storageLocation: [{ required: true, message: '请选择存放位置', trigger: 'change' }],
  inspectorId: [{ required: true, message: '请选择全检员', trigger: 'change' }]
}

const loadPackagingInfo = async () => {
  loading.value = true
  try {
    const id = route.params.id
    // TODO: API
    packagingInfo.value = {
      id,
      packagingNo: 'PKG-2026-001',
      partName: '冲压件A',
      partNo: 'P001',
      quantity: 500,
      packedBy: '张三',
      packagingTime: '2026-06-20 14:00'
    }

    // 设置默认抽检数量（10%）
    inspectForm.sampleQuantity = Math.ceil(packagingInfo.value.quantity * 0.1)
    inspectForm.qualifiedQuantity = inspectForm.sampleQuantity
  } catch (error) {
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
}

const loadInspectors = async () => {
  try {
    inspectorsList.value = [
      { id: 1, name: '李四' },
      { id: 2, name: '王五' }
    ]
  } catch (error) {
    ElMessage.error('加载全检员失败')
  }
}

const getPassRate = () => {
  if (inspectForm.sampleQuantity === 0) return 0
  return Math.round((inspectForm.qualifiedQuantity / inspectForm.sampleQuantity) * 100)
}

// 监听合格数量变化，自动判断结果
watch(
  () => inspectForm.qualifiedQuantity,
  () => {
    const passRate = getPassRate()
    if (passRate >= 95) {
      inspectForm.result = 'pass'
    } else if (passRate < 80) {
      inspectForm.result = 'reject'
    }
  }
)

const submitInspect = async () => {
  if (!inspectFormRef.value) return

  await inspectFormRef.value.validate(async (valid) => {
    if (!valid) return

    try {
      const action = inspectForm.result === 'pass' ? '入库' : '拒绝入库'
      await ElMessageBox.confirm(
        `确认${action}吗？${inspectForm.result === 'pass' ? '入库后将更新库存。' : ''}`,
        `确认${action}`,
        {
          confirmButtonText: '确认',
          cancelButtonText: '取消',
          type: 'warning'
        }
      )

      submitting.value = true

      // TODO: 上传照片并提交
      // await api.packaging.inspect(packagingInfo.value.id, inspectForm)

      ElMessage.success(
        inspectForm.result === 'pass'
          ? '全检通过，已入库'
          : '全检不通过，已拒绝入库'
      )

      // 跳转到列表或库存页面
      if (inspectForm.result === 'pass') {
        router.push('/packaging/inventory')
      } else {
        router.push('/packaging')
      }
    } catch (error: any) {
      if (error !== 'cancel') {
        ElMessage.error('操作失败')
      }
    } finally {
      submitting.value = false
    }
  })
}

const goBack = () => {
  router.back()
}

onMounted(() => {
  loadPackagingInfo()
  loadInspectors()
})
</script>

<style scoped lang="scss">
.inspect-container {
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

    .form-tip {
      margin-top: 4px;
    }
  }
}
</style>
