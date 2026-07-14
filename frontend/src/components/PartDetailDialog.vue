<template>
  <el-dialog v-model="visible" title="零件详情" width="900px" :close-on-click-modal="false">
    <div v-if="detail" class="detail-container">
      <!-- 基本信息 -->
      <el-card class="section-card" shadow="never">
        <template #header><strong>基本信息</strong></template>
        <el-descriptions :column="2" border>
          <el-descriptions-item label="内部零件ID">{{ detail.id }}</el-descriptions-item>
          <el-descriptions-item label="内部零件名称">{{ detail.internal_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="材料">{{ detail.material_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="statusType(detail.part_status)">{{ statusLabel(detail.part_status) }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="厚度(T)">{{ formatDimension(detail.thickness) }}</el-descriptions-item>
          <el-descriptions-item label="宽度(W)">{{ formatDimension(detail.width) }}</el-descriptions-item>
          <el-descriptions-item label="节距(P)">{{ formatDimension(detail.pitch) }}</el-descriptions-item>
          <el-descriptions-item label="位置">{{ detail.part_position || '-' }}</el-descriptions-item>
          <el-descriptions-item label="毛重">{{ detail.gross_weight ? detail.gross_weight + 'g' : '-' }}</el-descriptions-item>
          <el-descriptions-item label="净重">{{ detail.net_weight ? detail.net_weight + 'g' : '-' }}</el-descriptions-item>
        </el-descriptions>
      </el-card>

      <!-- 关联客户 -->
      <el-card class="section-card" shadow="never">
        <template #header><strong>关联客户 ({{ detail.customer_aliases?.length || 0 }})</strong></template>
        <el-table :data="detail.customer_aliases" stripe max-height="300" v-if="detail.customer_aliases?.length">
          <el-table-column prop="customer_name" label="客户名称" width="160" />
          <el-table-column prop="customer_code" label="客户代号" width="100" />
          <el-table-column prop="customer_part_no" label="客户件号" width="140" />
          <el-table-column prop="customer_part_name" label="客户件名" min-width="140" />
          <el-table-column prop="vehicle_model" label="车型" width="100" />
          <el-table-column prop="revision" label="版本" width="80" />
          <el-table-column prop="is_active" label="有效" width="60" align="center">
            <template #default="{ row }">
              <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
                {{ row.is_active ? '是' : '否' }}
              </el-tag>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-else description="暂无关联客户" :image-size="80" />
      </el-card>

      <!-- 关联模具 -->
      <el-card class="section-card" shadow="never">
        <template #header><strong>关联模具 ({{ detail.tooling?.length || 0 }})</strong></template>
        <div v-if="detail.tooling?.length">
          <el-collapse v-model="activeTooling" accordion>
            <el-collapse-item v-for="t in detail.tooling" :key="t.tooling_id" :name="t.tooling_id">
              <template #title>
                <div class="tooling-title">
                  <el-tag type="primary" size="small" style="margin-right: 8px">{{ t.tooling_number }}</el-tag>
                  <span>{{ t.tooling_name || '未命名' }}</span>
                  <el-tag v-if="t.is_continuous" type="success" size="small" style="margin-left: 8px">连续模</el-tag>
                  <el-tag v-else type="warning" size="small" style="margin-left: 8px">{{ t.mold_type }}</el-tag>
                </div>
              </template>

              <el-descriptions :column="2" border size="small">
                <el-descriptions-item label="模具号">{{ t.tooling_number }}</el-descriptions-item>
                <el-descriptions-item label="模具名称">{{ t.tooling_name || '-' }}</el-descriptions-item>
                <el-descriptions-item label="模具类型">{{ t.mold_type }}</el-descriptions-item>
                <el-descriptions-item label="穴数">{{ t.cavity_count }}</el-descriptions-item>
                <el-descriptions-item label="是否连续模">{{ t.is_continuous ? '是' : '否' }}</el-descriptions-item>
                <el-descriptions-item label="步骤数">
                  {{ t.is_continuous ? '-' : (t.process_step_count || 0) }}
                </el-descriptions-item>
                <el-descriptions-item label="状态">{{ t.status }}</el-descriptions-item>
                <el-descriptions-item label="位置">{{ t.position || '-' }}</el-descriptions-item>
              </el-descriptions>

              <!-- 模具关联客户 -->
              <div v-if="t.tooling_customers && t.tooling_customers.length" style="margin-top: 12px">
                <div style="font-weight: 500; margin-bottom: 8px; color: #606266">模具关联客户：</div>
                <el-tag v-for="(cust, idx) in t.tooling_customers" :key="idx" style="margin-right: 8px; margin-bottom: 4px">
                  {{ cust }}
                </el-tag>
              </div>

              <!-- 非连续模步骤明细 -->
              <div v-if="!t.is_continuous && t.steps && t.steps.length" style="margin-top: 12px">
                <div style="font-weight: 500; margin-bottom: 8px; color: #606266">工序步骤明细：</div>
                <el-table :data="t.steps" size="small" border>
                  <el-table-column prop="step_no" label="步号" width="80" align="center" />
                  <el-table-column prop="step_code" label="步骤代码" width="100" />
                  <el-table-column prop="step_name" label="步骤名称" min-width="120" />
                  <el-table-column prop="operation_type" label="工序类型" width="120" />
                  <el-table-column prop="sequence" label="顺序" width="80" align="center" />
                </el-table>
              </div>
            </el-collapse-item>
          </el-collapse>
        </div>
        <el-empty v-else description="暂无关联模具" :image-size="80" />
      </el-card>
    </div>

    <template #footer>
      <el-button @click="visible = false">关闭</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  modelValue: Boolean,
  detail: Object,
})

const emit = defineEmits(['update:modelValue'])

const visible = ref(props.modelValue)
const activeTooling = ref(null)

const STATUS_MAP = {
  DRAFT: { label: '草稿', type: 'info' },
  SAMPLING: { label: '打样', type: 'warning' },
  MASS_PRODUCTION: { label: '量产', type: 'success' },
  OBSOLETE: { label: '淘汰', type: 'danger' },
}

const statusLabel = s => STATUS_MAP[s]?.label || s
const statusType = s => STATUS_MAP[s]?.type || 'info'

const formatDimension = (value) => {
  // Format dimension value - just show the number without unit
  if (value === null || value === undefined) return '-'
  return String(value)
}

watch(() => props.modelValue, (val) => { visible.value = val })
watch(visible, (val) => { emit('update:modelValue', val) })
</script>

<style scoped>
.detail-container { max-height: 70vh; overflow-y: auto; }
.section-card { margin-bottom: 16px; }
.section-card:last-child { margin-bottom: 0; }
.tooling-title { display: flex; align-items: center; width: 100%; }
</style>
