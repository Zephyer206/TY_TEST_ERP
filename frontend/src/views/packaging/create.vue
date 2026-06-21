<template>
  <div class="create-packaging-container">
    <el-page-header @back="goBack" title="返回">
      <template #content>
        <span class="page-title">创建包装记录</span>
      </template>
    </el-page-header>

    <div class="content-wrapper">
      <el-card>
        <el-steps :active="currentStep" align-center finish-status="success">
          <el-step title="扫码/选择生产计划" />
          <el-step title="填写包装信息" />
          <el-step title="生成包装号" />
        </el-steps>

        <!-- 步骤1: 选择生产计划 -->
        <div v-if="currentStep === 0" class="step-content">
          <el-form :model="step1Form" label-width="120px">
            <el-form-item label="扫码生产计划">
              <el-input
                v-model="step1Form.scanCode"
                placeholder="扫描生产计划二维码或输入编号"
                clearable
                @keyup.enter="handleScan"
                style="width: 400px"
              >
                <template #prepend>
                  <el-icon><Barcode /></el-icon>
                </template>
                <template #append>
                  <el-button @click="handleScan">扫描</el-button>
                </template>
              </el-input>
            </el-form-item>
            <el-divider>或</el-divider>
            <el-form-item label="选择生产计划">
              <el-select
                v-model="step1Form.productionPlanId"
                placeholder="选择生产计划"
                filterable
                style="width: 400px"
                @change="handleSelectPlan"
              >
                <el-option
                  v-for="plan in productionPlans"
                  :key="plan.id"
                  :label="`${plan.planNo} - ${plan.partName} (完成: ${plan.completedQuantity})`"
                  :value="plan.id"
                />
              </el-select>
            </el-form-item>
          </el-form>

          <el-card v-if="selectedPlan" class="plan-info-card" shadow="never">
            <template #header>
              <span>生产计划信息</span>
            </template>
            <el-descriptions :column="2" border>
              <el-descriptions-item label="计划编号">{{ selectedPlan.planNo }}</el-descriptions-item>
              <el-descriptions-item label="零件名称">{{ selectedPlan.partName }}</el-descriptions-item>
              <el-descriptions-item label="零件号">{{ selectedPlan.partNo }}</el-descriptions-item>
              <el-descriptions-item label="完成数量">{{ selectedPlan.completedQuantity }} 个</el-descriptions-item>
              <el-descriptions-item label="已包装">{{ selectedPlan.packagedQuantity }} 个</el-descriptions-item>
              <el-descriptions-item label="可包装">
                <el-text type="primary" tag="b">
                  {{ selectedPlan.completedQuantity - selectedPlan.packagedQuantity }} 个
                </el-text>
              </el-descriptions-item>
            </el-descriptions>
          </el-card>

          <div class="step-actions">
            <el-button type="primary" @click="nextStep" :disabled="!selectedPlan">
              下一步
            </el-button>
          </div>
        </div>

        <!-- 步骤2: 填写包装信息 -->
        <div v-if="currentStep === 1" class="step-content">
          <el-form :model="step2Form" :rules="step2Rules" ref="step2FormRef" label-width="120px">
            <el-form-item label="包装数量" prop="quantity">
              <el-input-number
                v-model="step2Form.quantity"
                :min="1"
                :max="selectedPlan ? selectedPlan.completedQuantity - selectedPlan.packagedQuantity : 10000"
                style="width: 200px"
              />
              <span style="margin-left: 10px">个</span>
              <div class="form-tip">
                <el-text type="info" size="small">
                  最多可包装: {{ selectedPlan ? selectedPlan.completedQuantity - selectedPlan.packagedQuantity : 0 }} 个
                </el-text>
              </div>
            </el-form-item>
            <el-form-item label="包装员" prop="packerId">
              <el-select v-model="step2Form.packerId" placeholder="选择包装员" style="width: 200px">
                <el-option
                  v-for="packer in packersList"
                  :key="packer.id"
                  :label="packer.name"
                  :value="packer.id"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="包装类型">
              <el-radio-group v-model="step2Form.packagingType">
                <el-radio label="box">纸箱</el-radio>
                <el-radio label="pallet">托盘</el-radio>
                <el-radio label="bag">袋装</el-radio>
              </el-radio-group>
            </el-form-item>
            <el-form-item label="备注">
              <el-input v-model="step2Form.notes" type="textarea" :rows="3" style="width: 400px" />
            </el-form-item>
          </el-form>

          <div class="step-actions">
            <el-button @click="prevStep">上一步</el-button>
            <el-button type="primary" @click="nextStep">下一步</el-button>
          </div>
        </div>

        <!-- 步骤3: 生成包装号 -->
        <div v-if="currentStep === 2" class="step-content">
          <el-result icon="success" title="包装记录创建成功">
            <template #sub-title>
              <div class="result-info">
                <p>包装号已生成，状态为"待入库"</p>
                <p>请进行全检后入库</p>
              </div>
            </template>
            <template #extra>
              <div class="qr-code-section">
                <h3>包装号二维码</h3>
                <div class="qr-code-placeholder">
                  <el-icon :size="120"><Barcode /></el-icon>
                  <div class="qr-code-text">{{ generatedPackagingNo }}</div>
                </div>
                <div class="qr-actions">
                  <el-button type="primary" @click="printQRCode">
                    <el-icon><Printer /></el-icon>
                    打印二维码
                  </el-button>
                  <el-button @click="downloadQRCode">
                    <el-icon><Download /></el-icon>
                    下载二维码
                  </el-button>
                </div>
              </div>

              <el-descriptions :column="2" border class="packaging-info">
                <el-descriptions-item label="包装号">
                  <el-text tag="b">{{ generatedPackagingNo }}</el-text>
                </el-descriptions-item>
                <el-descriptions-item label="零件">{{ selectedPlan?.partName }}</el-descriptions-item>
                <el-descriptions-item label="数量">{{ step2Form.quantity }} 个</el-descriptions-item>
                <el-descriptions-item label="包装员">{{ getPackerName(step2Form.packerId) }}</el-descriptions-item>
                <el-descriptions-item label="状态">
                  <el-tag type="warning">待入库</el-tag>
                </el-descriptions-item>
                <el-descriptions-item label="创建时间">{{ currentTime }}</el-descriptions-item>
              </el-descriptions>

              <div class="final-actions">
                <el-button type="success" size="large" @click="goToInspect">
                  去全检入库
                </el-button>
                <el-button size="large" @click="createAnother">
                  继续创建
                </el-button>
                <el-button size="large" @click="goToList">
                  返回列表
                </el-button>
              </div>
            </template>
          </el-result>
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Barcode, Printer, Download } from '@element-plus/icons-vue'
import type { FormInstance, FormRules } from 'element-plus'

