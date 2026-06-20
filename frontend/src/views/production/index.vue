<template>
  <div class="production-page">
    <!-- Header -->
    <div class="page-header">
      <h2>生产管理</h2>
      <div class="header-actions">
        <el-button type="primary" @click="handleCreatePlan">
          <el-icon><Plus /></el-icon> 新建计划
        </el-button>
      </div>
    </div>

    <!-- Status Summary -->
    <el-row :gutter="20" class="status-summary">
      <el-col :span="6">
        <el-card shadow="hover" class="summary-card">
          <div class="summary-item">
            <div class="summary-value">{{ stats.planned }}</div>
            <div class="summary-label">已计划</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="summary-card">
          <div class="summary-item">
            <div class="summary-value running">{{ stats.inProgress }}</div>
            <div class="summary-label">进行中</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="summary-card">
          <div class="summary-item">
            <div class="summary-value success">{{ stats.completed }}</div>
            <div class="summary-label">已完成</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="summary-card">
          <div class="summary-item">
            <div class="summary-value warning">{{ stats.overdue }}</div>
            <div class="summary-label">已逾期</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Filters -->
    <el-card class="filter-card" shadow="never">
      <el-form :inline="true" :model="filters">
        <el-form-item label="状态">
          <el-select v-model="filters.status" placeholder="全部状态" clearable>
            <el-option label="已计划" value="planned" />
            <el-option label="进行中" value="in_progress" />
            <el-option label="已完成" value="completed" />
            <el-option label="已取消" value="cancelled" />
          </el-select>
        </el-form-item>
        <el-form-item label="计划日期">
          <el-date-picker
            v-model="filters.dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            value-format="YYYY-MM-DD"
          />
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
        <el-table-column prop="plan_no" label="计划单号" width="150" />
        <el-table-column prop="plan_date" label="计划日期" width="110" />
        <el-table-column prop="part_name" label="零件名称" min-width="150" />
        <el-table-column label="计划数量" width="100" align="right">
          <template #default="{ row }">
            {{ row.planned_qty }}
          </template>
        </el-table-column>
        <el-table-column label="完成数量" width="100" align="right">
          <template #default="{ row }">
            {{ row.completed_qty || 0 }}
          </template>
        </el-table-column>
        <el-table-column label="完成率" width="90" align="center">
          <template #default="{ row }">
            <el-progress
              :percentage="calculateProgress(row)"
              :status="getProgressStatus(row)"
              :stroke-width="8"
            />
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">
              {{ getStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="handleView(row)">查看</el-button>
            <el-button
              v-if="row.status === 'planned'"
              link
              type="success"
              @click="handleStart(row)"
            >
              开始
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
import { http } from '@/utils/api-helper'

interface Plan {
  id: number
  plan_no: string
  plan_date: string
  part_id: number
  part_name: string
  planned_qty: number
  completed_qty: number
  status: string
  due_date: string
}

const router = useRouter()

// State
const loading = ref(false)
const tableData = ref<Plan[]>([])

// Stats
const stats = reactive({
  planned: 0,
  inProgress: 0,
  completed: 0,
  overdue: 0,
})

// Filters
const filters = reactive({
  status: '',
  dateRange: [] as string[],
})

// Pagination
const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0,
})

// Methods
const getStatusType = (status: string) => {
  const typeMap: Record<string, string> = {
    planned: 'info',
    in_progress: 'primary',
    completed: 'success',
    cancelled: 'danger',
    overdue: 'warning',
  }
  return typeMap[status] || 'info'
}

const getStatusLabel = (status: string) => {
  const labelMap: Record<string, string> = {
    planned: '已计划',
    in_progress: '进行中',
    completed: '已完成',
    cancelled: '已取消',
    overdue: '已逾期',
  }
  return labelMap[status] || status
}

const calculateProgress = (row: Plan) => {
  if (!row.planned_qty) return 0
  return Math.round(((row.completed_qty || 0) / row.planned_qty) * 100)
}

const getProgressStatus = (row: Plan) => {
  const pct = calculateProgress(row)
  if (pct >= 100) return 'success'
  if (pct >= 50) return 'primary'
  return 'warning'
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
    if (filters.dateRange?.length === 2) {
      params.append('start_date', filters.dateRange[0])
      params.append('end_date', filters.dateRange[1])
    }

    const response = await http.get<{ items: Plan[]; total: number }>(
      `/api/v1/production/plans?${params}`
    )

    tableData.value = response.items || []
    pagination.total = response.total || 0
  } catch (error) {
    ElMessage.error('获取数据失败')
  } finally {
    loading.value = false
  }
}

const fetchStats = async () => {
  try {
    const response = await http.get<typeof stats>('/api/v1/production/stats')
    Object.assign(stats, response)
  } catch (error) {
    console.error('Failed to fetch stats:', error)
  }
}

// Event handlers
const handleSearch = () => {
  pagination.page = 1
  fetchData()
}

const handleReset = () => {
  filters.status = ''
  filters.dateRange = []
  handleSearch()
}

const handleCreatePlan = () => {
  router.push('/production/new')
}

const handleView = (row: Plan) => {
  router.push(`/production/${row.id}`)
}

const handleStart = (row: Plan) => {
  router.push(`/production/${row.id}/start`)
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
  fetchStats()
})
</script>

<style scoped>
.production-page {
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

.status-summary {
  margin-bottom: 20px;
}

.summary-card {
  text-align: center;
}

.summary-item {
  padding: 10px 0;
}

.summary-value {
  font-size: 32px;
  font-weight: bold;
  color: #409eff;
}

.summary-value.running {
  color: #67c23a;
}

.summary-value.success {
  color: #e6a23c;
}

.summary-value.warning {
  color: #f56c6c;
}

.summary-label {
  font-size: 14px;
  color: #909399;
  margin-top: 5px;
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
