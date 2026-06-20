<template>
  <div class="dashboard-container">
    <!-- 欢迎信息 -->
    <div class="welcome-section">
      <h1>欢迎回来，{{ userInfo.real_name || userInfo.username }}</h1>
      <p class="welcome-sub">{{ currentDateTime }}</p>
    </div>

    <!-- 统计卡片 -->
    <el-row :gutter="20" class="stats-row">
      <el-col :xs="24" :sm="12" :lg="6">
        <div class="stat-card stat-quotes">
          <div class="stat-icon"><el-icon><Document /></el-icon></div>
          <div class="stat-content">
            <div class="stat-value">{{ stats.pendingQuotes }}</div>
            <div class="stat-label">待审批报价</div>
          </div>
        </div>
      </el-col>
      <el-col :xs="24" :sm="12" :lg="6">
        <div class="stat-card stat-production">
          <div class="stat-icon"><el-icon><Setting /></el-icon></div>
          <div class="stat-content">
            <div class="stat-value">{{ stats.activePlans }}</div>
            <div class="stat-label">进行中计划</div>
          </div>
        </div>
      </el-col>
      <el-col :xs="24" :sm="12" :lg="6">
        <div class="stat-card stat-quality">
          <div class="stat-icon"><el-icon><CircleCheck /></el-icon></div>
          <div class="stat-content">
            <div class="stat-value">{{ stats.todayInspections }}</div>
            <div class="stat-label">今日检验</div>
          </div>
        </div>
      </el-col>
      <el-col :xs="24" :sm="12" :lg="6">
        <div class="stat-card stat-warehouse">
          <div class="stat-icon"><el-icon><Box /></el-icon></div>
          <div class="stat-content">
            <div class="stat-value">{{ stats.lowStockItems }}</div>
            <div class="stat-label">库存预警</div>
          </div>
        </div>
      </el-col>
    </el-row>

    <!-- 内容区域 -->
    <el-row :gutter="20">
      <!-- 待办事项 -->
      <el-col :xs="24" :lg="12">
        <el-card class="todo-card">
          <template #header>
            <div class="card-header">
              <span>待办事项</span>
              <el-badge :value="todos.length" class="badge" />
            </div>
          </template>
          <el-scrollbar height="300px">
            <div class="todo-list" v-if="todos.length">
              <div v-for="todo in todos" :key="todo.id" class="todo-item">
                <el-checkbox v-model="todo.done" @change="handleTodoChange(todo)">
                  <span :class="{ 'todo-done': todo.done }">{{ todo.title }}</span>
                </el-checkbox>
                <el-tag :type="getPriorityType(todo.priority)" size="small">
                  {{ getPriorityText(todo.priority) }}
                </el-tag>
              </div>
            </div>
            <el-empty v-else description="暂无待办" />
          </el-scrollbar>
        </el-card>
      </el-col>

      <!-- 最新动态 -->
      <el-col :xs="24" :lg="12">
        <el-card class="activity-card">
          <template #header>
            <div class="card-header">
              <span>最新动态</span>
            </div>
          </template>
          <el-scrollbar height="300px">
            <el-timeline v-if="activities.length">
              <el-timeline-item
                v-for="activity in activities"
                :key="activity.id"
                :timestamp="activity.time"
                :type="getActivityType(activity.type)"
                placement="top"
              >
                <el-card>
                  <h4>{{ activity.title }}</h4>
                  <p class="activity-desc">{{ activity.description }}</p>
                </el-card>
              </el-timeline-item>
            </el-timeline>
            <el-empty v-else description="暂无动态" />
          </el-scrollbar>
        </el-card>
      </el-col>
    </el-row>

    <!-- 机台状态概览 -->
    <el-card class="machine-overview" v-if="userInfo.role_level >= 3">
      <template #header>
        <div class="card-header">
          <span>机台状态概览</span>
          <el-button link type="primary" @click="$router.push('/machines')">查看详情</el-button>
        </div>
      </template>
      <el-row :gutter="16">
        <el-col :xs="12" :sm="8" :md="4" v-for="status in machineStatuses" :key="status.key">
          <div class="machine-status-item">
            <div class="machine-count" :style="{ color: status.color }">{{ status.count }}</div>
            <div class="machine-label">{{ status.label }}</div>
          </div>
        </el-col>
      </el-row>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { Document, Setting, CircleCheck, Box } from '@element-plus/icons-vue'
import { get } from '@/utils/request'
import { handleApiError } from '@/utils/errorHandler'

const userInfo = ref(JSON.parse(localStorage.getItem('userInfo') || '{}'))

// 当前时间
const currentDateTime = ref('')
let timeInterval = null

const updateDateTime = () => {
  const now = new Date()
  currentDateTime.value = now.toLocaleString('zh-CN', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    weekday: 'long',
    hour: '2-digit',
    minute: '2-digit',
  })
}

// 统计数据
const stats = reactive({
  pendingQuotes: 0,
  activePlans: 0,
  todayInspections: 0,
  lowStockItems: 0,
})

