<template>
  <div class="customer-prices-container">
    <div class="page-header">
      <h2>客户零件价格查询</h2>
    </div>

    <el-card class="filter-card">
      <el-form :inline="true">
        <el-form-item label="选择客户">
          <el-select
            v-model="selectedCustomerId"
            placeholder="请选择客户"
            filterable
            style="width: 300px"
            @change="handleCustomerChange"
          >
            <el-option
              v-for="c in customers"
              :key="c.id"
              :value="c.id"
              :label="c.customer_code ? `${c.customer_code} ${c.name}` : c.name"
            />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="fetchCustomerParts" :disabled="!selectedCustomerId">
            查询
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card v-if="customerData" class="result-card">
      <template #header>
        <div class="card-header">
          <span>
            <strong>{{ customerData.customer_name }}</strong>
            <el-tag v-if="customerData.customer_code" type="primary" size="small" style="margin-left: 8px">
              {{ customerData.customer_code }}
            </el-tag>
          </span>
          <span style="color: #909399">共 {{ customerData.parts_count }} 个零件</span>
        </div>
      </template>

      <el-table :data="customerData.parts" v-loading="loading" stripe border max-height="600">
        <el-table-column prop="part_id" label="零件ID" width="100" fixed />
        <el-table-column prop="internal_name" label="内部零件名称" min-width="160" fixed />
        <el-table-column prop="customer_part_no" label="客户件号" width="140" />
        <el-table-column prop="customer_part_name" label="客户件名" min-width="140" />
        <el-table-column prop="material_name" label="材料" width="120" />
        <el-table-column label="价格状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.has_price_account ? 'success' : 'info'" size="small">
              {{ row.has_price_account ? '有价格' : '暂无价格' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="材料单价" width="120" align="right">
          <template #default="{ row }">
            <span v-if="row.material_unit_price !== null">¥{{ row.material_unit_price.toFixed(4) }}</span>
            <span v-else class="no-price">-</span>
          </template>
        </el-table-column>
        <el-table-column label="废料单价" width="120" align="right">
          <template #default="{ row }">
            <span v-if="row.scrap_price !== null">¥{{ row.scrap_price.toFixed(4) }}</span>
            <span v-else class="no-price">-</span>
          </template>
        </el-table-column>
        <el-table-column label="表面处理" width="120" align="right">
          <template #default="{ row }">
            <span v-if="row.surface_treatment_cost !== null">¥{{ row.surface_treatment_cost.toFixed(4) }}</span>
            <span v-else class="no-price">-</span>
          </template>
        </el-table-column>
        <el-table-column label="材料成本" width="120" align="right">
          <template #default="{ row }">
            <span v-if="row.material_cost !== null">¥{{ row.material_cost.toFixed(4) }}</span>
            <span v-else class="no-price">-</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="viewPriceHistory(row)">
              调价历史
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-empty v-else-if="!loading" description="请选择客户查询零件价格" :image-size="120" />

    <!-- 调价历史对话框 -->
    <el-dialog v-model="historyVisible" title="调价历史" width="800px">
      <div v-if="currentPart" style="margin-bottom: 16px">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="零件ID">{{ currentPart.part_id }}</el-descriptions-item>
          <el-descriptions-item label="内部名称">{{ currentPart.internal_name }}</el-descriptions-item>
          <el-descriptions-item label="客户件号">{{ currentPart.customer_part_no }}</el-descriptions-item>
          <el-descriptions-item label="客户件名">{{ currentPart.customer_part_name || '-' }}</el-descriptions-item>
        </el-descriptions>
      </div>

      <el-table :data="priceHistory" v-loading="historyLoading" stripe border max-height="400">
        <el-table-column label="调价类型" width="100">
          <template #default="{ row }">
            <el-tag size="small">{{ row.adjustment_type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="原价格" width="120" align="right">
          <template #default="{ row }">
            <span v-if="row.old_price !== null">¥{{ row.old_price.toFixed(4) }}</span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="新价格" width="120" align="right">
          <template #default="{ row }">¥{{ row.new_price.toFixed(4) }}</template>
        </el-table-column>
        <el-table-column prop="reason" label="调价原因" min-width="140" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusTypeMap[row.status] || 'info'" size="small">
              {{ statusLabelMap[row.status] || row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="申请时间" width="160">
          <template #default="{ row }">{{ formatDate(row.requested_at) }}</template>
        </el-table-column>
      </el-table>

      <el-empty v-if="!historyLoading && priceHistory.length === 0" description="暂无调价记录" :image-size="80" />

      <template #footer>
        <el-button @click="historyVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { get } from '@/utils/request'

const customers = ref([])
const selectedCustomerId = ref(null)
const customerData = ref(null)
const loading = ref(false)
const historyVisible = ref(false)
const historyLoading = ref(false)
const priceHistory = ref([])
const currentPart = ref(null)

const statusTypeMap = {
  pending: 'warning',
  approved: 'success',
  rejected: 'danger',
  cancelled: 'info',
}

const statusLabelMap = {
  pending: '待审批',
  approved: '已批准',
  rejected: '已拒绝',
  cancelled: '已取消',
}

const fetchCustomers = async () => {
  try {
    customers.value = await get('/customers', { limit: 200, has_parts: true })
  } catch (e) {
    ElMessage.error('获取客户列表失败: ' + (e.message || '未知错误'))
  }
}

const handleCustomerChange = () => {
  customerData.value = null
}

const fetchCustomerParts = async () => {
  if (!selectedCustomerId.value) return

  loading.value = true
  try {
    const data = await get(`/customer-prices/customers/${selectedCustomerId.value}/parts-with-prices`)
    customerData.value = data
  } catch (e) {
    ElMessage.error('获取客户零件价格失败: ' + (e.message || '未知错误'))
  } finally {
    loading.value = false
  }
}

const viewPriceHistory = async (part) => {
  currentPart.value = part
  historyVisible.value = true
  historyLoading.value = true
  priceHistory.value = []

  try {
    const data = await get(`/customer-prices/customers/${selectedCustomerId.value}/parts/${part.part_id}/price-history`)
    priceHistory.value = data
  } catch (e) {
    ElMessage.error('获取调价历史失败: ' + (e.message || '未知错误'))
  } finally {
    historyLoading.value = false
  }
}

const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

onMounted(() => {
  fetchCustomers()
})
</script>

<style scoped>
.customer-prices-container { padding: 20px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.page-header h2 { margin: 0; }
.filter-card { margin-bottom: 16px; }
.result-card { margin-bottom: 16px; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.no-price { color: #c0c4cc; }
</style>