const router = useRouter()

const currentStep = ref(0)
const selectedPlan = ref<any>(null)
const generatedPackagingNo = ref('')
const currentTime = ref('')

const productionPlans = ref<any[]>([
  {
    id: 1,
    planNo: 'PROD-2026-001',
    partName: '冲压件A',
    partNo: 'P001',
    completedQuantity: 5000,
    packagedQuantity: 4500
  }
])

const packersList = ref<any[]>([
  { id: 1, name: '张三' },
  { id: 2, name: '李四' }
])

const step1Form = reactive({
  scanCode: '',
  productionPlanId: null as any
})

const step2FormRef = ref<FormInstance>()
const step2Form = reactive({
  quantity: 0,
  packerId: null as any,
  packagingType: 'box',
  notes: ''
})

const step2Rules: FormRules = {
  quantity: [{ required: true, message: '请输入包装数量', trigger: 'blur' }],
  packerId: [{ required: true, message: '请选择包装员', trigger: 'change' }]
}

const handleScan = () => {
  if (!step1Form.scanCode.trim()) {
    ElMessage.warning('请输入编号')
    return
  }
  // TODO: 扫码查询
  ElMessage.info('扫码功能')
}

const handleSelectPlan = (planId: number) => {
  selectedPlan.value = productionPlans.value.find(p => p.id === planId)
  if (selectedPlan.value) {
    step2Form.quantity = Math.min(500, selectedPlan.value.completedQuantity - selectedPlan.value.packagedQuantity)
  }
}

const nextStep = async () => {
  if (currentStep.value === 0 && !selectedPlan.value) {
    ElMessage.warning('请选择生产计划')
    return
  }

  if (currentStep.value === 1) {
    if (!step2FormRef.value) return
    const valid = await step2FormRef.value.validate().catch(() => false)
    if (!valid) return

    // 提交创建
    try {
      // TODO: API
      generatedPackagingNo.value = `PKG-${Date.now()}`
      currentTime.value = new Date().toLocaleString('zh-CN')
      ElMessage.success('包装记录创建成功')
    } catch (error) {
      ElMessage.error('创建失败')
      return
    }
  }

  currentStep.value++
}

const prevStep = () => {
  currentStep.value--
}

const getPackerName = (id: number) => {
  return packersList.value.find(p => p.id === id)?.name || ''
}

const printQRCode = () => {
  ElMessage.info('打印二维码')
}

const downloadQRCode = () => {
  ElMessage.info('下载二维码')
}

const goToInspect = () => {
  router.push(`/packaging/inspect/${generatedPackagingNo.value}`)
}

const createAnother = () => {
  currentStep.value = 0
  selectedPlan.value = null
  step1Form.scanCode = ''
  step1Form.productionPlanId = null
  step2Form.quantity = 0
  step2Form.packerId = null
  step2Form.packagingType = 'box'
  step2Form.notes = ''
  generatedPackagingNo.value = ''
}

const goToList = () => {
  router.push('/packaging')
}

const goBack = () => {
  router.back()
}
</script>

<style scoped lang="scss">
.create-packaging-container {
  padding: 20px;

  .page-title {
    font-size: 18px;
    font-weight: 500;
  }

  .content-wrapper {
    margin-top: 20px;

    .el-steps {
      margin-bottom: 40px;
    }

    .step-content {
      padding: 20px;
      min-height: 400px;

      .plan-info-card {
        margin-top: 20px;
      }

      .form-tip {
        margin-top: 4px;
      }

      .step-actions {
        margin-top: 40px;
        text-align: center;
      }

      .result-info {
        margin: 20px 0;
        line-height: 1.8;
        font-size: 16px;
      }

      .qr-code-section {
        margin: 30px 0;
        text-align: center;

        h3 {
          margin-bottom: 20px;
        }

        .qr-code-placeholder {
          width: 200px;
          height: 200px;
          margin: 0 auto 20px;
          border: 2px dashed #dcdfe6;
          border-radius: 4px;
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          background: #f5f7fa;

          .qr-code-text {
            margin-top: 10px;
            font-weight: bold;
            font-size: 14px;
          }
        }

        .qr-actions {
          display: flex;
          gap: 10px;
          justify-content: center;
        }
      }

      .packaging-info {
        margin: 30px 0;
      }

      .final-actions {
        margin-top: 30px;
        display: flex;
        gap: 10px;
        justify-content: center;
      }
    }
  }
}
</style>
