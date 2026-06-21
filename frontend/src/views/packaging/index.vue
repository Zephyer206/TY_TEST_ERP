<template>
  <div class="packaging-container">
    <el-card class="header-card">
      <div class="header-content">
        <h2>包装管理</h2>
        <el-button type="primary" @click="goToCreate">
          <el-icon><Plus /></el-icon>
          创建包装记录
        </el-button>
      </div>
    </el-card>

    <!-- 统计卡片 -->
    <el-row :gutter="20" class="stats-row">
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-label">待入库</div>
            <div class="stat-value">{{ stats.pending }}</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-label">已入库</div>
            <div class="stat-value success">{{ stats.inStock }}</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-label">本月包装</div>
            <div class="stat-value">{{ stats.thisMonth }}</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-label">当前库存</div>
            <div class="stat-value info">{{ stats.stockTotal }}</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 筛选条件 -->
    <el-card class="filter-card">
      <el-form :inline="true" :model="filters">
        <el-form-item label="状态">
          <el-select v-model="filters.status" placeholder="全部状态" clearable style="width: 120px">
            <el-option label="待入库" value="pending" />
            <el-option label="已入库" value="in_stock" />
            <el-option label="已出库" value="out_stock" />
          </el-select>
        </el-form-item>
        <el-form-item label="零件">
          <el-input v-model="filters.partName" placeholder="零件名称" clearable style="width: 150px" />
        </el-form-item>
        <el-form-item label="包装号">
          <el-input v-model="filters.packagingNo" placeholder="包装号" clearable style="width: 180px" />
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

    <!-- 包装记录列表 -->
    <el-card>
      <el-table :data="packagingList" v-loading="loading" border stripe>
        <el-table-column prop="packagingNo" label="包装号" width="180" fixed="left">
          <template #default="{ row }">
            <div style="display: flex; align-items: center; gap: 8px">
              <el-icon><Barcode /></el-icon>
              <el-text tag="b">{{ row.packagingNo }}</el-text>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="partName" label="零件名称" width="180" />
        <el-table-column prop="partNo" label="零件号" width="130" />
        <el-table-column prop="quantity" label="包装数量" width="100" align="right">
          <template #default="{ row }">
            {{ row.quantity }} 个
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">
              {{ getStatusText(row.status) }}
            </el-tag>
          </el-template>
        </el-table-column>
        <el-table-column prop="packedBy" label="包装员" width="100" />
        <el-table-column prop="packagingTime" label="包装时间" width="160" />
        <el-table-column prop="inspectedBy" label="全检员" width="100" />
        <el-table-column prop="inspectionTime" label="全检时间" width="160" />
        <el-table-column prop="storageLocation" label="存放位置" width="120" />
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="viewDetail(row.id)">详情</el-button>
            <el-button
              v-if="row.status === 'pending'"
              type="success"
              link
              @click="goToInspect(row.id)"
            >
              全检入库
            </el-button>
            <el-button
              v-if="row.status === 'in_stock'"
              type="warning"
              link
              @click="handleOutStock(row)"
            >
              出库
            </el-button>
            <el-button type="info" link @click="printQR(row)">打印二维码</el-button>
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

    <!-- 出库对话框 -->
    <el-dialog v-model="showOutStockDialog" title="出库" width="500px">
      <el-form :model="outStockForm" :rules="outStockRules" ref="outStockFormRef" label-width="100px">
        <el-form-item label="包装号">
          <el-text tag="b">{{ currentPackaging?.packagingNo }}</el-text>
        </el-form-item>
        <el-form-item label="出库数量" prop="quantity">
          <el-input-number
            v-model="outStockForm.quantity"
            :min="1"
            :max="currentPackaging?.quantity"
            style="width: 200px"
          />
          <span style="margin-left: 10px">/ {{ currentPackaging?.quantity }} 个</span>
        </el-form-item>
        <el-form-item label="出库原因" prop="reason">
          <el-select v-model="outStockForm.reason" style="width: 100%">
            <el-option label="客户发货" value="shipment" />
            <el-option label="返工" value="rework" />
            <el-option label="其他" value="other" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="outStockForm.notes" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showOutStockDialog = false">取消</el-button>
        <el-button type="primary" @click="submitOutStock" :loading="submitting">确认出库</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus, Barcode } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import type { FormInstance, FormRules } from 'element-plus'

