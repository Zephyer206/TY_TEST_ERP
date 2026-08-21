<template>
  <div class="trace-container">
    <el-card class="header-card">
      <h2>批次追溯</h2>
    </el-card>

    <!-- 扫码输入 -->
    <el-card class="scan-card">
      <el-form :inline="true" :model="scanForm">
        <el-form-item label="扫码/输入">
          <el-input
            v-model="scanForm.code"
            placeholder="批次号或包装号"
            clearable
            style="width: 300px"
            @keyup.enter="handleScan"
          >
            <template #prepend>
          <el-icon><Tickets /></el-icon>
            </template>
          </el-input>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleScan" :loading="loading">
            <el-icon><Search /></el-icon>
            追溯
          </el-button>
          <el-button @click="clearTrace">清除</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 追溯结果 -->
    <div v-if="traceData" class="trace-result" v-loading="loading">
      <!-- 追溯链路 -->
      <el-card class="chain-card">
        <template #header>
          <span class="card-title">追溯链路</span>
        </template>
        <el-steps :active="traceData.steps.length" direction="vertical" finish-status="success">
          <el-step
            v-for="(step, index) in traceData.steps"
            :key="index"
            :title="step.title"
            :description="step.description"
          >
            <template #icon>
              <el-icon v-if="step.type === 'material'"><Box /></el-icon>
              <el-icon v-else-if="step.type === 'batch'"><Tickets /></el-icon>
              <el-icon v-else-if="step.type === 'slitting'"><ScissorIcon /></el-icon>
              <el-icon v-else-if="step.type === 'production'"><Operation /></el-icon>
              <el-icon v-else-if="step.type === 'packaging'"><Box /></el-icon>
            </template>
          </el-step>
        </el-steps>
      </el-card>

      <!-- 追溯树 -->
      <el-card class="tree-card">
        <template #header>
          <span class="card-title">追溯关系树</span>
        </template>
        <el-tree
          :data="traceData.tree"
          :props="{ children: 'children', label: 'label' }"
          default-expand-all
          node-key="id"
        >
          <template #default="{ data }">
            <div class="tree-node">
              <el-tag :type="getNodeType(data.type)" size="small">
                {{ getNodeTypeText(data.type) }}
              </el-tag>
              <span style="margin-left: 10px">{{ data.label }}</span>
              <el-button
                v-if="data.detailUrl"
                type="primary"
                link
                size="small"
                @click="viewDetail(data)"
                style="margin-left: 10px"
              >
                查看详情
              </el-button>
            </div>
          </template>
        </el-tree>
      </el-card>

      <!-- 详细信息 -->
      <el-row :gutter="20">
        <!-- 原材料信息 -->
        <el-col :span="12" v-if="traceData.material">
          <el-card class="info-card">
            <template #header>
              <span class="card-title">原材料信息</span>
            </template>
            <el-descriptions :column="1" border>
              <el-descriptions-item label="物料编码">
                {{ traceData.material.materialCode }}
              </el-descriptions-item>
              <el-descriptions-item label="材质">
                {{ traceData.material.materialName }}
              </el-descriptions-item>
              <el-descriptions-item label="规格">
                {{ traceData.material.specification }}
              </el-descriptions-item>
              <el-descriptions-item label="供应商">
                {{ traceData.material.supplierName }}
              </el-descriptions-item>
            </el-descriptions>
          </el-card>
        </el-col>

        <!-- 批次信息 -->
        <el-col :span="12" v-if="traceData.batch">
          <el-card class="info-card">
            <template #header>
              <span class="card-title">批次信息</span>
            </template>
            <el-descriptions :column="1" border>
              <el-descriptions-item label="批次号">
                <el-text tag="b">{{ traceData.batch.batchNo }}</el-text>
              </el-descriptions-item>
              <el-descriptions-item label="到货日期">
                {{ traceData.batch.arrivalDate }}
              </el-descriptions-item>
              <el-descriptions-item label="数量">
                {{ traceData.batch.quantity }} {{ traceData.material?.unit }}
              </el-descriptions-item>
              <el-descriptions-item label="IQC结果">
                <el-tag :type="traceData.batch.iqcResult === 'qualified' ? 'success' : 'danger'">
                  {{ traceData.batch.iqcResult === 'qualified' ? '合格' : '不合格' }}
                </el-tag>
              </el-descriptions-item>
            </el-descriptions>
          </el-card>
        </el-col>

        <!-- 分条信息 -->
        <el-col :span="12" v-if="traceData.slitting">
          <el-card class="info-card">
            <template #header>
              <span class="card-title">分条信息</span>
            </template>
            <el-descriptions :column="1" border>
              <el-descriptions-item label="分条任务">
                {{ traceData.slitting.taskNo }}
              </el-descriptions-item>
              <el-descriptions-item label="母批次">
                {{ traceData.slitting.parentBatchNo }}
              </el-descriptions-item>
              <el-descriptions-item label="目标宽度">
                {{ traceData.slitting.targetWidth }}mm
              </el-descriptions-item>
              <el-descriptions-item label="子批次数">
                {{ traceData.slitting.childBatchCount }} 个
              </el-descriptions-item>
            </el-descriptions>
          </el-card>
        </el-col>

        <!-- 生产信息 -->
        <el-col :span="12" v-if="traceData.production">
          <el-card class="info-card">
            <template #header>
              <span class="card-title">生产信息</span>
            </template>
            <el-descriptions :column="1" border>
              <el-descriptions-item label="生产计划">
                {{ traceData.production.planNo }}
              </el-descriptions-item>
              <el-descriptions-item label="零件">
                {{ traceData.production.partName }}
              </el-descriptions-item>
              <el-descriptions-item label="机台">
                {{ traceData.production.machineName }}
              </el-descriptions-item>
              <el-descriptions-item label="生产数量">
                {{ traceData.production.quantity }} 个
              </el-descriptions-item>
            </el-descriptions>
          </el-card>
        </el-col>

        <!-- 包装信息 -->
        <el-col :span="12" v-if="traceData.packaging">
          <el-card class="info-card">
            <template #header>
              <span class="card-title">包装信息</span>
            </template>
            <el-descriptions :column="1" border>
              <el-descriptions-item label="包装号">
                <el-text tag="b">{{ traceData.packaging.packagingNo }}</el-text>
              </el-descriptions-item>
              <el-descriptions-item label="包装时间">
                {{ traceData.packaging.packagingTime }}
              </el-descriptions-item>
              <el-descriptions-item label="包装数量">
                {{ traceData.packaging.quantity }} 个
              </el-descriptions-item>
              <el-descriptions-item label="状态">
                <el-tag :type="traceData.packaging.status === 'in_stock' ? 'success' : undefined">
                  {{ traceData.packaging.status === 'in_stock' ? '已入库' : '待入库' }}
                </el-tag>
              </el-descriptions-item>
            </el-descriptions>
          </el-card>
        </el-col>
      </el-row>

      <!-- 质检记录 -->
      <el-card class="qc-card" v-if="traceData.qcRecords?.length">
        <template #header>
          <span class="card-title">质检记录</span>
        </template>
        <el-timeline>
          <el-timeline-item
            v-for="(record, index) in traceData.qcRecords"
            :key="index"
            :timestamp="record.inspectionTime"
            placement="top"
            :type="record.result === 'qualified' ? 'success' : 'danger'"
          >
            <el-card>
              <div class="qc-record">
                <div>
                  <el-tag :type="record.result === 'qualified' ? 'success' : 'danger'">
                    {{ record.type }} - {{ record.result === 'qualified' ? '合格' : '不合格' }}
                  </el-tag>
                  <span style="margin-left: 10px">检验员：{{ record.inspectorName }}</span>
                </div>
                <div style="margin-top: 8px">
                  <el-text type="info">{{ record.comment }}</el-text>
                </div>
              </div>
            </el-card>
          </el-timeline-item>
        </el-timeline>
      </el-card>
    </div>

    <!-- 空状态 -->
    <el-empty v-else description="请扫描批次号或包装号开始追溯" :image-size="200">
      <template #image>
        <el-icon :size="100"><Tickets /></el-icon>
      </template>
    </el-empty>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import { Search, Box, Tickets, Operation } from '@element-plus/icons-vue'

