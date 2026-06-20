<template>
  <div class="dashboard-page">
    <!-- Welcome -->
    <div class="welcome-section">
      <h1>欢迎回来，{{ userName }}</h1>
      <p class="date">{{ currentDate }}</p>
    </div>

    <!-- Quick Stats -->
    <el-row :gutter="20" class="stats-row">
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-icon quotes">
              <el-icon><Document /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats.quotes }}</div>
              <div class="stat-label">待审批报价</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-icon plans">
              <el-icon><Calendar /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats.plans }}</div>
              <div class="stat-label">进行中计划</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-icon machines">
              <el-icon><Box /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats.runningMachines }}/{{ stats.totalMachines }}</div>
              <div class="stat-label">机台运行</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-icon quality">
              <el-icon><CircleCheck /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats.passRate }}%</div>
              <div class="stat-label">今日合格率</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Main Content -->
    <el-row :gutter="20">
      <!-- Recent Quotes -->
      <el-col :span="12">
        <el-card class="dashboard-card">
          <template #header>
            <div class="card-header">
              <span>待审批报价</span>
              <el-button link type="primary" @click="$router.push('/quotes')">
                查看全部
              </el-button>
            </div>
          </template>
          <el-table :data="recentQuotes" stripe size="small">
            <el-table-column prop="quote_serial" label="报价单号" width="130" />
            <el-table-column prop="part_name" label="零件" min-width="120" />
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <el-tag size="small" :type="getQuoteStatusType(row.approval_status)">
                  {{ getQuoteStatusLabel(row.approval_status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="80">
              <template #default="{ row }">
                <el-button link type="primary" size="small" @click="handleViewQuote(row)">
                  查看
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>

      <!-- Production Progress -->
      <el-col :span="12">
        <el-card class="dashboard-card">
          <template #header>
            <div class="card-header">
              <span>生产进度</span>
              <el-button link type="primary" @click="$router.push('/production')">
                查看全部
              </el-button>
            </div>
          </template>
          <el-table :data="recentPlans" stripe size="small">
            <el-table-column prop="plan_no" label="计划单号" width="120" />
            <el-table-column prop="part_name" label="零件" min-width="120" />
            <el-table-column label="进度" width="120">
              <template #default="{ row }">
                <el-progress
                  :percentage="calculateProgress(row)"
                  :stroke-width="6"
                  :show-text="false"
                />
                <span class="progress-text">
                  {{ row.completed_qty || 0 }}/{{ row.planned_qty }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <el-tag size="small" :type="getPlanStatusType(row.status)">
                  {{ getPlanStatusLabel(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <!-- Machine Status -->
    <el-row :gutter="20" class="machine-row">
      <el-col :span="24">
        <el-card class="dashboard-card">
          <template #header>
            <div class="card-header">
              <span>机台状态</span>
              <el-button link type="primary" @click="$router.push('/machines')">
                查看全部
              </el-button>
            </div>
          </template>
          <div class="machine-grid">
            <div
              v-for="machine in machines"
              :key="machine.id"
              class="machine-item"
              :class="machine.status"
            >
              <div class="machine-number">{{ machine.machine_number }}</div>
              <div class="machine-status">{{ getMachineStatusLabel(machine.status) }}</div>
              <div v-if="machine.current_mold_name" class="machine-mold">
                {{ machine.current_mold_name }}
              </div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Document, Calendar, Box, CircleCheck } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import { http } from '@/utils/api-helper'

const router = useRouter()
const userStore = useUserStore()

// Computed
const userName = computed(() => userStore.userInfo?.real_name || '用户')
const currentDate = computed(() => {
  const now = new Date()
  return now.toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    weekday: 'long',
  })
})

// Stats
const stats = reactive({
  quotes: 0,
  plans: 0,
  totalMachines: 0,
  runningMachines: 0,
  passRate: 0,
})

// Recent data
const recentQuotes = ref<any[]>([])
const recentPlans = ref<any[]>([])
const machines = ref<any[]>([])

// Status helpers
const getQuoteStatusType = (status: string) => {
  const map: Record<string, string> = {
    WAITING_FOR_TECH: 'warning',
    TECH_APPROVED: 'success',
    PENDING_BOSS: 'primary',
    REJECTED: 'danger',
  }
  return map[status] || 'info'
}

const getQuoteStatusLabel = (status: string) => {
  const map: Record<string, string> = {
    WAITING_FOR_TECH: '待技术审核',
    TECH_APPROVED: '技术通过',
    PENDING_BOSS: '待老板审批',
    REJECTED: '已驳回',
  }
  return map[status] || status
}

const getPlanStatusType = (status: string) => {
  const map: Record<string, string> = {
    planned: 'info',
    in_progress: 'primary',
    completed: 'success',
    cancelled: 'danger',
  }
  return map[status] || 'info'
}

const getPlanStatusLabel = (status: string) => {
  const map: Record<string, string> = {
    planned: '已计划',
    in_progress: '进行中',
    completed: '已完成',
    cancelled: '已取消',
  }
  return map[status] || status
}

const getMachineStatusLabel = (status: string) => {
  const map: Record<string, string> = {
    idle: '空闲',
    running: '运行中',
    fault: '故障',
    pending_check: '待检验',
    repairing: '维修中',
    offline: '离线',
  }
  return map[status] || status
}

const calculateProgress = (row: any) => {
  if (!row.planned_qty) return 0
  return Math.round(((row.completed_qty || 0) / row.planned_qty) * 100)
}

// Actions
const handleViewQuote = (row: any) => {
  router.push(`/quotes/${row.id}`)
}

// Fetch data
const fetchDashboardData = async () => {
  try {
    const [statsRes, quotesRes, plansRes, machinesRes] = await Promise.all([
      http.get<typeof stats>('/api/v1/dashboard/stats'),
      http.get<{ items: any[] }>('/api/v1/quotes?status=PENDING_BOSS&limit=5'),
      http.get<{ items: any[] }>('/api/v1/production/plans?status=in_progress&limit=5'),
      http.get<any[]>('/api/v1/machines'),
    ])

    Object.assign(stats, statsRes)
    recentQuotes.value = quotesRes.items || []
    recentPlans.value = plansRes.items || []
    machines.value = machinesRes.slice(0, 12) || []
  } catch (error) {
    console.error('Failed to fetch dashboard data:', error)
  }
}

// Lifecycle
onMounted(() => {
  fetchDashboardData()
})
</script>

<style scoped>
.dashboard-page {
  padding: 20px;
}

.welcome-section {
  margin-bottom: 30px;
}

.welcome-section h1 {
  margin: 0 0 5px 0;
  font-size: 28px;
  font-weight: 600;
}

.welcome-section .date {
  margin: 0;
  color: #909399;
  font-size: 14px;
}

/* Stats Row */
.stats-row {
  margin-bottom: 20px;
}

.stat-card {
  height: 100px;
}

.stat-content {
  display: flex;
  align-items: center;
  gap: 20px;
  height: 60px;
}

.stat-icon {
  width: 60px;
  height: 60px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28px;
  color: #fff;
}

.stat-icon.quotes {
  background: linear-gradient(135deg, #409eff, #66b1ff);
}

.stat-icon.plans {
  background: linear-gradient(135deg, #67c23a, #85ce61);
}

.stat-icon.machines {
  background: linear-gradient(135deg, #e6a23c, #ebb563);
}

.stat-icon.quality {
  background: linear-gradient(135deg, #909399, #a6a9ad);
}

.stat-info {
  flex: 1;
}

.stat-value {
  font-size: 28px;
  font-weight: bold;
  color: #303133;
  line-height: 1.2;
}

.stat-label {
  font-size: 14px;
  color: #909399;
  margin-top: 4px;
}

/* Dashboard Cards */
.dashboard-card {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.progress-text {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}

/* Machine Grid */
.machine-row {
  margin-bottom: 20px;
}

.machine-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 12px;
}

.machine-item {
  background: #f5f7fa;
  border-radius: 8px;
  padding: 15px;
  text-align: center;
  transition: all 0.3s;
}

.machine-item:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.machine-item.running {
  background: linear-gradient(135deg, #e8f4e8, #d1f2d1);
  border: 1px solid #67c23a;
}

.machine-item.fault {
  background: linear-gradient(135deg, #fde2e2, #fbc4c4);
  border: 1px solid #f56c6c;
}

.machine-item.idle {
  background: linear-gradient(135deg, #f4f4f5, #e9e9eb);
  border: 1px solid #909399;
}

.machine-number {
  font-size: 18px;
  font-weight: bold;
  color: #303133;
}

.machine-status {
  font-size: 12px;
  color: #606266;
  margin-top: 4px;
}

.machine-mold {
  font-size: 11px;
  color: #909399;
  margin-top: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
