<template>
  <el-dialog
    v-model="visible"
    title="编辑零件"
    width="95%"
    :close-on-click-modal="false"
    :before-close="handleBeforeClose"
    destroy-on-close
  >
    <div v-if="loading" class="loading-container">
      <el-icon class="is-loading" :size="40"><Loading /></el-icon>
      <p>加载中...</p>
    </div>

    <div v-else-if="editorData" class="editor-container">
      <!-- 基本信息 -->
      <el-card class="section-card" shadow="never">
        <template #header><strong>基本信息</strong></template>
        <el-form :model="baseForm" label-width="120px" size="default">
          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item label="零件编号">
                <el-input v-model="editorData.part_number" disabled />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="内部零件号">
                <el-input v-model="baseForm.internal_part_no" @input="hasUnsavedChanges = true" />
              </el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item label="内部零件名称">
                <el-input v-model="baseForm.internal_name" @input="hasUnsavedChanges = true" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="材料名称">
                <el-input v-model="baseForm.material_name" @input="hasUnsavedChanges = true" />
              </el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item label="零件状态">
                <el-select v-model="baseForm.part_status" @change="hasUnsavedChanges = true" style="width: 100%">
                  <el-option label="草稿" value="DRAFT" />
                  <el-option label="打样" value="SAMPLING" />
                  <el-option label="量产" value="MASS_PRODUCTION" />
                  <el-option label="淘汰" value="OBSOLETE" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="位置">
                <el-select v-model="baseForm.part_position" @change="hasUnsavedChanges = true" style="width: 100%">
                  <el-option label="左" value="left" />
                  <el-option label="右" value="right" />
                  <el-option label="中" value="center" />
                  <el-option label="单件" value="single" />
                  <el-option label="无" value="" />
                </el-select>
              </el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="20">
            <el-col :span="8">
              <el-form-item label="厚度(T)">
                <el-input v-model="baseForm.thickness" @input="hasUnsavedChanges = true" type="number" step="0.001" />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="宽度(W)">
                <el-input v-model="baseForm.width" @input="hasUnsavedChanges = true" type="number" step="0.001" />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="步距(P)">
                <el-input v-model="baseForm.pitch" @input="hasUnsavedChanges = true" type="number" step="0.001" />
              </el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item label="毛重(g)">
                <el-input v-model="baseForm.gross_weight" @input="hasUnsavedChanges = true" type="number" step="0.001" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="净重(g)">
                <el-input v-model="baseForm.net_weight" @input="hasUnsavedChanges = true" type="number" step="0.001" />
              </el-form-item>
            </el-col>
          </el-row>
          <el-form-item label="图纸链接">
            <el-input v-model="baseForm.drawing_url" @input="hasUnsavedChanges = true" />
          </el-form-item>
          <el-form-item label="规格说明">
            <el-input v-model="baseForm.spec_info" @input="hasUnsavedChanges = true" type="textarea" :rows="2" />
          </el-form-item>
          <el-form-item label="备注">
            <el-input v-model="baseForm.remark" @input="hasUnsavedChanges = true" type="textarea" :rows="2" />
          </el-form-item>
        </el-form>
      </el-card>

      <!-- 客户别名 -->
      <el-card class="section-card" shadow="never">
        <template #header>
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <strong>客户别名 ({{ customerAliases.length }})</strong>
            <el-button size="small" type="primary" @click="addCustomerAlias">添加</el-button>
          </div>
        </template>
        <el-table :data="customerAliases" border max-height="300">
          <el-table-column label="客户" width="180">
            <template #default="{ row }">
              <el-select v-model="row.customer_id" @change="hasUnsavedChanges = true" filterable style="width: 100%">
                <el-option
                  v-for="c in customersForSelect"
                  :key="c.id"
                  :value="c.id"
                  :label="c.customer_code ? `${c.customer_code} ${c.name}` : c.name"
                />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="客户件号" width="140">
            <template #default="{ row }">
              <el-input v-model="row.customer_part_no" @input="hasUnsavedChanges = true" size="small" />
            </template>
          </el-table-column>
          <el-table-column label="客户件名" min-width="140">
            <template #default="{ row }">
              <el-input v-model="row.customer_part_name" @input="hasUnsavedChanges = true" size="small" />
            </template>
          </el-table-column>
          <el-table-column label="版本" width="100">
            <template #default="{ row }">
              <el-input v-model="row.revision" @input="hasUnsavedChanges = true" size="small" />
            </template>
          </el-table-column>
          <el-table-column label="车型" width="120">
            <template #default="{ row }">
              <el-input v-model="row.vehicle_model" @input="hasUnsavedChanges = true" size="small" />
            </template>
          </el-table-column>
          <el-table-column label="有效" width="70" align="center">
            <template #default="{ row }">
              <el-checkbox v-model="row.is_active" @change="hasUnsavedChanges = true" />
            </template>
          </el-table-column>
          <el-table-column label="操作" width="80" align="center" fixed="right">
            <template #default="{ $index }">
              <el-button link type="danger" size="small" @click="removeCustomerAlias($index)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!customerAliases.length" description="暂无客户别名" :image-size="60" />
      </el-card>

      <!-- 关联模具 -->
      <el-card class="section-card" shadow="never">
        <template #header>
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <strong>关联模具 ({{ toolingParts.length }})</strong>
            <el-button size="small" type="primary" @click="addTooling">添加</el-button>
          </div>
        </template>
        <div v-if="sortedToolingParts.length">
          <div v-for="(tp, tpIndex) in sortedToolingParts" :key="tpIndex" class="tooling-item">
            <el-card shadow="never" :class="{'tooling-card': true, 'continuous-tooling': getToolingById(tp.tooling_id)?.is_continuous}">
              <el-row :gutter="20">
                <el-col :span="8">
                  <el-form-item label="模具" label-width="60px">
                    <el-select
                      v-model="tp.tooling_id"
                      @change="hasUnsavedChanges = true"
                      filterable
                      style="width: 100%"
                      :disabled="tp.id !== null"
                    >
                      <el-option
                        v-for="t in editorData.available_toolings"
                        :key="t.id"
                        :value="t.id"
                        :label="`${t.tooling_number || '未命名'} - ${t.tooling_name || ''}`"
                      >
                        <span>{{ t.tooling_number || '未命名' }}</span>
                        <el-tag v-if="t.is_continuous" type="success" size="small" style="margin-left: 8px">连续模</el-tag>
                        <el-tag v-else type="info" size="small" style="margin-left: 8px">{{ t.mold_type }}</el-tag>
                      </el-option>
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :span="4">
                  <el-form-item label="位置" label-width="60px">
                    <el-input v-model="tp.position" @input="hasUnsavedChanges = true" size="small" />
                  </el-form-item>
                </el-col>
                <el-col :span="4">
                  <el-form-item label="顺序" label-width="60px">
                    <el-input-number v-model="tp.sequence" @change="hasUnsavedChanges = true" :min="0" size="small" style="width: 100%" />
                  </el-form-item>
                </el-col>
                <el-col :span="4">
                  <el-form-item label="主模" label-width="60px">
                    <el-checkbox
                      :model-value="tp.is_primary"
                      @change="setPrimaryTooling(tpIndex)"
                      :disabled="!canSetPrimary(tp)"
                    />
                    <el-tooltip v-if="hasContinuousTooling && !getToolingById(tp.tooling_id)?.is_continuous" content="存在连续模时，只能设置连续模为主模" placement="top">
                      <el-icon style="margin-left: 4px; color: #909399;"><QuestionFilled /></el-icon>
                    </el-tooltip>
                  </el-form-item>
                </el-col>
                <el-col :span="4" style="text-align: right;">
                  <el-button link type="danger" size="small" @click="removeTooling(tpIndex)">删除模具</el-button>
                </el-col>
              </el-row>

              <!-- TWP 规格 for this tooling -->
              <div v-if="tp.tooling_id" class="twp-section">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                  <strong style="font-size: 13px; color: #606266;">TWP 规格 ({{ getToolingSpecs(tp.tooling_id).length }})</strong>
                  <el-button size="small" @click="addTWPSpec(tp.tooling_id)">添加规格</el-button>
                </div>
                <el-table :data="getToolingSpecs(tp.tooling_id)" border size="small" max-height="200">
                  <el-table-column label="规格字符串" width="140">
                    <template #default="{ row }">
                      <el-input v-model="row.spec_twph" @input="hasUnsavedChanges = true" size="small" />
                    </template>
                  </el-table-column>
                  <el-table-column label="T" width="100">
                    <template #default="{ row }">
                      <el-input v-model="row.thickness" @input="hasUnsavedChanges = true" type="number" step="0.001" size="small" />
                    </template>
                  </el-table-column>
                  <el-table-column label="W" width="100">
                    <template #default="{ row }">
                      <el-input v-model="row.width" @input="hasUnsavedChanges = true" type="number" step="0.001" size="small" />
                    </template>
                  </el-table-column>
                  <el-table-column label="P" width="100">
                    <template #default="{ row }">
                      <el-input v-model="row.pitch" @input="hasUnsavedChanges = true" type="number" step="0.001" size="small" />
                    </template>
                  </el-table-column>
                  <el-table-column label="Excel来源" min-width="180">
                    <template #default="{ row }">
                      <span v-if="row.source_sheet" class="source-info">
                        {{ row.source_sheet }}<span v-if="row.source_row"> / 第{{ row.source_row }}行</span>
                      </span>
                      <span v-else class="text-muted">新建</span>
                    </template>
                  </el-table-column>
                  <el-table-column label="主规格" width="80" align="center">
                    <template #default="{ row, $index }">
                      <el-radio
                        :model-value="row.is_primary"
                        @change="setPrimaryTWP(tp.tooling_id, twpSpecs.findIndex(s => s === row))"
                        :label="true"
                      />
                    </template>
                  </el-table-column>
                  <el-table-column label="操作" width="80" align="center" fixed="right">
                    <template #default="{ row }">
                      <el-button link type="danger" size="small" @click="removeTWPSpec(twpSpecs.findIndex(s => s === row))">删除</el-button>
                    </template>
                  </el-table-column>
                </el-table>
              </div>
            </el-card>
          </div>
        </div>
        <el-empty v-else description="暂无关联模具" :image-size="60" />
      </el-card>
    </div>

    <template #footer>
      <el-button @click="handleCancel">取消</el-button>
      <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
      <el-button v-if="hasUnsavedChanges" @click="handleReload">重新加载</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Loading, QuestionFilled } from '@element-plus/icons-vue'
