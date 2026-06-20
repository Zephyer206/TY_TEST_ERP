<template>
  <div class="quotes-page">
    <!-- Header -->
    <div class="page-header">
      <h2>报价管理</h2>
      <div class="header-actions">
        <el-button type="primary" @click="handleCreate">
          <el-icon><Plus /></el-icon> 新建报价
        </el-button>
      </div>
    </div>

    <!-- Filters -->
    <el-card class="filter-card" shadow="never">
      <el-form :inline="true" :model="filters">
        <el-form-item label="状态">
          <el-select v-model="filters.status" placeholder="全部状态" clearable>
            <el-option label="等待技术审核" value="WAITING_FOR_TECH" />
            <el-option label="技术审核通过" value="TECH_APPROVED" />
            <el-option label="技术审核驳回" value="TECH_REJECTED" />
            <el-option label="草稿" value="DRAFT" />
            <el-option label="待老板审批" value="PENDING_BOSS" />
            <el-option label="已审批" value="APPROVED" />
            <el-option label="已驳回" value="REJECTED" />
          </el-select>
        </el-form-item>
        <el-form-item label="零件号">
          <el-input v-model="filters.partNo" placeholder="零件号" clearable />
        </el-form-item>
        <el-form-item label="客户">
          <el-input v-model="filters.customer" placeholder="客户名称" clearable />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">搜索</el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- Table -->
    <el-card class="table-card">
      <el-table :data="tableData" v-loading="loading" stripe>
        <el-table-column prop="quote_serial" label="报价单号" width="160" />
        <el-table-column prop="part_no" label="零件号" width="140" />
        <el-table-column prop="part_name" label="零件名称" min-width="150" />
        <el-table-column prop="customer_name" label="客户" width="120" />
        <el-table-column label="状态" width="130">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.approval_status)">
              {{ getStatusLabel(row.approval_status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="final_price" label="最终报价" width="110" align="right">
          <template #default="{ row }">
            {{ row.final_price ? `¥${row.final_price.toFixed(2)}` : '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="submitted_at" label="提交时间" width="160">
          <template #default="{ row }">
            {{ row.submitted_at ? formatDate(row.submitted_at) : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="handleView(row)">查看</el-button>
            <el-button
              v-if="canEdit(row)"
              link
              type="primary"
              @click="handleEdit(row)"
            >
              编辑
            </el-button>
            <el-button
              v-if="canApprove(row)"
              link
              type="success"
              @click="handleApprove(row)"
            >
              审批
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- Pagination -->
      <div class="pagination-wrapper">
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
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import { http } from '@/utils/api-helper'

interface Quote {
  id: number
  quote_serial: string
  part_id: number
  part_no: string
  part_name: string
  customer_id: number
  customer_name: string
  approval_status: string
  final_price: number | null
  submitted_at: string | null
  created_at: string
}

const router = useRouter()
const userStore = useUserStore()

// State
const loading = ref(false)
const tableData = ref<Quote[]>([])

// Filters
const filters = reactive({
  status: '',
  partNo: '',
  customer: '',
})

// Pagination
const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0,
})

// Role check
const roleLevel = computed(() => userStore.userInfo?.role_level || 0)

// Methods
const getStatusType = (status: string) => {
  const typeMap: Record<string, string> = {
    WAITING_FOR_TECH: 'warning',
    TECH_APPROVED: 'success',
    TECH_REJECTED: 'danger',
    DRAFT: 'info',
    PENDING_BOSS: 'primary',
    APPROVED: 'success',
    REJECTED: 'danger',
  }
  return typeMap[status] || 'info'
}

const getStatusLabel = (status: string) => {
  const labelMap: Record<string, string> = {
    WAITING_FOR_TECH: '等待技术审核',
    TECH_APPROVED: '技术审核通过',
    TECH_REJECTED: '技术审核驳回',
    DRAFT: '草稿',
    PENDING_BOSS: '待老板审批',
    APPROVED: '已审批',
    REJECTED: '已驳回',
  }
  return labelMap[status] || status
}

const formatDate = (dateStr: string) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

const canEdit = (row: Quote) => {
  // Can edit DRAFT or REJECTED quotes
  return ['DRAFT', 'REJECTED'].includes(row.approval_status) && roleLevel.value >= 4
}

const canApprove = (row: Quote) => {
  // Boss can approve PENDING_BOSS quotes
  if (row.approval_status === 'PENDING_BOSS' && roleLevel.value >= 9) {
    return true
  }
  // Tech can approve WAITING_FOR_TECH quotes
  if (row.approval_status === 'WAITING_FOR_TECH' && roleLevel.value >= 2) {
    return true
  }
  return false
}

// API calls
const fetchData = async () => {
  loading.value = true
  try {
    const params = new URLSearchParams({
      page: pagination.page.toString(),
      page_size: pagination.pageSize.toString(),
    })

    if (filters.status) params.append('status', filters.status)
    if (filters.partNo) params.append('part_no', filters.partNo)
    if (filters.customer) params.append('customer', filters.customer)

    const response = await http.get<{ items: Quote[]; total: number }>(
      `/api/v1/quotes?${params}`
    )

    tableData.value = response.items || []
    pagination.total = response.total || 0
  } catch (error) {
    ElMessage.error('获取数据失败')
  } finally {
    loading.value = false
  }
}

// Event handlers
const handleSearch = () => {
  pagination.page = 1
  fetchData()
}

const handleReset = () => {
  filters.status = ''
  filters.partNo = ''
  filters.customer = ''
  handleSearch()
}

const handleCreate = () => {
  router.push('/quotes/new')
}

const handleView = (row: Quote) => {
  router.push(`/quotes/${row.id}`)
}

const handleEdit = (row: Quote) => {
  router.push(`/quotes/${row.id}/edit`)
}

const handleApprove = (row: Quote) => {
  router.push(`/quotes/${row.id}/approve`)
}

const handleSizeChange = () => {
  fetchData()
}

const handlePageChange = () => {
  fetchData()
}

// Lifecycle
onMounted(() => {
  fetchData()
})
</script>

<style scoped>
.quotes-page {
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
  font-size: 20px;
  font-weight: 600;
}

.filter-card {
  margin-bottom: 20px;
}

.table-card {
  margin-bottom: 20px;
}

.pagination-wrapper {
  display: flex;
  justify-content: flex-end;
  margin-top: 20px;
}
</style>
