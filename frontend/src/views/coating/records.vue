<template>
  <div class="records-container">
    <el-card class="header-card">
      <div class="header-content">
        <h2>喷涂记录</h2>
        <el-button type="primary" @click="showCreateDialog = true">
          <el-icon><Plus /></el-icon>
          创建喷涂记录
        </el-button>
      </div>
    </el-card>

    <!-- 筛选条件 -->
    <el-card class="filter-card">
      <el-form :inline="true" :model="filters">
        <el-form-item label="配方">
          <el-select v-model="filters.recipeId" placeholder="全部配方" clearable style="width: 180px">
            <el-option
              v-for="recipe in recipesList"
              :key="recipe.id"
              :label="recipe.recipeName"
              :value="recipe.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="零件">
          <el-input v-model="filters.partName" placeholder="零件名称" clearable style="width: 150px" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.status" placeholder="全部状态" clearable style="width: 120px">
            <el-option label="待喷涂" value="pending" />
            <el-option label="喷涂中" value="in_progress" />
            <el-option label="已完成" value="completed" />
            <el-option label="不合格" value="rejected" />
          </el-select>
        </el-form-item>
        <el-form-item label="日期">
          <el-date-picker
            v-model="filters.dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            style="width: 260px"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadData">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 喷涂记录列表 -->
    <el-card>
      <el-table :data="recordList" v-loading="loading" border stripe>
        <el-table-column prop="recordNo" label="记录编号" width="160" fixed="left" />
        <el-table-column prop="partName" label="零件名称" width="180" />
        <el-table-column prop="recipeName" label="配方名称" width="180">
          <template #default="{ row }">
            <div style="display: flex; align-items: center; gap: 8px">
              <div class="color-preview" :style="{ backgroundColor: row.colorCode }"></div>
              <span>{{ row.recipeName }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="quantity" label="喷涂数量" width="100" align="right">
          <template #default="{ row }">
            {{ row.quantity }} 个
          </template>
        </el-table-column>
        <el-table-column prop="qualifiedQuantity" label="合格数量" width="100" align="right">
          <template #default="{ row }">
            {{ row.qualifiedQuantity }} 个
          </template>
        </el-table-column>
        <el-table-column prop="passRate" label="合格率" width="100" align="center">
          <template #default="{ row }">
            <el-text :type="getPassRateColor(row.passRate)">
              {{ row.passRate }}%
            </el-text>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">
              {{ getStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="operatorName" label="喷涂员" width="100" />
        <el-table-column prop="startTime" label="开始时间" width="160" />
        <el-table-column prop="endTime" label="完成时间" width="160" />
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.status === 'pending'"
              type="primary"
              link
              @click="handleStart(row)"
            >
              开始喷涂
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

    <!-- 创建喷涂记录对话框 -->
    <el-dialog
      v-model="showCreateDialog"
      title="创建喷涂记录"
      width="600px"
      :close-on-click-modal="false"
    >
      <el-form :model="recordForm" :rules="recordRules" ref="recordFormRef" label-width="120px">
        <el-form-item label="选择零件" prop="partId">
          <el-select v-model="recordForm.partId" placeholder="选择零件" filterable style="width: 100%">
            <el-option
              v-for="part in partsList"
              :key="part.id"
              :label="`${part.partName} (${part.partNo})`"
              :value="part.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="选择配方" prop="recipeId">
          <el-select v-model="recordForm.recipeId" placeholder="选择配方" style="width: 100%">
            <el-option
              v-for="recipe in recipesList"
              :key="recipe.id"
              :label="recipe.recipeName"
              :value="recipe.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="喷涂数量" prop="quantity">
          <el-input-number v-model="recordForm.quantity" :min="1" :max="10000" style="width: 200px" />
          <span style="margin-left: 10px">个</span>
        </el-form-item>
        <el-form-item label="喷涂员" prop="operatorId">
          <el-select v-model="recordForm.operatorId" placeholder="选择喷涂员" style="width: 100%">
            <el-option
              v-for="operator in operatorsList"
              :key="operator.id"
              :label="operator.name"
              :value="operator.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="recordForm.notes" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="submitRecord" :loading="submitting">创建</el-button>
      </template>
    </el-dialog>

    <!-- 完成喷涂对话框 -->
    <el-dialog v-model="showCompleteDialog" title="完成喷涂" width="600px">
      <el-form :model="completeForm" :rules="completeRules" ref="completeFormRef" label-width="120px">
        <el-form-item label="记录编号">
          <el-text tag="b">{{ currentRecord?.recordNo }}</el-text>
        </el-form-item>
        <el-form-item label="实际喷涂数" prop="actualQuantity">
          <el-input-number v-model="completeForm.actualQuantity" :min="0" :max="currentRecord?.quantity" style="width: 200px" />
          <span style="margin-left: 10px">/ {{ currentRecord?.quantity }} 个</span>
        </el-form-item>
        <el-form-item label="合格数量" prop="qualifiedQuantity">
          <el-input-number v-model="completeForm.qualifiedQuantity" :min="0" :max="completeForm.actualQuantity" style="width: 200px" />
          <span style="margin-left: 10px">个</span>
        </el-form-item>
        <el-form-item label="合格率">
          <el-text :type="getPassRateColor(getCompletePassRate())" tag="b" size="large">
            {{ getCompletePassRate() }}%
          </el-text>
        </el-form-item>
        <el-form-item label="质检结果" prop="inspectionResult">
          <el-radio-group v-model="completeForm.inspectionResult">
            <el-radio label="qualified">
              <el-tag type="success">合格</el-tag>
            </el-radio>
            <el-radio label="rejected">
              <el-tag type="danger">不合格</el-tag>
            </el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="质检意见">
          <el-input v-model="completeForm.inspectionComment" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="喷涂照片">
          <el-upload
            v-model:file-list="completeForm.photoList"
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
        <el-button @click="showCompleteDialog = false">取消</el-button>
        <el-button type="primary" @click="submitComplete" :loading="submitting">确认完成</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import type { FormInstance, FormRules, UploadFile } from 'element-plus'

const loading = ref(false)
const submitting = ref(false)
const showCreateDialog = ref(false)
const showCompleteDialog = ref(false)
const currentRecord = ref<any>(null)

const filters = reactive({
  recipeId: null as any,
  partName: '',
  status: '',
  dateRange: null as any
})

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

const recordList = ref<any[]>([])
const recipesList = ref<any[]>([])
const partsList = ref<any[]>([])
const operatorsList = ref<any[]>([])

const recordFormRef = ref<FormInstance>()
const recordForm = reactive({
  partId: null as any,
  recipeId: null as any,
  quantity: 100,
  operatorId: null as any,
  notes: ''
})

const recordRules: FormRules = {
  partId: [{ required: true, message: '请选择零件', trigger: 'change' }],
  recipeId: [{ required: true, message: '请选择配方', trigger: 'change' }],
  quantity: [{ required: true, message: '请输入数量', trigger: 'blur' }],
  operatorId: [{ required: true, message: '请选择喷涂员', trigger: 'change' }]
}

const completeFormRef = ref<FormInstance>()
const completeForm = reactive({
  actualQuantity: 0,
  qualifiedQuantity: 0,
  inspectionResult: 'qualified',
  inspectionComment: '',
  photoList: [] as UploadFile[]
})

const completeRules: FormRules = {
  actualQuantity: [{ required: true, message: '请输入实际喷涂数', trigger: 'blur' }],
  qualifiedQuantity: [{ required: true, message: '请输入合格数量', trigger: 'blur' }],
  inspectionResult: [{ required: true, message: '请选择质检结果', trigger: 'change' }]
}

const loadData = async () => {
  loading.value = true
  try {
    // TODO: API
    recordList.value = [
      {
        id: 1,
        recordNo: 'COA-2026-001',
        partName: '冲压件A',
        recipeName: '亮黑色粉末喷涂',
        colorCode: '#000000',
        quantity: 500,
        qualifiedQuantity: 495,
        passRate: 99,
        status: 'completed',
        operatorName: '李四',
        startTime: '2026-06-20 10:00',
        endTime: '2026-06-20 15:00'
      }
    ]
    pagination.total = 1
  } catch (error) {
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
}

const loadRecipes = async () => {
  try {
    recipesList.value = [
      { id: 1, recipeName: '亮黑色粉末喷涂' }
    ]
  } catch (error) {
    ElMessage.error('加载配方失败')
  }
}

const loadParts = async () => {
  try {
    partsList.value = [
      { id: 1, partName: '冲压件A', partNo: 'P001' }
    ]
  } catch (error) {
    ElMessage.error('加载零件失败')
  }
}

const loadOperators = async () => {
  try {
    operatorsList.value = [
      { id: 1, name: '李四' }
    ]
  } catch (error) {
    ElMessage.error('加载操作员失败')
  }
}

const resetFilters = () => {
  filters.recipeId = null
  filters.partName = ''
  filters.status = ''
  filters.dateRange = null
  loadData()
}

const getStatusType = (status: string) => {
  const map: any = {
    pending: 'info',
    in_progress: 'warning',
    completed: 'success',
    rejected: 'danger'
  }
  return map[status] || ''
}

const getStatusText = (status: string) => {
  const map: any = {
    pending: '待喷涂',
    in_progress: '喷涂中',
    completed: '已完成',
    rejected: '不合格'
  }
  return map[status] || status
}

const getPassRateColor = (rate: number) => {
  if (rate >= 95) return 'success'
  if (rate >= 85) return 'warning'
  return 'danger'
}

const getCompletePassRate = () => {
  if (completeForm.actualQuantity === 0) return 0
  return Math.round((completeForm.qualifiedQuantity / completeForm.actualQuantity) * 100)
}

watch(() => completeForm.qualifiedQuantity, () => {
  const rate = getCompletePassRate()
  if (rate >= 95) {
    completeForm.inspectionResult = 'qualified'
  } else if (rate < 85) {
    completeForm.inspectionResult = 'rejected'
  }
})

const handleStart = async (_row: any) => {
  try {
    // TODO: API
    ElMessage.success('已开始喷涂')
    loadData()
  } catch (error) {
    ElMessage.error('操作失败')
  }
}

const handleComplete = (row: any) => {
  currentRecord.value = row
  completeForm.actualQuantity = row.quantity
  completeForm.qualifiedQuantity = row.quantity
  showCompleteDialog.value = true
}

const viewDetail = (_row: any) => {
  ElMessage.info('详情功能')
}

const submitRecord = async () => {
  if (!recordFormRef.value) return
  await recordFormRef.value.validate(async (valid) => {
    if (valid) {
      submitting.value = true
      try {
        // TODO: API
        ElMessage.success('创建成功')
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

const submitComplete = async () => {
  if (!completeFormRef.value) return
  await completeFormRef.value.validate(async (valid) => {
    if (valid) {
      submitting.value = true
      try {
        // TODO: API
        ElMessage.success('喷涂完成')
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

onMounted(() => {
  loadData()
  loadRecipes()
  loadParts()
  loadOperators()
})
</script>

<style scoped lang="scss">
.records-container {
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

  .color-preview {
    width: 24px;
    height: 24px;
    border-radius: 4px;
    border: 1px solid #dcdfe6;
  }

  .pagination-container {
    margin-top: 20px;
    display: flex;
    justify-content: flex-end;
  }
}
</style>