import { get } from '@/utils/request'
import apiClient from '@/utils/request'

const props = defineProps({
  modelValue: Boolean,
  partId: Number,
})

const emit = defineEmits(['update:modelValue', 'saved'])

const visible = ref(false)
const loading = ref(false)
const saving = ref(false)
const editorData = ref(null)
const originalData = ref(null)
const hasUnsavedChanges = ref(false)

// Form data structures
const baseForm = ref({})
const customerAliases = ref([])
const toolingParts = ref([])
const twpSpecs = ref([])
const deletedAliasIds = ref([])
const deletedToolingPartIds = ref([])
const deletedSpecIds = ref([])

// UI state
const customersForSelect = ref([])
const materialsForSelect = ref([])

watch(() => props.modelValue, async (val) => {
  visible.value = val
  if (val && props.partId) {
    await loadEditorData()
  }
})

watch(visible, (val) => {
  if (!val) {
    emit('update:modelValue', false)
  }
})

const loadEditorData = async () => {
  if (!props.partId) return
  loading.value = true
  try {
    const data = await get(`/parts/${props.partId}/editor/detail`)
    editorData.value = data
    originalData.value = JSON.parse(JSON.stringify(data))

    // Initialize base form
    baseForm.value = {
      internal_part_no: data.internal_part_no,
      internal_name: data.internal_name,
      customer_product_no: data.customer_product_no,
      customer_product_name: data.customer_product_name,
      vehicle_model: data.vehicle_model,
      material_name: data.material_name,
      material_id: data.material_id,
      drawing_url: data.drawing_url,
      spec_info: data.spec_info,
      spec_twph: data.spec_twph,
      thickness: data.thickness,
      width: data.width,
      pitch: data.pitch,
      height: data.height,
      gross_weight: data.gross_weight,
      net_weight: data.net_weight,
      part_position: data.part_position,
      part_status: data.part_status,
      status: data.status,
      remark: data.remark,
      press_tonnage: data.press_tonnage,
      ppap_no: data.ppap_no,
    }

    // Initialize relationships
    customerAliases.value = data.customer_aliases.map(a => ({ ...a }))
    toolingParts.value = data.tooling_associations.map(tp => ({ ...tp }))
    twpSpecs.value = data.twp_specs.map(s => ({ ...s }))

    // Reset deletion trackers
    deletedAliasIds.value = []
    deletedToolingPartIds.value = []
    deletedSpecIds.value = []
    hasUnsavedChanges.value = false

    await loadCustomers()
  } catch (e) {
    ElMessage.error('加载失败: ' + (e.message || '未知错误'))
  } finally {
    loading.value = false
  }
}

