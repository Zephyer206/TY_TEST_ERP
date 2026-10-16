<template>
  <el-dialog v-model="visible" title="零件详情" width="900px" :close-on-click-modal="false">
    <div v-if="detail" class="detail-container">
      <!-- 零件实物图与图纸 -->
      <el-card class="section-card media-card" shadow="never">
        <template #header><strong>实物图与图纸</strong></template>
        <div class="media-content">
          <div class="part-image-panel">
            <div class="media-label">实物图</div>
            <el-image
              v-if="detail.drawing_url"
              class="part-image"
              :src="detail.drawing_url"
              :preview-src-list="[detail.drawing_url]"
              fit="contain"
              preview-teleported
            >
              <template #error>
                <div class="media-placeholder">图片加载失败</div>
              </template>
            </el-image>
            <div v-else class="media-placeholder">暂无实物图</div>
          </div>

          <div class="drawing-panel">
            <div class="media-label">图纸</div>
            <el-link
              v-if="detail.drawing_url"
              :href="detail.drawing_url"
              target="_blank"
              rel="noopener noreferrer"
              type="primary"
            >
              打开图纸
            </el-link>
            <span v-else class="text-muted">暂无图纸链接</span>
          </div>
        </div>
      </el-card>

      <!-- 基本信息 -->
      <el-card class="section-card" shadow="never">
        <template #header><strong>基本信息</strong></template>
        <el-descriptions :column="2" border>
          <el-descriptions-item label="零件编号">{{ detail.part_number || detail.internal_part_no || '-' }}</el-descriptions-item>
          <el-descriptions-item label="零件名称">{{ detail.internal_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="材料">{{ detail.material_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="statusType(detail.part_status)">{{ statusLabel(detail.part_status) }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="厚度(T)">{{ formatDimension(detail.thickness) }}</el-descriptions-item>
          <el-descriptions-item label="宽度(W)">{{ formatDimension(detail.width) }}</el-descriptions-item>
          <el-descriptions-item label="步距(P)">{{ formatDimension(detail.pitch) }}</el-descriptions-item>
          <el-descriptions-item label="位置">{{ detail.part_position || '-' }}</el-descriptions-item>
          <el-descriptions-item label="毛重">{{ detail.gross_weight ? detail.gross_weight + 'g' : '-' }}</el-descriptions-item>
          <el-descriptions-item label="净重">{{ detail.net_weight ? detail.net_weight + 'g' : '-' }}</el-descriptions-item>
        </el-descriptions>
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
                  <el-tag v-if="t.is_primary" type="danger" size="small" style="margin-left: 8px">主模</el-tag>
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
              <div v-if="t.twp_options && t.twp_options.length" class="twp-options-panel">
                <div class="subsection-title">TWP 规格选项</div>
                <el-alert
                  v-if="t.twp_options.length > 1 && !hasPrimarySpec(t.twp_options)"
                  title="该模具存在多个 TWP 规格，请选择一个作为主规格"
                  type="warning"
                  :closable="false"
                  show-icon
                  style="margin-bottom: 8px"
                />
                <el-table :data="t.twp_options" size="small" border>
                  <el-table-column label="TWP" min-width="180">
                    <template #default="{ row }">{{ formatSpec(row) || '暂无记录' }}</template>
                  </el-table-column>
                  <el-table-column label="Excel 来源" min-width="170">
                    <template #default="{ row }">
                      {{ row.source_sheet || '-' }}<span v-if="row.source_row"> / 第 {{ row.source_row }} 行</span>
                    </template>
                  </el-table-column>
                  <el-table-column label="状态" width="110" align="center">
                    <template #default="{ row }">
                      <el-tag v-if="row.is_primary" type="success" size="small">主规格</el-tag>
                      <span v-else class="text-muted">未选择</span>
                    </template>
                  </el-table-column>
                  <el-table-column label="操作" width="130" align="center">
                    <template #default="{ row }">
                      <el-button
                        v-if="!row.is_primary"
                        link
                        type="primary"
                        size="small"
                        :loading="settingPrimaryId === row.id"
                        @click="setPrimarySpec(row)"
                      >
                        设为主规格
                      </el-button>
                    </template>
                  </el-table-column>
                </el-table>
              </div>

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

      <el-card v-if="detail.shared_tooling_relations?.length" class="section-card" shadow="never">
        <template #header><strong>共模关联 ({{ detail.shared_tooling_relations.length }})</strong></template>
        <el-table :data="detail.shared_tooling_relations" stripe max-height="320">
          <el-table-column label="模具号" min-width="170">
            <template #default="{ row }">{{ row.tooling_number || '-' }}</template>
          </el-table-column>
          <el-table-column label="共模模具号" min-width="170">
            <template #default="{ row }">{{ row.related_tooling_number || '-' }}</template>
          </el-table-column>
          <el-table-column label="来源" min-width="220">
            <template #default="{ row }">
              {{ row.source_sheet || '-' }}<span v-if="row.source_row"> · 第{{ row.source_row }}行</span>
            </template>
          </el-table-column>
          <el-table-column label="备注" min-width="280">
            <template #default="{ row }">{{ row.source_note || '-' }}</template>
          </el-table-column>
        </el-table>
      </el-card>
    </div>

    <template #footer>
      <el-button type="primary" :disabled="!detail" @click="emit('edit', detail)">编辑零件</el-button>
      <el-button @click="visible = false">关闭</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { partsApi } from '@/api/parts'

const props = defineProps({
  modelValue: Boolean,
  detail: Object,
})

const emit = defineEmits(['update:modelValue', 'primary-spec-updated', 'edit'])

const visible = ref(props.modelValue)
const activeTooling = ref(null)
const settingPrimaryId = ref(null)

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

const formatSpec = (option) => {
  if (option?.spec_twph) return option.spec_twph
  const values = [option?.thickness, option?.width, option?.pitch]
  return values.every(value => value === null || value === undefined || value === '')
    ? ''
    : values.map(value => value === null || value === undefined ? '-' : value).join('*')
}

const hasPrimarySpec = (options) => options?.some(option => option.is_primary)

const setPrimarySpec = async (option) => {
  settingPrimaryId.value = option.id
  try {
    await partsApi.setPrimaryToolingSpec(option.id)
    ElMessage.success('主规格已更新')
    emit('primary-spec-updated', { partId: option.part_id, specId: option.id })
  } catch (error) {
    ElMessage.error(error?.message || '主规格更新失败')
  } finally {
    settingPrimaryId.value = null
  }
}

watch(() => props.modelValue, (val) => { visible.value = val })
watch(visible, (val) => { emit('update:modelValue', val) })
</script>

<style scoped>
.detail-container { max-height: 70vh; overflow-y: auto; }
.section-card { margin-bottom: 16px; }
.section-card:last-child { margin-bottom: 0; }
.tooling-title { display: flex; align-items: center; width: 100%; }
.twp-options-panel { margin-top: 14px; padding: 12px; border: 1px solid #ebeef5; border-radius: 4px; background: #fafcff; }
.subsection-title { margin-bottom: 8px; color: #303133; font-weight: 600; }
.media-content { display: flex; gap: 28px; align-items: flex-start; flex-wrap: wrap; }
.part-image-panel { min-width: 280px; }
.drawing-panel { min-width: 180px; padding-top: 4px; }
.media-label { margin-bottom: 10px; color: #606266; font-weight: 600; }
.part-image,
.media-placeholder {
  width: 280px;
  height: 210px;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  background: #f8fafc;
}
.media-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  color: #909399;
  font-size: 13px;
}
.text-muted { color: #909399; }
</style>
