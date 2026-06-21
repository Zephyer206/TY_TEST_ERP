<template>
  <div class="inventory-container">
    <el-card class="header-card">
      <h2>包装库存</h2>
    </el-card>

    <!-- 统计卡片 -->
    <el-row :gutter="20" class="stats-row">
      <el-col :span="8">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-label">总库存数量</div>
            <div class="stat-value primary">{{ stats.totalQuantity }}</div>
            <div class="stat-unit">个</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-label">包装批次数</div>
            <div class="stat-value success">{{ stats.totalPackages }}</div>
            <div class="stat-unit">批</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-label">零件品种数</div>
            <div class="stat-value info">{{ stats.totalParts }}</div>
            <div class="stat-unit">种</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 筛选条件 -->
    <el-card class="filter-card">
      <el-form :inline="true" :model="filters">
        <el-form-item label="零件">
          <el-input v-model="filters.partName" placeholder="零件名称" clearable style="width: 180px" />
        </el-form-item>
        <el-form-item label="存放位置">
          <el-input v-model="filters.location" placeholder="位置" clearable style="width: 150px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadData">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 库存列表 -->
    <el-card>
      <el-table :data="inventoryList" v-loading="loading" border stripe show-summary>
        <el-table-column type="expand">
          <template #default="{ row }">
            <div class="expand-content">
              <h4>包装明细</h4>
              <el-table :data="row.packages" border>
                <el-table-column prop="packagingNo" label="包装号" width="180" />
                <el-table-column prop="quantity" label="数量" width="100" align="right">
                  <template #default="{ row: pkg }">
                    {{ pkg.quantity }} 个
                  </template>
                </el-table-column>
                <el-table-column prop="packagingTime" label="包装时间" width="160" />
                <el-table-column prop="inspectionTime" label="入库时间" width="160" />
                <el-table-column prop="storageLocation" label="存放位置" width="120" />
              </el-table>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="partName" label="零件名称" width="200" fixed="left" />
        <el-table-column prop="partNo" label="零件号" width="130" />
        <el-table-column prop="totalQuantity" label="总库存" width="120" align="right">
          <template #default="{ row }">
            <el-text tag="b" type="primary">{{ row.totalQuantity }} 个</el-text>
          </template>
        </el-table-column>
        <el-table-column prop="packageCount" label="包装批次" width="100" align="center">
          <template #default="{ row }">
            {{ row.packageCount }} 批
          </template>
        </el-table-column>
        <el-table-column prop="lastPackagingDate" label="最近包装" width="110" />
        <el-table-column prop="storageLocations" label="存放位置" min-width="200">
          <template #default="{ row }">
            <el-tag
              v-for="loc in row.storageLocations"
              :key="loc"
              size="small"
              style="margin-right: 5px"
            >
              {{ loc }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="viewFlow(row)">
              库存流水
            </el-button>
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

    <!-- 库存流水对话框 -->
    <el-dialog v-model="showFlowDialog" title="库存流水" width="800px">
      <el-table :data="flowRecords" border stripe max-height="400">
        <el-table-column prop="time" label="时间" width="160" />
        <el-table-column prop="type" label="类型" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.type === 'in' ? 'success' : 'warning'">
              {{ row.type === 'in' ? '入库' : '出库' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="packagingNo" label="包装号" width="180" />
        <el-table-column prop="quantity" label="数量" width="100" align="right">
          <template #default="{ row }">
            <el-text :type="row.type === 'in' ? 'success' : 'warning'">
              {{ row.type === 'in' ? '+' : '-' }}{{ row.quantity }} 个
            </el-text>
          </template>
        </el-table-column>
        <el-table-column prop="operatorName" label="操作人" width="100" />
        <el-table-column prop="notes" label="备注" min-width="150" />
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'

const loading = ref(false)
const showFlowDialog = ref(false)

const stats = reactive({
  totalQuantity: 0,
  totalPackages: 0,
  totalParts: 0
})

const filters = reactive({
  partName: '',
  location: ''
})

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

const inventoryList = ref<any[]>([])
const flowRecords = ref<any[]>([])

const loadData = async () => {
  loading.value = true
  try {
    // TODO: API
    inventoryList.value = [
      {
        id: 1,
        partName: '冲压件A',
        partNo: 'P001',
        totalQuantity: 45000,
        packageCount: 90,
        lastPackagingDate: '2026-06-20',
        storageLocations: ['成品区A01', '成品区A02'],
        packages: [
          {
            packagingNo: 'PKG-2026-001',
            quantity: 500,
            packagingTime: '2026-06-20 14:00',
            inspectionTime: '2026-06-20 15:30',
            storageLocation: '成品区A01'
          }
        ]
      }
    ]
    pagination.total = 1

    stats.totalQuantity = 50000
    stats.totalPackages = 100
    stats.totalParts = 25
  } catch (error) {
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
}

const resetFilters = () => {
  filters.partName = ''
  filters.location = ''
  loadData()
}

const viewFlow = async (row: any) => {
  try {
    // TODO: API
    flowRecords.value = [
      {
        time: '2026-06-20 15:30',
        type: 'in',
        packagingNo: 'PKG-2026-001',
        quantity: 500,
        operatorName: '李四',
        notes: '全检入库'
      },
      {
        time: '2026-06-21 10:00',
        type: 'out',
        packagingNo: 'PKG-2026-001',
        quantity: 500,
        operatorName: '王五',
        notes: '客户发货'
      }
    ]
    showFlowDialog.value = true
  } catch (error) {
    ElMessage.error('加载流水失败')
  }
}

onMounted(() => {
  loadData()
})
</script>

<style scoped lang="scss">
.inventory-container {
  padding: 20px;

  .header-card {
    margin-bottom: 20px;

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
          font-size: 32px;
          font-weight: bold;
          margin-bottom: 4px;

          &.primary {
            color: #409eff;
          }

          &.success {
            color: #67c23a;
          }

          &.info {
            color: #909399;
          }
        }

        .stat-unit {
          font-size: 14px;
          color: #909399;
        }
      }
    }
  }

  .filter-card {
    margin-bottom: 20px;
  }

  .expand-content {
    padding: 16px;

    h4 {
      margin-top: 0;
      margin-bottom: 12px;
    }
  }

  .pagination-container {
    margin-top: 20px;
    display: flex;
    justify-content: flex-end;
  }
}
</style>
