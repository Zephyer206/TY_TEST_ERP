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
          <span style="color: #909399">共 {{ customerData.parts_count }} 个零件</span>
        </div>
      </template>

      <el-table :data="customerData.parts" v-loading="loading" stripe border max-height="600" :span-method="spanMethod">
        <el-table-column label="图片" width="100" align="center">
          <template #default="{ row }">
            <el-image
              v-if="row.image_url"
              :src="row.image_url"
              fit="contain"
              style="width: 60px; height: 60px"
              :preview-src-list="[row.image_url]"
              preview-teleported
            >
              <template #error>
                <div class="image-placeholder">
                  <el-icon><Picture /></el-icon>
                </div>
              </template>
            </el-image>
            <div v-else class="image-placeholder">
              <el-icon><Picture /></el-icon>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="display_name" label="零件名称" min-width="160" />
        <el-table-column prop="customer_part_no" label="客户件号" width="140" />
        <el-table-column :label="`${customerData.current_year}年售价`" width="140" align="right">
          <template #default="{ row }">
            <span v-if="row.current_year_price !== null">¥{{ row.current_year_price.toFixed(4) }}</span>
            <span v-else class="no-price">暂无价格</span>
          </template>
        </el-table-column>
        <el-table-column :label="`${customerData.previous_year}年售价`" width="140" align="right">
          <template #default="{ row }">
            <span v-if="row.previous_year_price !== null">¥{{ row.previous_year_price.toFixed(4) }}</span>
            <span v-else class="no-price">暂无价格</span>
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

    <el-dialog v-model="historyVisible" title="调价历史" width="800px">
      <div v-if="currentPart" style="margin-bottom: 16px">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="零件名称">{{ currentPart.display_name }}</el-descriptions-item>
          <el-descriptions-item label="客户件号">{{ currentPart.customer_part_no }}</el-descriptions-item>
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
import { Picture } from '@element-plus/icons-vue'
import { customersApi } from '@/api/customers'
import { customerPricesApi } from '@/api/pricing'

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
    const data = await customersApi.list({ limit: 200, has_parts: true })
    customers.value = Array.isArray(data) ? data : (data.items || [])
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
    const data = await customerPricesApi.yearPrices(selectedCustomerId.value)
    customerData.value = data
  } catch (e) {
    ElMessage.error('获取客户零件价格失败: ' + (e.message || '未知错误'))
  } finally {
    loading.value = false
  }
}

const spanMethod = ({ row, column, rowIndex, columnIndex }) => {
  if (columnIndex === 0) {
    const parts = customerData.value?.parts || []
    const currentImageUrl = row.image_url

    if (!currentImageUrl) {
      return { rowspan: 1, colspan: 1 }
    }

    if (rowIndex > 0) {
      const prevRow = parts[rowIndex - 1]
      if (prevRow.image_url === currentImageUrl) {
        const prevPrevRow = rowIndex > 1 ? parts[rowIndex - 2] : null
        if (prevPrevRow && prevPrevRow.image_url === currentImageUrl) {
          return { rowspan: 1, colspan: 1 }
        }
        return { rowspan: 0, colspan: 0 }
      }
    }

    if (rowIndex < parts.length - 1) {
      const nextRow = parts[rowIndex + 1]
      if (nextRow.image_url === currentImageUrl) {
        return { rowspan: 2, colspan: 1 }
      }
    }

    return { rowspan: 1, colspan: 1 }
  }
  return { rowspan: 1, colspan: 1 }
}

const viewPriceHistory = async (part) => {
  currentPart.value = part
  historyVisible.value = true
  historyLoading.value = true
  priceHistory.value = []

  try {
    const data = await customerPricesApi.priceHistory(selectedCustomerId.value, part.part_id)
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
.image-placeholder {
  width: 60px;
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: #f5f7fa;
  border: 1px dashed #dcdfe6;
  border-radius: 4px;
  color: #c0c4cc;
  font-size: 24px;
}
</style>
