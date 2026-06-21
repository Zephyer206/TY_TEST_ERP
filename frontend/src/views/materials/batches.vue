<template>
  <div class="batches-container">
    <el-page-header @back="goBack" title="返回">
      <template #content>
        <span class="page-title">批次管理</span>
      </template>
    </el-page-header>

    <div class="content-wrapper" v-loading="loading">
      <!-- 原材料信息 -->
      <el-card class="material-info-card">
        <el-descriptions :column="4" border>
          <el-descriptions-item label="物料编码">
            <el-text tag="b">{{ materialInfo.materialCode }}</el-text>
          </el-descriptions-item>
          <el-descriptions-item label="材质">{{ materialInfo.materialName }}</el-descriptions-item>
          <el-descriptions-item label="规格">
            {{ materialInfo.thickness }}×{{ materialInfo.width }}mm
          </el-descriptions-item>
          <el-descriptions-item label="当前库存">
            <el-text :type="getStockColor(materialInfo.stockQuantity, materialInfo.safetyStock)">
              {{ materialInfo.stockQuantity }} {{ materialInfo.unit }}
            </el-text>
          </el-descriptions-item>
        </el-descriptions>
      </el-card>

      <!-- 新增批次按钮 -->
      <el-card class="actions-card">
        <el-button type="primary" size="large" @click="showCreateDialog = true">
          <el-icon><Plus /></el-icon>
          来料入库
        </el-button>
        <el-button type="success" size="large" @click="goToSlitting">
          <el-icon><ScissorIcon /></el-icon>
          分条记录
        </el-button>
        <el-button type="info" size="large" @click="goToTrace">
          <el-icon><Search /></el-icon>
          批次追溯
        </el-button>
      </el-card>

      <!-- 筛选条件 -->
      <el-card class="filter-card">
        <el-form :inline="true" :model="filters">
          <el-form-item label="批次状态">
            <el-select v-model="filters.status" placeholder="全部状态" clearable style="width: 150px">
              <el-option label="待检" value="pending_iqc" />
              <el-option label="合格" value="qualified" />
              <el-option label="不合格" value="rejected" />
              <el-option label="使用中" value="in_use" />
              <el-option label="已用完" value="used_up" />
            </el-select>
          </el-form-item>
          <el-form-item label="批次号">
            <el-input v-model="filters.batchNo" placeholder="批次号" clearable style="width: 200px" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="loadBatches">查询</el-button>
            <el-button @click="resetFilters">重置</el-button>
          </el-form-item>
        </el-form>
      </el-card>

      <!-- 批次列表 -->
      <el-card>
        <el-table :data="batchList" border stripe>
          <el-table-column prop="batchNo" label="批次号" width="180" fixed="left" />
          <el-table-column prop="supplierName" label="供应商" width="150" />
          <el-table-column prop="quantity" label="来料数量" width="120" align="right">
            <template #default="{ row }">
              {{ row.quantity }} {{ materialInfo.unit }}
            </template>
          </el-table-column>
          <el-table-column prop="remainingQuantity" label="剩余数量" width="120" align="right">
            <template #default="{ row }">
              {{ row.remainingQuantity }} {{ materialInfo.unit }}
            </template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="100" align="center">
            <template #default="{ row }">
              <el-tag :type="getStatusType(row.status)">
                {{ getStatusText(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="iqcResult" label="IQC检验" width="100" align="center">
            <template #default="{ row }">
              <el-tag v-if="row.iqcResult" :type="row.iqcResult === 'qualified' ? 'success' : 'danger'">
                {{ row.iqcResult === 'qualified' ? '合格' : '不合格' }}
              </el-tag>
              <el-text v-else type="info">待检</el-text>
            </template>
          </el-table-column>
          <el-table-column prop="arrivalDate" label="到货日期" width="110" />
          <el-table-column prop="expiryDate" label="有效期至" width="110" />
          <el-table-column prop="storageLocation" label="存放位置" width="120" />
          <el-table-column label="操作" width="220" fixed="right">
            <template #default="{ row }">
              <el-button
                v-if="row.status === 'pending_iqc'"
                type="primary"
                link
                @click="handleIQC(row)"
              >
                IQC检验
              </el-button>
              <el-button type="info" link @click="viewDetail(row)">详情</el-button>
              <el-button type="success" link @click="goToTrace">追溯</el-button>
            </template>
          </el-table-column>
        </el-table>

        <!-- 分页 -->
        <div class="pagination-container">
          <el-pagination
            v-model:current-page="pagination.page"
            v-model:page-size="pagination.pageSize"
            :page-sizes="[10, 20, 50]"
            :total="pagination.total"
            layout="total, sizes, prev, pager, next, jumper"
            @size-change="loadBatches"
            @current-change="loadBatches"
          />
        </div>
      </el-card>
    </div>

    <!-- 来料入库对话框 -->
    <el-dialog
      v-model="showCreateDialog"
      title="来料入库"
      width="600px"
      :close-on-click-modal="false"
    >
      <el-form :model="batchForm" :rules="batchRules" ref="batchFormRef" label-width="120px">
        <el-form-item label="批次号" prop="batchNo">
          <el-input v-model="batchForm.batchNo" placeholder="如：BATCH-2026-06-001" />
          <div class="form-tip">
            <el-text type="info" size="small">供应商提供的批次号</el-text>
          </div>
        </el-form-item>
        <el-form-item label="供应商" prop="supplierId">
          <el-select v-model="batchForm.supplierId" placeholder="选择供应商" style="width: 100%">
            <el-option
              v-for="supplier in suppliersList"
              :key="supplier.id"
              :label="supplier.name"
              :value="supplier.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="来料数量" prop="quantity">
          <el-input-number v-model="batchForm.quantity" :min="0" :precision="2" style="width: 200px" />
          <span style="margin-left: 10px">{{ materialInfo.unit }}</span>
        </el-form-item>
        <el-form-item label="到货日期" prop="arrivalDate">
          <el-date-picker
            v-model="batchForm.arrivalDate"
            type="date"
            placeholder="选择日期"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="有效期至">
          <el-date-picker
            v-model="batchForm.expiryDate"
            type="date"
            placeholder="选择日期"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="存放位置" prop="storageLocation">
          <el-input v-model="batchForm.storageLocation" placeholder="如：仓库A区01" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="batchForm.notes" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="submitBatch" :loading="submitting">确认入库</el-button>
      </template>
    </el-dialog>

    <!-- IQC检验对话框 -->
    <el-dialog v-model="showIQCDialog" title="IQC来料检验" width="600px">
      <el-form :model="iqcForm" :rules="iqcRules" ref="iqcFormRef" label-width="120px">
        <el-form-item label="批次号">
          <el-text tag="b">{{ currentBatch?.batchNo }}</el-text>
        </el-form-item>
        <el-form-item label="检验结果" prop="result">
          <el-radio-group v-model="iqcForm.result">
            <el-radio label="qualified">
              <el-tag type="success">合格</el-tag>
            </el-radio>
            <el-radio label="rejected">
              <el-tag type="danger">不合格</el-tag>
            </el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="检验意见" prop="comment">
          <el-input v-model="iqcForm.comment" type="textarea" :rows="4" placeholder="请输入检验意见" />
        </el-form-item>
        <el-form-item label="检验照片">
          <el-upload
            v-model:file-list="iqcForm.photoList"
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
        <el-button @click="showIQCDialog = false">取消</el-button>
        <el-button type="primary" @click="submitIQC" :loading="submitting">提交检验</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Plus, Search } from '@element-plus/icons-vue'
import type { FormInstance, FormRules, UploadFile } from 'element-plus'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const submitting = ref(false)
const showCreateDialog = ref(false)
const showIQCDialog = ref(false)
const currentBatch = ref<any>(null)

const materialInfo = ref<any>({})
const batchList = ref<any[]>([])
const suppliersList = ref<any[]>([])

const filters = reactive({
  status: '',
  batchNo: ''
})

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

const batchFormRef = ref<FormInstance>()
const batchForm = reactive({
  batchNo: '',
  supplierId: null as any,
  quantity: 0,
  arrivalDate: '',
  expiryDate: '',
  storageLocation: '',
  notes: ''
})

const batchRules: FormRules = {
  batchNo: [{ required: true, message: '请输入批次号', trigger: 'blur' }],
  supplierId: [{ required: true, message: '请选择供应商', trigger: 'change' }],
  quantity: [{ required: true, message: '请输入数量', trigger: 'blur' }],
  arrivalDate: [{ required: true, message: '请选择到货日期', trigger: 'change' }],
  storageLocation: [{ required: true, message: '请输入存放位置', trigger: 'blur' }]
}

const iqcFormRef = ref<FormInstance>()
const iqcForm = reactive({
  result: '',
  comment: '',
  photoList: [] as UploadFile[]
})

const iqcRules: FormRules = {
  result: [{ required: true, message: '请选择检验结果', trigger: 'change' }],
  comment: [{ required: true, message: '请输入检验意见', trigger: 'blur' }]
}

const loadMaterialInfo = async () => {
  try {
    const id = route.params.id
    // TODO: API
    materialInfo.value = {
      id,
      materialCode: 'MAT-2026-001',
      materialName: 'SPCC',
      thickness: 1.0,
      width: 1000,
      unit: '公斤',
      stockQuantity: 1500,
      safetyStock: 500
    }
  } catch (error) {
    ElMessage.error('加载失败')
  }
}

const loadBatches = async () => {
  loading.value = true
  try {
    // TODO: API
    batchList.value = [
      {
        id: 1,
        batchNo: 'BATCH-2026-06-001',
        supplierName: '供应商A',
        quantity: 1000,
        remainingQuantity: 800,
        status: 'qualified',
        iqcResult: 'qualified',
        arrivalDate: '2026-06-15',
        expiryDate: '2026-12-15',
        storageLocation: '仓库A区01'
      }
    ]
    pagination.total = 1
  } catch (error) {
    ElMessage.error('加载批次失败')
  } finally {
    loading.value = false
  }
}

const loadSuppliers = async () => {
  try {
    suppliersList.value = [
      { id: 1, name: '供应商A' },
      { id: 2, name: '供应商B' }
    ]
  } catch (error) {
    ElMessage.error('加载供应商失败')
  }
}

const resetFilters = () => {
  filters.status = ''
  filters.batchNo = ''
  loadBatches()
}

const getStockColor = (current: number, safety: number) => {
  if (current < safety * 0.5) return 'danger'
  if (current < safety) return 'warning'
  return 'success'
}

const getStatusType = (status: string) => {
  const map: any = {
    pending_iqc: 'info',
    qualified: 'success',
    rejected: 'danger',
    in_use: 'warning',
    used_up: ''
  }
  return map[status] || ''
}

const getStatusText = (status: string) => {
  const map: any = {
    pending_iqc: '待检',
    qualified: '合格',
    rejected: '不合格',
    in_use: '使用中',
    used_up: '已用完'
  }
  return map[status] || status
}

const submitBatch = async () => {
  if (!batchFormRef.value) return
  await batchFormRef.value.validate(async (valid) => {
    if (valid) {
      submitting.value = true
      try {
        // TODO: API
        ElMessage.success('入库成功')
        showCreateDialog.value = false
        loadBatches()
      } catch (error) {
        ElMessage.error('入库失败')
      } finally {
        submitting.value = false
      }
    }
  })
}

const handleIQC = (row: any) => {
  currentBatch.value = row
  showIQCDialog.value = true
}

const submitIQC = async () => {
  if (!iqcFormRef.value) return
  await iqcFormRef.value.validate(async (valid) => {
    if (valid) {
      submitting.value = true
      try {
        // TODO: API
        ElMessage.success('检验完成')
        showIQCDialog.value = false
        loadBatches()
      } catch (error) {
        ElMessage.error('提交失败')
      } finally {
        submitting.value = false
      }
    }
  })
}

const viewDetail = (row: any) => {
  ElMessage.info('详情功能')
}

const goBack = () => router.back()
const goToSlitting = () => router.push(`/materials/slitting/${materialInfo.value.id}`)
const goToTrace = () => router.push('/materials/trace')

onMounted(() => {
  loadMaterialInfo()
  loadBatches()
  loadSuppliers()
})
</script>

<style scoped lang="scss">
.batches-container {
  padding: 20px;

  .page-title {
    font-size: 18px;
    font-weight: 500;
  }

  .content-wrapper {
    margin-top: 20px;

    .el-card {
      margin-bottom: 20px;
    }

    .actions-card {
      text-align: center;
    }

    .form-tip {
      margin-top: 4px;
    }

    .pagination-container {
      margin-top: 20px;
      display: flex;
      justify-content: flex-end;
    }
  }
}
</style>
