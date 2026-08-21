<template>
  <div class="slitting-container">
    <el-page-header @back="goBack" title="返回">
      <template #content>
        <span class="page-title">分条记录</span>
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
            {{ materialInfo.stockQuantity }} {{ materialInfo.unit }}
          </el-descriptions-item>
        </el-descriptions>
      </el-card>

      <!-- 创建分条任务按钮 -->
      <el-card class="actions-card">
        <el-button type="primary" size="large" @click="showCreateDialog = true">
          <el-icon><Plus /></el-icon>
          创建分条任务
        </el-button>
      </el-card>

      <!-- 分条记录列表 -->
      <el-card>
        <template #header>
          <span class="card-title">分条记录</span>
        </template>
        <el-table :data="slittingList" border stripe>
          <el-table-column type="expand">
            <template #default="{ row }">
              <div class="expand-content">
                <h4 style="margin-top: 0">子批次明细</h4>
                <el-table :data="row.childBatches" border>
                  <el-table-column prop="childBatchNo" label="子批次号" width="180" />
                  <el-table-column prop="targetWidth" label="目标宽度(mm)" width="120" align="center" />
                  <el-table-column prop="quantity" label="数量" width="120" align="right">
                    <template #default="{ row: child }">
                      {{ child.quantity }} {{ materialInfo.unit }}
                    </template>
                  </el-table-column>
                  <el-table-column prop="status" label="状态" width="100" align="center">
                    <template #default="{ row: child }">
                      <el-tag :type="child.status === 'completed' ? 'success' : 'warning'">
                        {{ child.status === 'completed' ? '已完成' : '分条中' }}
                      </el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column prop="completedAt" label="完成时间" width="160" />
                </el-table>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="taskNo" label="任务编号" width="160" fixed="left" />
          <el-table-column prop="parentBatchNo" label="母批次号" width="180" />
          <el-table-column prop="targetWidth" label="目标宽度(mm)" width="120" align="center" />
          <el-table-column prop="plannedQuantity" label="计划数量" width="120" align="right">
            <template #default="{ row }">
              {{ row.plannedQuantity }} {{ materialInfo.unit }}
            </template>
          </el-table-column>
          <el-table-column prop="actualQuantity" label="实际数量" width="120" align="right">
            <template #default="{ row }">
              {{ row.actualQuantity }} {{ materialInfo.unit }}
            </template>
          </el-table-column>
          <el-table-column prop="childBatchCount" label="子批次数" width="100" align="center">
            <template #default="{ row }">
              {{ row.childBatchCount }} 个
            </template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="100" align="center">
            <template #default="{ row }">
              <el-tag :type="getStatusType(row.status)">
                {{ getStatusText(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="operatorName" label="操作员" width="100" />
          <el-table-column prop="createdAt" label="创建时间" width="160" />
          <el-table-column label="操作" width="180" fixed="right">
            <template #default="{ row }">
              <el-button
                v-if="row.status === 'pending'"
                type="primary"
                link
                @click="handleStart(row)"
              >
                开始分条
              </el-button>
              <el-button
                v-if="row.status === 'in_progress'"
                type="success"
                link
                @click="handleComplete(row)"
              >
                完成
              </el-button>
              <el-button type="info" link @click="viewDetail(row)">详情</el-button>
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
            @size-change="loadData"
            @current-change="loadData"
          />
        </div>
      </el-card>
    </div>

    <!-- 创建分条任务对话框 -->
    <el-dialog
      v-model="showCreateDialog"
      title="创建分条任务"
      width="600px"
      :close-on-click-modal="false"
    >
      <el-form :model="slittingForm" :rules="slittingRules" ref="slittingFormRef" label-width="120px">
        <el-form-item label="选择母批次" prop="parentBatchId">
          <el-select v-model="slittingForm.parentBatchId" placeholder="选择批次" style="width: 100%">
            <el-option
              v-for="batch in availableBatches"
              :key="batch.id"
              :label="`${batch.batchNo} (剩余: ${batch.remainingQuantity}${materialInfo.unit})`"
              :value="batch.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="目标宽度(mm)" prop="targetWidth">
          <el-input-number v-model="slittingForm.targetWidth" :min="10" :max="1000" style="width: 100%" />
          <div class="form-tip">
            <el-text type="info" size="small">
              当前宽度：{{ materialInfo.width }}mm，将分条为目标宽度
            </el-text>
          </div>
        </el-form-item>
        <el-form-item label="计划数量" prop="plannedQuantity">
          <el-input-number v-model="slittingForm.plannedQuantity" :min="0" :precision="2" style="width: 200px" />
          <span style="margin-left: 10px">{{ materialInfo.unit }}</span>
        </el-form-item>
        <el-form-item label="操作员" prop="operatorId">
          <el-select v-model="slittingForm.operatorId" placeholder="选择操作员" style="width: 100%">
            <el-option
              v-for="operator in operatorsList"
              :key="operator.id"
              :label="operator.name"
              :value="operator.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="slittingForm.notes" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="submitSlitting" :loading="submitting">创建任务</el-button>
      </template>
    </el-dialog>

    <!-- 完成分条对话框 -->
    <el-dialog v-model="showCompleteDialog" title="完成分条" width="600px">
      <el-form :model="completeForm" :rules="completeRules" ref="completeFormRef" label-width="120px">
        <el-form-item label="任务编号">
          <el-text tag="b">{{ currentTask?.taskNo }}</el-text>
        </el-form-item>
        <el-form-item label="实际数量" prop="actualQuantity">
          <el-input-number v-model="completeForm.actualQuantity" :min="0" :precision="2" style="width: 200px" />
          <span style="margin-left: 10px">{{ materialInfo.unit }}</span>
        </el-form-item>
        <el-form-item label="生成子批次数" prop="childBatchCount">
          <el-input-number v-model="completeForm.childBatchCount" :min="1" :max="100" style="width: 200px" />
          <span style="margin-left: 10px">个</span>
          <div class="form-tip">
            <el-text type="info" size="small">
              系统将自动生成子批次号，并建立追溯关系
            </el-text>
          </div>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="completeForm.notes" type="textarea" :rows="3" />
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
import { Plus } from '@element-plus/icons-vue'
import type { FormInstance, FormRules } from 'element-plus'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const submitting = ref(false)
const showCreateDialog = ref(false)
const showCompleteDialog = ref(false)
const currentTask = ref<any>(null)

const materialInfo = ref<any>({})
const slittingList = ref<any[]>([])
const availableBatches = ref<any[]>([])
const operatorsList = ref<any[]>([])

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

const slittingFormRef = ref<FormInstance>()
const slittingForm = reactive({
  parentBatchId: null as any,
  targetWidth: 500,
  plannedQuantity: 0,
  operatorId: null as any,
  notes: ''
})

const slittingRules: FormRules = {
  parentBatchId: [{ required: true, message: '请选择母批次', trigger: 'change' }],
  targetWidth: [{ required: true, message: '请输入目标宽度', trigger: 'blur' }],
  plannedQuantity: [{ required: true, message: '请输入计划数量', trigger: 'blur' }],
  operatorId: [{ required: true, message: '请选择操作员', trigger: 'change' }]
}

const completeFormRef = ref<FormInstance>()
const completeForm = reactive({
  actualQuantity: 0,
  childBatchCount: 1,
  notes: ''
})

const completeRules: FormRules = {
  actualQuantity: [{ required: true, message: '请输入实际数量', trigger: 'blur' }],
  childBatchCount: [{ required: true, message: '请输入子批次数', trigger: 'blur' }]
}

const loadMaterialInfo = async () => {
  try {
    const id = route.params.id
    materialInfo.value = {
      id,
      materialCode: 'MAT-2026-001',
      materialName: 'SPCC',
      thickness: 1.0,
      width: 1000,
      unit: '公斤',
      stockQuantity: 1500
    }
  } catch (error) {
    ElMessage.error('加载失败')
  }
}

const loadData = async () => {
  loading.value = true
  try {
    // TODO: API
    slittingList.value = [
      {
        id: 1,
        taskNo: 'SLIT-2026-001',
        parentBatchNo: 'BATCH-2026-06-001',
        targetWidth: 500,
        plannedQuantity: 500,
        actualQuantity: 495,
        childBatchCount: 5,
        status: 'completed',
        operatorName: '张三',
        createdAt: '2026-06-20 10:00',
        childBatches: [
          {
            childBatchNo: 'BATCH-2026-06-001-001',
            targetWidth: 500,
            quantity: 99,
            status: 'completed',
            completedAt: '2026-06-20 11:30'
          }
        ]
      }
    ]
    pagination.total = 1
  } catch (error) {
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
}

const loadAvailableBatches = async () => {
  try {
    availableBatches.value = [
      { id: 1, batchNo: 'BATCH-2026-06-001', remainingQuantity: 800 }
    ]
  } catch (error) {
    ElMessage.error('加载批次失败')
  }
}

const loadOperators = async () => {
  try {
    operatorsList.value = [
      { id: 1, name: '张三' },
      { id: 2, name: '李四' }
    ]
  } catch (error) {
    ElMessage.error('加载操作员失败')
  }
}

const getStatusType = (status: string) => {
  const map: any = { pending: 'info', in_progress: 'warning', completed: 'success' }
  return map[status] || ''
}

const getStatusText = (status: string) => {
  const map: any = { pending: '待分条', in_progress: '分条中', completed: '已完成' }
  return map[status] || status
}

const submitSlitting = async () => {
  if (!slittingFormRef.value) return
  await slittingFormRef.value.validate(async (valid) => {
    if (valid) {
      submitting.value = true
      try {
        // TODO: API
        ElMessage.success('任务创建成功')
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

const handleStart = async (_row: any) => {
  try {
    // TODO: API
    ElMessage.success('已开始分条')
    loadData()
  } catch (error) {
    ElMessage.error('操作失败')
  }
}

const handleComplete = (row: any) => {
  currentTask.value = row
  completeForm.actualQuantity = row.plannedQuantity
  showCompleteDialog.value = true
}

const submitComplete = async () => {
  if (!completeFormRef.value) return
  await completeFormRef.value.validate(async (valid) => {
    if (valid) {
      submitting.value = true
      try {
        // TODO: API
        ElMessage.success('分条完成，已生成子批次')
        showCompleteDialog.value = false
        loadData()
      } catch (error) {
        ElMessage.error('操作失败')
      } finally {
        submitting.value = false
      }
    }
  })
}

const viewDetail = (_row: any) => {
  ElMessage.info('详情功能')
}

const goBack = () => router.back()

onMounted(() => {
  loadMaterialInfo()
  loadData()
  loadAvailableBatches()
  loadOperators()
})
</script>

<style scoped lang="scss">
.slitting-container {
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

    .actions-card {
      text-align: center;
    }

    .expand-content {
      padding: 16px;

      h4 {
        margin-bottom: 12px;
      }
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