const loadCustomers = async () => {
  try {
    const data = await get('/customers', { limit: 200 })
    customersForSelect.value = data.items || []
  } catch (e) {
    // Silent fail
  }
}

const handleSave = async () => {
  saving.value = true
  try {
    // Update base fields
    const baseUpdatePayload = {
      ...baseForm.value,
      updated_at: editorData.value.updated_at,
    }
    await apiClient.patch(`/parts/${props.partId}/editor`, baseUpdatePayload)

    // Update relationships via bulk endpoint
    const bulkPayload = {
      expected_updated_at: editorData.value.updated_at,
      customer_aliases: customerAliases.value.map(a => ({
        id: a.id || null,
        customer_id: a.customer_id,
        customer_part_no: a.customer_part_no || '',
        customer_part_name: a.customer_part_name || null,
        revision: a.revision || '',
        vehicle_model: a.vehicle_model || null,
        remark: a.remark || null,
        is_active: a.is_active !== false,
      })),
      delete_alias_ids: deletedAliasIds.value,
      tooling_parts: toolingParts.value.map(tp => ({
        id: tp.id || null,
        tooling_id: tp.tooling_id,
        position: tp.position || null,
        sequence: tp.sequence || 0,
        is_primary: tp.is_primary || false,
      })),
      delete_tooling_part_ids: deletedToolingPartIds.value,
      twp_specs: twpSpecs.value.map(s => ({
        id: s.id || null,
        tooling_id: s.tooling_id,
        spec_twph: s.spec_twph || null,
        thickness: s.thickness || null,
        width: s.width || null,
        pitch: s.pitch || null,
        is_primary: s.is_primary || false,
      })),
      delete_spec_ids: deletedSpecIds.value,
    }

    await apiClient.put(`/parts/${props.partId}/editor/bulk`, bulkPayload)

    ElMessage.success('保存成功')
    hasUnsavedChanges.value = false
    emit('saved')
    visible.value = false
  } catch (e) {
    if (e.response?.status === 409) {
      ElMessageBox.confirm(
        '该零件已被其他用户修改。请重新加载最新数据后再保存。',
        '冲突',
        {
          confirmButtonText: '重新加载',
          cancelButtonText: '取消',
          type: 'warning',
        }
      ).then(() => {
        handleReload()
      }).catch(() => {})
    } else {
      ElMessage.error('保存失败: ' + (e.message || '未知错误'))
    }
  } finally {
    saving.value = false
  }
}

