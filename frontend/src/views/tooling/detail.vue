<template>
  <div class="tooling-detail-container">
    <el-page-header @back="goBack" title="返回">
      <template #content>
        <span class="page-title">模具详情</span>
      </template>
    </el-page-header>

    <div class="content-wrapper" v-loading="loading">
      <!-- 基本信息 -->
      <el-card class="info-card">
        <template #header>
          <div class="card-header">
            <span class="card-title">基本信息</span>
            <el-tag :type="getStatusType(toolingDetail.status)" size="large">
              {{ getStatusText(toolingDetail.status) }}
            </el-tag>
          </div>
        </template>
        <el-descriptions :column="3" border>
          <el-descriptions-item label="模具号" :span="1">
            <el-text tag="b" size="large">{{ toolingDetail.toolingNo }}</el-text>
          </el-descriptions-item>
          <el-descriptions-item label="客户名称">{{ toolingDetail.customerName }}</el-descriptions-item>
          <el-descriptions-item label="客户产品号">{{ toolingDetail.customerPartNo }}</el-descriptions-item>
          <el-descriptions-item label="模具类型">{{ getTypeText(toolingDetail.type) }}</el-descriptions-item>
          <el-descriptions-item label="穴数">{{ toolingDetail.cavities }}</el-descriptions-item>
          <el-descriptions-item label="吨位">{{ toolingDetail.tonnage }}T</el-descriptions-item>
          <el-descriptions-item label="模具尺寸">{{ toolingDetail.size || '-' }}</el-descriptions-item>
          <el-descriptions-item label="存放位置">{{ toolingDetail.location }}</el-descriptions-item>
          <el-descriptions-item label="入库日期">{{ toolingDetail.createdAt }}</el-descriptions-item>
          <el-descriptions-item label="理论寿命">
            {{ toolingDetail.designedLife ? (toolingDetail.designedLife / 10000).toFixed(0) + '万次' : '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="累计冲次">
            <el-text :type="getShotsColor(toolingDetail.totalShots, toolingDetail.designedLife)">
              {{ formatNumber(toolingDetail.totalShots) }}
            </el-text>
            <el-progress
              :percentage="getLifePercentage(toolingDetail.totalShots, toolingDetail.designedLife)"
              :status="getLifeStatus(toolingDetail.totalShots, toolingDetail.designedLife)"
              style="margin-top: 8px"
            />
          </el-descriptions-item>
          <el-descriptions-item label="维修次数">
            {{ toolingDetail.maintenanceCount || 0 }} 次
          </el-descriptions-item>
          <el-descriptions-item label="备注" :span="3">
            {{ toolingDetail.notes || '-' }}
          </el-descriptions-item>
        </el-descriptions>
      </el-card>

      <!-- 绑定的零件 -->
      <el-card class="parts-card">
        <template #header>
          <div class="card-header">
            <span class="card-title">绑定零件</span>
            <el-button type="primary" size="small" @click="showBindDialog = true">
              绑定零件
            </el-button>
          </div>
        </template>
        <el-table :data="toolingDetail.parts" border stripe>
          <el-table-column prop="partName" label="零件名称" />
          <el-table-column prop="partNo" label="零件号" width="150" />
          <el-table-column prop="status" label="状态" width="100" align="center">
            <template #default="{ row }">
              <el-tag :type="row.status === 'active' ? 'success' : ''">
                {{ row.status === 'active' ? '量产中' : '已停产' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="bindDate" label="绑定时间" width="160" />
          <el-table-column label="操作" width="120" align="center">
            <template #default="{ row }">
              <el-button type="danger" link @click="handleUnbind(row.id)">
                解除绑定
              </el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!toolingDetail.parts?.length" description="暂无绑定零件" />
      </el-card>

      <!-- 使用记录 -->
      <el-card class="usage-card">
        <template #header>
          <span class="card-title">使用记录（最近10条）</span>
        </template>
        <el-timeline>
          <el-timeline-item
            v-for="(record, index) in toolingDetail.usageHistory"
            :key="index"
            :timestamp="record.date"
            placement="top"
          >
            <el-card>
              <div class="usage-record">
                <div>
                  <el-text tag="b">{{ record.partName }}</el-text>
                  <span style="margin: 0 10px">|</span>
                  <span>机台：{{ record.machineName }}</span>
                  <span style="margin: 0 10px">|</span>
                  <span>操作员：{{ record.operatorName }}</span>
                </div>
                <div style="margin-top: 8px">
                  <el-text type="info">
                    生产数量：{{ record.quantity }} | 冲次：{{ formatNumber(record.shots) }}
                  </el-text>
                </div>
              </div>
            </el-card>
          </el-timeline-item>
        </el-timeline>
        <el-empty v-if="!toolingDetail.usageHistory?.length" description="暂无使用记录" />
      </el-card>

      <!-- 维修历史 -->
      <el-card class="maintenance-card">
        <template #header>
          <div class="card-header">
            <span class="card-title">维修历史</span>
            <el-button type="warning" size="small" @click="goToMaintenance">
              报修/维修
            </el-button>
          </div>
        </template>
        <el-table :data="toolingDetail.maintenanceHistory" border stripe>
          <el-table-column prop="reportDate" label="报修日期" width="110" />
          <el-table-column prop="reportBy" label="报修人" width="100" />
          <el-table-column prop="issue" label="故障描述" min-width="200" />
          <el-table-column prop="solution" label="维修方案" min-width="200" />
          <el-table-column prop="maintainedBy" label="维修人" width="100" />
          <el-table-column prop="maintainedAt" label="完成日期" width="110" />
          <el-table-column prop="cost" label="费用" width="100" align="right">
            <template #default="{ row }">
              {{ row.cost ? '¥' + row.cost.toFixed(2) : '-' }}
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!toolingDetail.maintenanceHistory?.length" description="暂无维修记录" />
      </el-card>

      <!-- 操作按钮 -->
      <el-card class="actions-card">
        <el-space wrap>
          <el-button type="primary" @click="goToEdit">编辑信息</el-button>
          <el-button type="warning" @click="goToMaintenance">报修</el-button>
          <el-button
            v-if="toolingDetail.status !== 'scrapped'"
            type="danger"
            @click="handleScrap"
          >
            报废
          </el-button>
        </el-space>
      </el-card>
    </div>

    <!-- 绑定零件对话框 -->
    <el-dialog v-model="showBindDialog" title="绑定零件" width="500px">
      <el-form label-width="100px">
        <el-form-item label="选择零件">
          <el-select v-model="bindPartId" placeholder="请选择零件" filterable style="width: 100%">
            <el-option
              v-for="part in availableParts"
              :key="part.id"
              :label="`${part.partName} (${part.partNo})`"
              :value="part.id"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showBindDialog = false">取消</el-button>
        <el-button type="primary" @click="submitBind">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const showBindDialog = ref(false)
const bindPartId = ref<number | null>(null)

// 模具详情
const toolingDetail = ref<any>({})

// 可用零件列表
const availableParts = ref<any[]>([])

// 加载详情
const loadDetail = async () => {
  loading.value = true
  try {
    const id = route.params.id
    // TODO: 调用 API
    // const response = await api.tooling.detail(id)
    // toolingDetail.value = response.data

    // 模拟数据
    toolingDetail.value = {
      id,
      toolingNo: 'M-2026-001',
      customerName: '客户A',
      customerPartNo: 'PA-001',
      type: 'progressive',
      cavities: 2,
      tonnage: 150,
      size: '400×300×250',
      location: 'A区01',
      status: 'available',
      designedLife: 10000000,
      totalShots: 1500000,
      maintenanceCount: 3,
      createdAt: '2026-01-15',
      notes: '重点模具，需定期保养',
      parts: [
        { id: 1, partName: '冲压件A', partNo: 'P001', status: 'active', bindDate: '2026-01-20' }
      ],
      usageHistory: [
        {
          date: '2026-06-20',
          partName: '冲压件A',
          machineName: '机台1',
          operatorName: '张三',
          quantity: 5000,
          shots: 10000
        }
      ],
      maintenanceHistory: [
        {
          reportDate: '2026-05-15',
          reportBy: '李四',
          issue: '冲头磨损',
          solution: '更换冲头',
          maintainedBy: '王五',
          maintainedAt: '2026-05-16',
          cost: 1200
        }
      ]
    }
  } catch (error) {
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
}

// 加载可用零件
const loadAvailableParts = async () => {
  try {
    // TODO: 调用 API
    availableParts.value = [
      { id: 2, partName: '冲压件B', partNo: 'P002' }
    ]
  } catch (error) {
    ElMessage.error('加载零件列表失败')
  }
}

// 类型和状态
const getTypeText = (type: string) => {
  const typeMap: any = { single: '单工序', progressive: '连续模', compound: '复合模' }
  return typeMap[type] || type
}

const getStatusType = (status: string) => {
  const typeMap: any = { available: 'success', in_use: 'warning', maintenance: 'info', scrapped: 'danger' }
  return typeMap[status] || ''
}

const getStatusText = (status: string) => {
  const textMap: any = { available: '可用', in_use: '使用中', maintenance: '维修中', scrapped: '报废' }
  return textMap[status] || status
}

// 寿命相关
const getLifePercentage = (current: number, designed: number) => {
  if (!designed) return 0
  return Math.min(Math.round((current / designed) * 100), 100)
}

const getLifeStatus = (current: number, designed: number) => {
  const pct = getLifePercentage(current, designed)
  if (pct >= 90) return 'exception'
  if (pct >= 70) return 'warning'
  return 'success'
}

const getShotsColor = (current: number, designed: number) => {
  const pct = getLifePercentage(current, designed)
  if (pct >= 90) return 'danger'
  if (pct >= 70) return 'warning'
  return 'success'
}

// 格式化数字
const formatNumber = (num: number) => {
  return num?.toLocaleString() || '0'
}

// 绑定零件
const submitBind = async () => {
  if (!bindPartId.value) {
    ElMessage.warning('请选择零件')
    return
  }
  try {
    // TODO: 调用 API
    // await api.tooling.bindPart(toolingDetail.value.id, bindPartId.value)
    ElMessage.success('绑定成功')
    showBindDialog.value = false
    loadDetail()
  } catch (error) {
    ElMessage.error('绑定失败')
  }
}

// 解除绑定
const handleUnbind = async (partId: number) => {
  try {
    await ElMessageBox.confirm('确认解除零件绑定吗？', '提示', {
      confirmButtonText: '确认',
      cancelButtonText: '取消',
      type: 'warning'
    })
    // TODO: 调用 API
    // await api.tooling.unbindPart(toolingDetail.value.id, partId)
    ElMessage.success('已解除绑定')
    loadDetail()
  } catch (error) {
    // 用户取消
  }
}

// 报废
const handleScrap = async () => {
  try {
    await ElMessageBox.confirm('确认报废此模具吗？报废后将无法恢复。', '确认报废', {
      confirmButtonText: '确认',
      cancelButtonText: '取消',
      type: 'warning'
    })
    // TODO: 调用 API
    // await api.tooling.scrap(toolingDetail.value.id)
    ElMessage.success('已报废')
    router.back()
  } catch (error) {
    // 用户取消
  }
}

// 导航
const goBack = () => router.back()
const goToEdit = () => ElMessage.info('编辑功能在列表页')
const goToMaintenance = () => router.push(`/tooling/maintenance/${toolingDetail.value.id}`)

onMounted(() => {
  loadDetail()
  loadAvailableParts()
})
</script>

<style scoped lang="scss">
.tooling-detail-container {
  padding: 20px;

  .page-title {
    font-size: 18px;
    font-weight: 500;
  }

  .content-wrapper {
    margin-top: 20px;

    .el-card {
      margin-bottom: 20px;

      .card-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
      }

      .card-title {
        font-size: 16px;
        font-weight: 500;
      }
    }

    .usage-record {
      line-height: 1.6;
    }

    .actions-card {
      .el-space {
        width: 100%;
      }
    }
  }
}
</style>