const router = useRouter()

const loading = ref(false)
const submitting = ref(false)
const showOutStockDialog = ref(false)
const currentPackaging = ref<any>(null)

const stats = reactive({
  pending: 0,
  inStock: 0,
  thisMonth: 0,
  stockTotal: 0
})

const filters = reactive({
  status: '',
  partName: '',
  packagingNo: '',
  dateRange: null as any
})

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

const packagingList = ref<any[]>([])

const outStockFormRef = ref<FormInstance>()
const outStockForm = reactive({
  quantity: 0,
  reason: '',
  notes: ''
})

const outStockRules: FormRules = {
  quantity: [{ required: true, message: '请输入出库数量', trigger: 'blur' }],
  reason: [{ required: true, message: '请选择出库原因', trigger: 'change' }]
}

const loadData = async () => {
  loading.value = true
  try {
    // TODO: API
    packagingList.value = [
      {
        id: 1,
        packagingNo: 'PKG-2026-001',
        partName: '冲压件A',
        partNo: 'P001',
        quantity: 500,
        status: 'in_stock',
        packedBy: '张三',
        packagingTime: '2026-06-20 14:00',
        inspectedBy: '李四',
        inspectionTime: '2026-06-20 15:30',
        storageLocation: '成品区A01'
      }
    ]
    pagination.total = 1

    // 统计数据
    stats.pending = 5
    stats.inStock = 120
    stats.thisMonth = 150
    stats.stockTotal = 50000
  } catch (error) {
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
}

const resetFilters = () => {
  filters.status = ''
  filters.partName = ''
  filters.packagingNo = ''
  filters.dateRange = null
  loadData()
}

const getStatusType = (status: string) => {
  const map: any = {
    pending: 'warning',
    in_stock: 'success',
    out_stock: ''
  }
  return map[status] || ''
}

const getStatusText = (status: string) => {
  const map: any = {
    pending: '待入库',
    in_stock: '已入库',
    out_stock: '已出库'
  }
  return map[status] || status
}

const goToCreate = () => {
  router.push('/packaging/create')
}

const viewDetail = (id: number) => {
  ElMessage.info('详情功能')
}

const goToInspect = (id: number) => {
  router.push(`/packaging/inspect/${id}`)
}

const handleOutStock = (row: any) => {
  currentPackaging.value = row
  outStockForm.quantity = row.quantity
  showOutStockDialog.value = true
}

const submitOutStock = async () => {
  if (!outStockFormRef.value) return
  await outStockFormRef.value.validate(async (valid) => {
    if (valid) {
      submitting.value = true
      try {
        // TODO: API
        ElMessage.success('出库成功')
        showOutStockDialog.value = false
        loadData()
      } catch (error) {
        ElMessage.error('出库失败')
      } finally {
        submitting.value = false
      }
    }
  })
}

const printQR = (row: any) => {
  ElMessage.info('打印二维码功能')
}

onMounted(() => {
  loadData()
})
</script>

<style scoped lang="scss">
.packaging-container {
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

  .stats-row {
    margin-bottom: 20px;

    .stat-card {
      .stat-content {
        text-align: center;

        .stat-label {
          font-size: 14px;
          color: #909399;
          margin-bottom: 8px;
        }

        .stat-value {
          font-size: 28px;
          font-weight: bold;
          color: #303133;

          &.success {
            color: #67c23a;
          }

          &.info {
            color: #409eff;
          }
        }
      }
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