const handleReload = async () => {
  await loadEditorData()
  ElMessage.success('已重新加载最新数据')
}

const handleCancel = () => {
  if (hasUnsavedChanges.value) {
    ElMessageBox.confirm('有未保存的更改，确认关闭？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    }).then(() => {
      visible.value = false
    }).catch(() => {})
  } else {
    visible.value = false
  }
}

const handleBeforeClose = (done) => {
  if (hasUnsavedChanges.value) {
    ElMessageBox.confirm('有未保存的更改，确认关闭？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    }).then(() => {
      done()
    }).catch(() => {})
  } else {
    done()
  }
}

// Customer alias management
const addCustomerAlias = () => {
  customerAliases.value.push({
    id: null,
    customer_id: null,
    customer_part_no: '',
    customer_part_name: null,
    revision: '',
    vehicle_model: null,
    remark: null,
    is_active: true,
  })
  hasUnsavedChanges.value = true
}

const removeCustomerAlias = (index) => {
  const alias = customerAliases.value[index]
  if (alias.id) {
    deletedAliasIds.value.push(alias.id)
  }
  customerAliases.value.splice(index, 1)
  hasUnsavedChanges.value = true
}

// Tooling association management
const addTooling = () => {
  toolingParts.value.push({
    id: null,
    tooling_id: null,
    position: null,
    sequence: toolingParts.value.length,
    is_primary: false,
  })
  hasUnsavedChanges.value = true
}

