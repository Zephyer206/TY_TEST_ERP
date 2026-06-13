<template>
  <div class="quotes-container">
    <div class="page-header">
      <h2>报价管理</h2>
      <el-button type="primary" @click="handleCreate">
        <el-icon><Plus /></el-icon>
        新建报价
      </el-button>
    </div>

    <!-- 搜索筛选 -->
    <el-card class="filter-card">
      <el-form :inline="true" :model="filterForm">
        <el-form-item label="客户">
          <el-input v-model="filterForm.customer" placeholder="客户名称" clearable />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filterForm.status" placeholder="全部" clearable>
            <el-option label="待技术审核" value="WAITING_FOR_TECH" />
            <el-option label="技术已审核" value="TECH_APPROVED" />
            <el-option label="待老板审批" value="PENDING_BOSS" />
            <el-option label="已审批" value="APPROVED" />
            <el-option label="已驳回" value="REJECTED" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">搜索</el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 报价列表 -->
    <el-table :data="quotes" v-loading="loading" stripe>
      <el-table-column prop="quote_no" label="报价单号" width="180" />
      <el-table-column prop="customer_name" label="客户" min-width="150" />
      <el-table-column prop="customer_product_no" label="客户品号" width="150" />
      <el-table-column prop="vehicle_model" label="车型" width="120" />
      <el-table-column prop="final_price" label="单价" width="100" align="right">
        <template #default="{ row }">
          ¥{{ row.final_price }}
        </template>
      </el-table-column>
      <el-table-column prop="approval_status" label="状态" width="120">
        <template #default="{ row }">
          <el-tag :type="getStatusType(row.approval_status)">
            {{ getStatusText(row.approval_status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" width="160">
        <template #default="{ row }">
          {{ formatDate(row.created_at) }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" size="small" @click="handleView(row)">
            查看
          </el-button>
          <el-button link type="primary" size="small" @click="handleEdit(row)" v-if="canEdit(row)">
            编辑
          </el-button>
          <el-button link type="success" size="small" @click="handleApprove(row)" v-if="canApprove(row)">
            审批
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 分页 -->
    <div class="pagination">
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="handleSizeChange"
        @current-change="handlePageChange"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { get } from '@/utils/request'
import { handleApiError } from '@/utils/errorHandler'
import { formatDate } from '@/utils/format'

const quotes = ref([])
const loading = ref(false)
const userInfo = ref(JSON.parse(localStorage.getItem('userInfo') || '{}'))

const filterForm = reactive({
  customer: '',
  status: '',
})

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0,
})

// 状态映射
const statusMap = {
  WAITING_FOR_TECH: { text: '待技术审核', type: 'warning' },
  TECH_APPROVED: { text: '技术已审核', type: 'success' },
  TECH_REJECTED: { text: '技术已驳回', type: 'danger' },
  DRAFT: { text: '草稿', type: 'info' },
  PENDING_BOSS: { text: '待老板审批', type: 'warning' },
  APPROVED: { text: '已审批', type: 'success' },
  REJECTED: { text: '已驳回', type: 'danger' },
}

const getStatusType = (status) => statusMap[status]?.type || 'info'
const getStatusText = (status) => statusMap[status]?.text || status

// 权限检查
const canEdit = (row) => {
  return userInfo.value.role_level >= 5 && row.approval_status === 'DRAFT'
}

const canApprove = (row) => {
  if (row.approval_status === 'PENDING_BOSS') {
    return userInfo.value.role_level >= 9
  }
  if (row.approval_status === 'WAITING_FOR_TECH') {
    return userInfo.value.is_tech || userInfo.value.role_level >= 4
  }
  return false
}

// 获取报价列表
const fetchQuotes = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.pageSize,
      ...(filterForm.customer && { customer: filterForm.customer }),
      ...(filterForm.status && { status: filterForm.status }),
    }
    const data = await get('/quotes', params)
    quotes.value = data.items || data || []
    pagination.total = data.total || quotes.value.length
  } catch (error) {
    handleApiError(error, '获取报价列表失败')
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  pagination.page = 1
  fetchQuotes()
}

const handleReset = () => {
  filterForm.customer = ''
  filterForm.status = ''
  handleSearch()
}

const handleCreate = () => {
  ElMessage.info('新建报价功能开发中')
}

const handleView = (row) => {
  ElMessage.info(`查看报价: ${row.quote_no}`)
}

const handleEdit = (row) => {
  ElMessage.info(`编辑报价: ${row.quote_no}`)
}

const handleApprove = (row) => {
  ElMessage.info(`审批报价: ${row.quote_no}`)
}

const handleSizeChange = (size) => {
  pagination.pageSize = size
  fetchQuotes()
}

const handlePageChange = (page) => {
  pagination.page = page
  fetchQuotes()
}

onMounted(() => {
  fetchQuotes()
})
</script>

<style scoped>
.quotes-container {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0;
}

.filter-card {
  margin-bottom: 16px;
}

.pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
</style>
