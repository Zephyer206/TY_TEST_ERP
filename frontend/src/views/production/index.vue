<template>
  <div class="production-container">
    <div class="page-header">
      <h2>生产计划</h2>
      <div class="header-actions">
        <el-button type="primary" @click="handleCreate">
          <el-icon><Plus /></el-icon>
          新建计划
        </el-button>
      </div>
    </div>

    <!-- 搜索筛选 -->
    <el-card class="filter-card">
      <el-form :inline="true" :model="filterForm">
        <el-form-item label="零件">
          <el-input v-model="filterForm.part" placeholder="零件名称/编号" clearable />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filterForm.status" placeholder="全部" clearable>
            <el-option label="待开始" value="planned" />
            <el-option label="进行中" value="in_progress" />
            <el-option label="已完成" value="completed" />
            <el-option label="已取消" value="cancelled" />
          </el-select>
        </el-form-item>
        <el-form-item label="日期范围">
          <el-date-picker
            v-model="filterForm.dateRange"
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

    <!-- 生产计划列表 -->
    <el-table :data="plans" v-loading="loading" stripe>
      <el-table-column prop="plan_no" label="计划单号" width="150" />
      <el-table-column prop="part_name" label="零件" min-width="180">
        <template #default="{ row }">
          <div>{{ row.part_name || row.part_number }}</div>
          <div class="text-secondary">{{ row.part_number }}</div>
        </template>
      </el-table-column>
      <el-table-column prop="planned_qty" label="计划数量" width="100" align="center" />
      <el-table-column prop="completed_qty" label="已完成" width="100" align="center">
        <template #default="{ row }">
          <el-progress
            :percentage="getProgress(row)"
            :color="getProgressColor(row)"
            :stroke-width="10"
          />
        </template>
      </el-table-column>
      <el-table-column prop="machine_name" label="机台" width="120" />
      <el-table-column prop="plan_date" label="计划日期" width="120" />
      <el-table-column prop="status" label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="getStatusType(row.status)">
            {{ getStatusText(row.status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="220" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" size="small" @click="handleView(row)">
            查看
          </el-button>
          <el-button link type="success" size="small" @click="handleReport(row)" v-if="canReport(row)">
            报工
          </el-button>
          <el-button link type="warning" size="small" @click="handleAssign(row)" v-if="canAssign(row)">
            分配机台
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

const plans = ref([])
const loading = ref(false)
const userInfo = ref(JSON.parse(localStorage.getItem('userInfo') || '{}'))

const filterForm = reactive({
  part: '',
  status: '',
  dateRange: [],
})

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0,
})

// 状态映射
const statusMap = {
  planned: { text: '待开始', type: 'info' },
  in_progress: { text: '进行中', type: 'warning' },
  completed: { text: '已完成', type: 'success' },
  cancelled: { text: '已取消', type: 'danger' },
  closed: { text: '已关闭', type: 'info' },
}

const getStatusType = (status) => statusMap[status]?.type || 'info'
const getStatusText = (status) => statusMap[status]?.text || status

// 计算进度
const getProgress = (row) => {
  if (!row.planned_qty) return 0
  return Math.round((row.completed_qty / row.planned_qty) * 100)
}

// 进度条颜色
const getProgressColor = (row) => {
  const pct = getProgress(row)
  if (pct >= 100) return '#67C23A'
  if (pct >= 50) return '#E6A23C'
  return '#409EFF'
}

// 权限检查
const canReport = (row) => {
  return row.status === 'in_progress' && userInfo.value.role_level >= 1
}

const canAssign = (row) => {
  return row.status === 'planned' && userInfo.value.role_level >= 3
}

// 获取生产计划列表
const fetchPlans = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.pageSize,
      ...(filterForm.part && { part: filterForm.part }),
      ...(filterForm.status && { status: filterForm.status }),
    }
    const data = await get('/production/plans', params)
    plans.value = data.items || data || []
    pagination.total = data.total || plans.value.length
  } catch (error) {
    handleApiError(error, '获取生产计划失败')
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  pagination.page = 1
  fetchPlans()
}

const handleReset = () => {
  filterForm.part = ''
  filterForm.status = ''
  filterForm.dateRange = []
  handleSearch()
}

const handleCreate = () => {
  ElMessage.info('新建生产计划功能开发中')
}

const handleView = (row) => {
  ElMessage.info(`查看计划: ${row.plan_no}`)
}

const handleReport = (row) => {
  ElMessage.info(`报工: ${row.plan_no}`)
}

const handleAssign = (row) => {
  ElMessage.info(`分配机台: ${row.plan_no}`)
}

const handleSizeChange = (size) => {
  pagination.pageSize = size
  fetchPlans()
}

const handlePageChange = (page) => {
  pagination.page = page
  fetchPlans()
}

onMounted(() => {
  fetchPlans()
})
</script>

<style scoped>
.production-container {
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

.header-actions {
  display: flex;
  gap: 12px;
}

.filter-card {
  margin-bottom: 16px;
}

.text-secondary {
  color: #909399;
  font-size: 12px;
}

.pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
</style>