const removeTooling = (index) => {
  const tp = toolingParts.value[index]
  if (tp.id) {
    deletedToolingPartIds.value.push(tp.id)
    // Also remove associated TWP specs
    const specsToRemove = twpSpecs.value.filter(s => s.tooling_id === tp.tooling_id)
    specsToRemove.forEach(s => {
      if (s.id) deletedSpecIds.value.push(s.id)
    })
    twpSpecs.value = twpSpecs.value.filter(s => s.tooling_id !== tp.tooling_id)
  }
  toolingParts.value.splice(index, 1)
  hasUnsavedChanges.value = true
}

const setPrimaryTooling = (index) => {
  toolingParts.value.forEach((tp, i) => {
    tp.is_primary = i === index
  })
  hasUnsavedChanges.value = true
}

// TWP spec management
const addTWPSpec = (toolingId) => {
  twpSpecs.value.push({
    id: null,
    tooling_id: toolingId,
    spec_twph: null,
    thickness: null,
    width: null,
    pitch: null,
    is_primary: false,
  })
  hasUnsavedChanges.value = true
}

const removeTWPSpec = (index) => {
  const spec = twpSpecs.value[index]
  if (spec.id) {
    deletedSpecIds.value.push(spec.id)
  }
  twpSpecs.value.splice(index, 1)
  hasUnsavedChanges.value = true
}

const setPrimaryTWP = (toolingId, index) => {
  twpSpecs.value.forEach((spec, i) => {
    if (spec.tooling_id === toolingId) {
      spec.is_primary = i === index
    }
  })
  hasUnsavedChanges.value = true
}

const getToolingById = (toolingId) => {
  return editorData.value?.available_toolings?.find(t => t.id === toolingId)
}

const getToolingSpecs = (toolingId) => {
  return twpSpecs.value.filter(s => s.tooling_id === toolingId)
}

const sortedToolingParts = computed(() => {
  return [...toolingParts.value].sort((a, b) => {
    const toolingA = getToolingById(a.tooling_id)
    const toolingB = getToolingById(b.tooling_id)
    if (toolingA?.is_continuous && !toolingB?.is_continuous) return -1
    if (!toolingA?.is_continuous && toolingB?.is_continuous) return 1
    return (a.sequence || 0) - (b.sequence || 0)
  })
})

const hasContinuousTooling = computed(() => {
  return toolingParts.value.some(tp => {
    const tooling = getToolingById(tp.tooling_id)
    return tooling?.is_continuous
  })
})

const canSetPrimary = (tp) => {
  if (hasContinuousTooling.value) {
    const tooling = getToolingById(tp.tooling_id)
    return tooling?.is_continuous
  }
  return true
}
</script>

<style scoped>
.loading-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 300px;
  color: #909399;
}

.editor-container {
  max-height: 70vh;
  overflow-y: auto;
}

.section-card {
  margin-bottom: 16px;
}

.section-card:last-child {
  margin-bottom: 0;
}

.tooling-item {
  margin-bottom: 12px;
}

.tooling-item:last-child {
  margin-bottom: 0;
}

.tooling-card {
  border: 1px solid #e4e7ed;
}

.continuous-tooling {
  border-color: #67c23a;
  background-color: #f0f9ff;
}

.twp-section {
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid #e4e7ed;
}

.source-info {
  color: #909399;
  font-size: 12px;
}

.text-muted {
  color: #c0c4cc;
}
</style>