// 待办事项
const todos = ref([
  { id: 1, title: '审批报价单 Q-20250613-001', priority: 'high', done: false },
  { id: 2, title: '完成零件首件检验', priority: 'medium', done: false },
  { id: 3, title: '更新生产计划', priority: 'low', done: true },
])

// 最新动态
const activities = ref([
  {
    id: 1,
    title: '报价单已审批',
    description: '报价单 Q-20250612-001 已通过老板审批',
    type: 'success',
    time: '10:30',
  },
  {
    id: 2,
    title: '生产计划已开始',
    description: '零件 PRT-001 开始生产',
    type: 'primary',
    time: '09:15',
  },
  {
    id: 3,
    title: '来料检验完成',
    description: '批次 B-20250612-001 检验合格',
    type: 'success',
    time: '08:45',
  },
])

// 机台状态
const machineStatuses = reactive([
  { key: 'running', label: '运行中', count: 5, color: '#67C23A' },
  { key: 'idle', label: '空闲', count: 2, color: '#409EFF' },
  { key: 'fault', label: '故障', count: 1, color: '#F56C6C' },
  { key: 'repairing', label: '维修中', count: 1, color: '#E6A23C' },
  { key: 'offline', label: '离线', count: 0, color: '#909399' },
])

// 优先级
const getPriorityType = (priority) => {
  const map = { high: 'danger', medium: 'warning', low: 'info' }
  return map[priority] || 'info'
}

const getPriorityText = (priority) => {
  const map = { high: '紧急', medium: '普通', low: '低' }
  return map[priority] || priority
}

// 动态类型
const getActivityType = (type) => {
  const map = { success: 'success', primary: 'primary', warning: 'warning', danger: 'danger' }
  return map[type] || 'primary'
}

// 处理待办事项状态变更
const handleTodoChange = (todo) => {
  console.log('Todo changed:', todo)
}

// 获取统计数据
const fetchStats = async () => {
  try {
    // 并行获取各项统计
    const [quotesRes, plansRes, inspectionsRes, inventoryRes] = await Promise.allSettled([
      get('/quotes', { status: 'PENDING_BOSS', page_size: 1 }),
      get('/production/plans', { status: 'in_progress', page_size: 1 }),
      get('/quality/inspections/today', {}),
      get('/warehouse/inventory/low-stock', {}),
    ])

    if (quotesRes.status === 'fulfilled') {
      stats.pendingQuotes = quotesRes.value.total || 0
    }
    if (plansRes.status === 'fulfilled') {
      stats.activePlans = plansRes.value.total || 0
    }
  } catch (error) {
    console.error('Failed to fetch stats:', error)
  }
}

// 获取待办事项
const fetchTodos = async () => {
  // 实际应该从 API 获取
  // 目前使用静态数据
}

// 获取最新动态
const fetchActivities = async () => {
  // 实际应该从 API 获取
  // 目前使用静态数据
}

onMounted(() => {
  updateDateTime()
  timeInterval = setInterval(updateDateTime, 60000)

  // 获取数据
  fetchStats()
  fetchTodos()
  fetchActivities()
})

onUnmounted(() => {
  if (timeInterval) {
    clearInterval(timeInterval)
  }
})
</script>

<style scoped>
.dashboard-container {
  padding: 20px;
}

.welcome-section {
  margin-bottom: 24px;
}

.welcome-section h1 {
  margin: 0 0 8px 0;
  font-size: 28px;
  color: #303133;
}

.welcome-sub {
  color: #909399;
  margin: 0;
}

.stats-row {
  margin-bottom: 20px;
}

.stat-card {
  display: flex;
  align-items: center;
  padding: 20px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
  margin-bottom: 16px;
}

.stat-icon {
  width: 60px;
  height: 60px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 16px;
  font-size: 28px;
  color: white;
}

.stat-quotes .stat-icon {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.stat-production .stat-icon {
  background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
}

.stat-quality .stat-icon {
  background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
}

.stat-warehouse .stat-icon {
  background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%);
}

.stat-content {
  flex: 1;
}

.stat-value {
  font-size: 32px;
  font-weight: bold;
  color: #303133;
  line-height: 1;
}

.stat-label {
  font-size: 14px;
  color: #909399;
  margin-top: 8px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-header span {
  font-size: 16px;
  font-weight: 600;
}

.badge {
  margin-left: 8px;
}

.todo-card,
.activity-card {
  margin-bottom: 20px;
}

.todo-list {
  padding: 8px 0;
}

.todo-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 0;
  border-bottom: 1px solid #f0f0f0;
}

.todo-item:last-child {
  border-bottom: none;
}

.todo-done {
  text-decoration: line-through;
  color: #909399;
}

.activity-desc {
  margin: 8px 0 0 0;
  color: #909399;
  font-size: 14px;
}

.machine-overview {
  margin-top: 20px;
}

.machine-status-item {
  text-align: center;
  padding: 16px 0;
}

.machine-count {
  font-size: 36px;
  font-weight: bold;
}

.machine-label {
  font-size: 14px;
  color: #909399;
  margin-top: 8px;
}
</style>