const loading = ref(false)

const scanForm = reactive({
  code: ''
})

const traceData = ref<any>(null)

const handleScan = async () => {
  if (!scanForm.code.trim()) {
    ElMessage.warning('请输入批次号或包装号')
    return
  }

  loading.value = true
  try {
    // TODO: API
    // const response = await api.materials.trace(scanForm.code)
    // traceData.value = response.data

    // 模拟数据
    traceData.value = {
      steps: [
        {
          type: 'material',
          title: '原材料入库',
          description: 'SPCC 1.0×1000mm - 2026-06-15'
        },
        {
          type: 'batch',
          title: '批次 BATCH-2026-06-001',
          description: 'IQC检验合格 - 1000公斤'
        },
        {
          type: 'slitting',
          title: '分条 SLIT-2026-001',
          description: '分条为500mm - 生成5个子批次'
        },
        {
          type: 'production',
          title: '生产 PROD-2026-001',
          description: '冲压件A - 机台1 - 5000个'
        },
        {
          type: 'packaging',
          title: '包装 PKG-2026-001',
          description: '包装数量500个 - 已入库'
        }
      ],
      tree: [
        {
          id: 1,
          type: 'material',
          label: 'MAT-2026-001 SPCC 1.0×1000mm',
          detailUrl: '/materials/1',
          children: [
            {
              id: 2,
              type: 'batch',
              label: 'BATCH-2026-06-001 (母批次)',
              detailUrl: '/materials/batches/1',
              children: [
                {
                  id: 3,
                  type: 'slitting',
                  label: 'SLIT-2026-001 分条任务',
                  children: [
                    {
                      id: 4,
                      type: 'batch',
                      label: 'BATCH-2026-06-001-001 (子批次)',
                      children: [
                        {
                          id: 5,
                          type: 'production',
                          label: 'PROD-2026-001 生产计划',
                          children: [
                            {
                              id: 6,
                              type: 'packaging',
                              label: 'PKG-2026-001 包装',
                              detailUrl: '/packaging/1'
                            }
                          ]
                        }
                      ]
                    }
                  ]
                }
              ]
            }
          ]
        }
      ],
      material: {
        materialCode: 'MAT-2026-001',
        materialName: 'SPCC',
        specification: '1.0×1000mm',
        supplierName: '供应商A',
        unit: '公斤'
      },
      batch: {
        batchNo: 'BATCH-2026-06-001',
        arrivalDate: '2026-06-15',
        quantity: 1000,
        iqcResult: 'qualified'
      },
      slitting: {
        taskNo: 'SLIT-2026-001',
        parentBatchNo: 'BATCH-2026-06-001',
        targetWidth: 500,
        childBatchCount: 5
      },
      production: {
        planNo: 'PROD-2026-001',
        partName: '冲压件A',
        machineName: '机台1',
        quantity: 5000
      },
      packaging: {
        packagingNo: 'PKG-2026-001',
        packagingTime: '2026-06-20 15:00',
        quantity: 500,
        status: 'in_stock'
      },
      qcRecords: [
        {
          type: 'IQC',
          result: 'qualified',
          inspectionTime: '2026-06-15 10:00',
          inspectorName: '王五',
          comment: '来料检验合格'
        },
        {
          type: 'IPQC',
          result: 'qualified',
          inspectionTime: '2026-06-20 11:00',
          inspectorName: '赵六',
          comment: '首检合格'
        }
      ]
    }

    ElMessage.success('追溯成功')
  } catch (error) {
    ElMessage.error('追溯失败')
  } finally {
    loading.value = false
  }
}

const clearTrace = () => {
  scanForm.code = ''
  traceData.value = null
}

const getNodeType = (type: string) => {
  const map: any = {
    material: 'primary',
    batch: 'success',
    slitting: 'warning',
    production: 'info',
    packaging: ''
  }
  return map[type] || ''
}

const getNodeTypeText = (type: string) => {
  const map: any = {
    material: '原材料',
    batch: '批次',
    slitting: '分条',
    production: '生产',
    packaging: '包装'
  }
  return map[type] || type
}

const viewDetail = (data: any) => {
  ElMessage.info(`查看详情：${data.label}`)
}
</script>

<style scoped lang="scss">
.trace-container {
  padding: 20px;

  .header-card {
    margin-bottom: 20px;

    h2 {
      margin: 0;
      font-size: 20px;
      font-weight: 500;
    }
  }

  .scan-card {
    margin-bottom: 20px;
  }

  .trace-result {
    .el-card {
      margin-bottom: 20px;

      .card-title {
        font-size: 16px;
        font-weight: 500;
      }
    }

    .tree-node {
      display: flex;
      align-items: center;
    }

    .qc-record {
      line-height: 1.6;
    }
  }
}
</style>
