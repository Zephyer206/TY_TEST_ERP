<template>
  <el-drawer v-model="visible" title="零件编辑器" size="85%" :close-on-click-modal="false" destroy-on-close @close="handleClose">
    <div v-if="editorData" class="editor-container">
      <el-tabs v-model="activeTab" type="border-card">
        <!-- 基本信息 -->
        <el-tab-pane label="基本信息" name="basic">
          <el-form :model="form" label-width="110px" class="editor-form">
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="零件编号">
                  <el-input v-model="form.part_number" disabled />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="零件名称">
                  <el-input v-model="form.internal_name" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="20">
              <el-col :span="8">
                <el-form-item label="厚度(T)">
                  <el-input v-model="form.thickness" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="宽度(W)">
                  <el-input v-model="form.width" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="步距(P)">
                  <el-input v-model="form.pitch" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="材料">
                  <el-input v-model="form.material_name" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="位置">
                  <el-select v-model="form.part_position" clearable style="width:100%">
                    <el-option label="左" value="left" />
                    <el-option label="右" value="right" />
                    <el-option label="中" value="center" />
                  </el-select>
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="毛重(g)">
                  <el-input v-model="form.gross_weight" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="净重(g)">
                  <el-input v-model="form.net_weight" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-form-item label="状态">
              <el-select v-model="form.part_status" style="width:100%">
                <el-option label="草稿" value="DRAFT" />
                <el-option label="打样" value="SAMPLING" />
                <el-option label="量产" value="MASS_PRODUCTION" />
                <el-option label="淘汰" value="OBSOLETE" />
              </el-select>
            </el-form-item>
            <el-form-item label="备注">
              <el-input v-model="form.remark" type="textarea" :rows="3" />
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <!-- 客户别名 -->
        <el-tab-pane label="客户别名" name="aliases">
          <div class="tab-toolbar">
            <el-button type="primary" size="small" @click="addAlias">新增别名</el-button>
          </div>
          <el-table :data="form.customer_aliases" border stripe max-height="450">
            <el-table-column label="客户" width="180">
              <template #default="{ row }">
                <el-select v-model="row.customer_id" filterable placeholder="选择客户" style="width:100%">
                  <el-option v-for="c in customers" :key="c.id" :value="c.id"
                    :label="c.customer_code ? `${c.customer_code} ${c.name}` : c.name" />
                </el-select>
              </template>
            </el-table-column>
            <el-table-column label="客户件号" width="150">
              <template #default="{ row }">
                <el-input v-model="row.customer_part_no" size="small" />
              </template>
            </el-table-column>
            <el-table-column label="客户件名" min-width="180">
              <template #default="{ row }">
                <el-input v-model="row.customer_part_name" size="small" />
              </template>
            </el-table-column>
            <el-table-column label="版本" width="100">
              <template #default="{ row }">
                <el-input v-model="row.revision" size="small" />
              </template>
            </el-table-column>
            <el-table-column label="车型" width="120">
              <template #default="{ row }">
                <el-input v-model="row.vehicle_model" size="small" />
              </template>
            </el-table-column>
            <el-table-column label="有效" width="80" align="center">
              <template #default="{ row }">
                <el-checkbox v-model="row.is_active" />
              </template>
            </el-table-column>
            <el-table-column label="操作" width="80" align="center" fixed="right">
              <template #default="{ $index }">
                <el-button link type="danger" size="small" @click="removeAlias($index)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- 模具关联 -->
        <el-tab-pane label="模具关联" name="tooling">
          <div class="tab-toolbar">
            <el-button type="primary" size="small" @click="addToolingAssoc">新增模具</el-button>
          </div>
          <el-table :data="form.tooling_associations" border stripe max-height="450">
            <el-table-column label="模具" width="220">
              <template #default="{ row }">
                <el-select v-model="row.tooling_id" filterable placeholder="选择模具" style="width:100%" :disabled="!!row.id">
                  <el-option v-for="t in availableToolings" :key="t.id" :value="t.id"
                    :label="`${t.tooling_number} - ${t.tooling_name || '未命名'}`" />
                </el-select>
              </template>
            </el-table-column>
            <el-table-column label="位置" width="120">
              <template #default="{ row }">
                <el-select v-model="row.position" clearable size="small" style="width:100%">
                  <el-option label="左" value="left" />
                  <el-option label="右" value="right" />
                  <el-option label="中" value="center" />
                </el-select>
              </template>
            </el-table-column>
            <el-table-column label="顺序" width="100">
              <template #default="{ row }">
                <el-input-number v-model="row.sequence" :min="0" size="small" controls-position="right" style="width:100%" />
              </template>
            </el-table-column>
            <el-table-column label="主模" width="80" align="center">
              <template #default="{ row }">
                <el-checkbox v-model="row.is_primary" :disabled="!canSetPrimary(row)" />
              </template>
            </el-table-column>
            <el-table-column label="操作" width="80" align="center" fixed="right">
              <template #default="{ $index }">
                <el-button link type="danger" size="small" @click="removeToolingAssoc($index)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- TWP规格 -->
        <el-tab-pane label="TWP规格" name="twp">
          <div class="tab-toolbar">
            <el-button type="primary" size="small" @click="addTwpSpec">新增规格</el-button>
          </div>
          <div v-for="group in twpSpecsByTooling" :key="group.tooling_id" class="twp-group">
            <div class="twp-group-header">
              <strong>模具：{{ group.tooling_number }}</strong>
            </div>
            <el-table :data="group.specs" border stripe size="small">
              <el-table-column label="规格字符串" width="150">
                <template #default="{ row }">
                  <el-input v-model="row.spec_twph" size="small" placeholder="如: 1.0*100*50" />
                </template>
              </el-table-column>
              <el-table-column label="厚度(T)" width="110">
                <template #default="{ row }">
                  <el-input v-model="row.thickness" size="small" />
                </template>
              </el-table-column>
              <el-table-column label="宽度(W)" width="110">
                <template #default="{ row }">
                  <el-input v-model="row.width" size="small" />
                </template>
              </el-table-column>
              <el-table-column label="步距(P)" width="110">
                <template #default="{ row }">
                  <el-input v-model="row.pitch" size="small" />
                </template>
              </el-table-column>
              <el-table-column label="Excel来源" width="200">
                <template #default="{ row }">
                  <span v-if="row.source_sheet" class="text-muted">
                    {{ row.source_sheet }}<span v-if="row.source_row"> / 第{{ row.source_row }}行</span>
                  </span>
                  <span v-else class="text-muted">手动创建</span>
                </template>
              </el-table-column>
              <el-table-column label="主规格" width="100" align="center">
                <template #default="{ row }">
                  <el-radio :model-value="row.is_primary" :label="true" @change="setPrimarySpec(group.tooling_id, row._index)">
                    <span></span>
                  </el-radio>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="80" align="center" fixed="right">
                <template #default="{ row }">
                  <el-button link type="danger" size="small" @click="removeTwpSpec(row._index)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
          <el-empty v-if="!twpSpecsByTooling.length" description="暂无规格，请先添加模具关联" :image-size="100" />
        </el-tab-pane>
      </el-tabs>
    </div>
    <template #footer>
      <div class="drawer-footer">
        <el-button @click="visible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveEditor">保存所有更改</el-button>
      </div>
    </template>
  </el-drawer>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import apiClient from '@/utils/request'

const props = defineProps({
  modelValue: Boolean,
  partId: Number,
  customers: Array,
})

const emit = defineEmits(['update:modelValue', 'saved'])

const visible = ref(props.modelValue)
const editorData = ref(null)
const activeTab = ref('basic')
const saving = ref(false)
const availableToolings = ref([])

const form = reactive({
  part_number: '',
  internal_name: '',
  thickness: null,
  width: null,
  pitch: null,
  material_name: '',
  part_position: null,
  gross_weight: null,
  net_weight: null,
  part_status: 'DRAFT',
  remark: '',
  updated_at: '',
  customer_aliases: [],
  tooling_associations: [],
  twp_specs: [],
})

const twpSpecsByTooling = computed(() => {
  const groups = {}
  form.twp_specs.forEach((spec, index) => {
    if (!groups[spec.tooling_id]) {
      const tooling = availableToolings.value.find(t => t.id === spec.tooling_id)
      groups[spec.tooling_id] = {
        tooling_id: spec.tooling_id,
        tooling_number: tooling?.tooling_number || `ID:${spec.tooling_id}`,
        specs: []
      }
    }
    groups[spec.tooling_id].specs.push({ ...spec, _index: index })
  })
  return Object.values(groups)
})

const canSetPrimary = (row) => {
  const hasContinuous = form.tooling_associations.some(t => {
    const tooling = availableToolings.value.find(tool => tool.id === t.tooling_id)
    return tooling?.is_continuous
  })
  if (!hasContinuous) return true
  const tooling = availableToolings.value.find(t => t.id === row.tooling_id)
  return tooling?.is_continuous || false
}

const loadEditorData = async () => {
  if (!props.partId) return
  try {
    const { get } = await import('@/utils/request')
    const detail = await get(`/parts/${props.partId}/editor/detail`)
    editorData.value = detail

    Object.assign(form, {
      part_number: detail.part_number || '',
      internal_name: detail.internal_name || '',
      thickness: detail.thickness,
      width: detail.width,
      pitch: detail.pitch,
      material_name: detail.material_name || '',
      part_position: detail.part_position,
      gross_weight: detail.gross_weight,
      net_weight: detail.net_weight,
      part_status: detail.part_status || 'DRAFT',
      remark: detail.remark || '',
      updated_at: detail.updated_at,
      customer_aliases: (detail.customer_aliases || []).map(a => ({
        id: a.id,
        customer_id: a.customer_id,
        customer_part_no: a.customer_part_no || '',
        customer_part_name: a.customer_part_name || '',
        revision: a.revision || '',
        vehicle_model: a.vehicle_model || '',
        remark: a.remark || '',
        is_active: a.is_active !== false,
      })),
      tooling_associations: (detail.tooling_associations || []).map(t => ({
        id: t.id,
        tooling_id: t.tooling_id,
        position: t.position,
        sequence: t.sequence || 0,
        is_primary: t.is_primary || false,
      })),
      twp_specs: (detail.twp_specs || []).map(s => ({
        id: s.id,
        tooling_id: s.tooling_id,
        spec_twph: s.spec_twph || '',
        thickness: s.thickness,
        width: s.width,
        pitch: s.pitch,
        is_primary: s.is_primary || false,
        source_sheet: s.source_sheet,
        source_row: s.source_row,
        source_note: s.source_note,
      })),
    })

    availableToolings.value = detail.available_toolings || []
    activeTab.value = 'basic'
  } catch (e) {
    ElMessage.error('加载编辑器失败: ' + (e.message || '未知错误'))
  }
}

const addAlias = () => {
  form.customer_aliases.push({
    id: null,
    customer_id: null,
    customer_part_no: '',
    customer_part_name: '',
    revision: '',
    vehicle_model: '',
    remark: '',
    is_active: true,
  })
}

const removeAlias = (index) => {
  form.customer_aliases.splice(index, 1)
}

const addToolingAssoc = () => {
  form.tooling_associations.push({
    id: null,
    tooling_id: null,
    position: null,
    sequence: 0,
    is_primary: false,
  })
}

const removeToolingAssoc = (index) => {
  const removed = form.tooling_associations[index]
  form.tooling_associations.splice(index, 1)
  if (removed.tooling_id) {
    form.twp_specs = form.twp_specs.filter(s => s.tooling_id !== removed.tooling_id)
  }
}

const addTwpSpec = () => {
  if (form.tooling_associations.length === 0) {
    ElMessage.warning('请先添加模具关联')
    return
  }
  const firstToolingId = form.tooling_associations[0].tooling_id
  form.twp_specs.push({
    id: null,
    tooling_id: firstToolingId,
    spec_twph: '',
    thickness: null,
    width: null,
    pitch: null,
    is_primary: false,
    source_sheet: null,
    source_row: null,
    source_note: null,
  })
}

const removeTwpSpec = (index) => {
  form.twp_specs.splice(index, 1)
}

const setPrimarySpec = (toolingId, specIndex) => {
  form.twp_specs.forEach((spec, idx) => {
    if (spec.tooling_id === toolingId) {
      spec.is_primary = idx === specIndex
    }
  })
}

const saveEditor = async () => {
  if (!editorData.value?.id) return

  try {
    saving.value = true

    const payload = {
      expected_updated_at: form.updated_at,
      base_fields: {
        internal_name: form.internal_name || null,
        thickness: form.thickness ? String(form.thickness) : null,
        width: form.width ? String(form.width) : null,
        pitch: form.pitch ? String(form.pitch) : null,
        material_name: form.material_name || null,
        part_position: form.part_position || null,
        gross_weight: form.gross_weight ? String(form.gross_weight) : null,
        net_weight: form.net_weight ? String(form.net_weight) : null,
        part_status: form.part_status,
        remark: form.remark || null,
      },
      customer_aliases: form.customer_aliases.filter(a => a.customer_id && a.customer_part_no).map(a => ({
        id: a.id || null,
        customer_id: a.customer_id,
        customer_part_no: a.customer_part_no,
        customer_part_name: a.customer_part_name || null,
        revision: a.revision || '',
        vehicle_model: a.vehicle_model || null,
        remark: a.remark || null,
        is_active: a.is_active !== false,
      })),
      delete_alias_ids: (editorData.value.customer_aliases || [])
        .filter(orig => !form.customer_aliases.some(curr => curr.id === orig.id))
        .map(a => a.id),
      tooling_parts: form.tooling_associations.filter(t => t.tooling_id).map(t => ({
        id: t.id || null,
        tooling_id: t.tooling_id,
        position: t.position || null,
        sequence: t.sequence || 0,
        is_primary: t.is_primary || false,
      })),
      delete_tooling_part_ids: (editorData.value.tooling_associations || [])
        .filter(orig => !form.tooling_associations.some(curr => curr.id === orig.id))
        .map(t => t.id),
      twp_specs: form.twp_specs.filter(s => s.tooling_id).map(s => ({
        id: s.id || null,
        tooling_id: s.tooling_id,
        spec_twph: s.spec_twph || null,
        thickness: s.thickness ? String(s.thickness) : null,
        width: s.width ? String(s.width) : null,
        pitch: s.pitch ? String(s.pitch) : null,
        is_primary: s.is_primary || false,
      })),
      delete_spec_ids: (editorData.value.twp_specs || [])
        .filter(orig => !form.twp_specs.some(curr => curr.id === orig.id))
        .map(s => s.id),
    }

    await apiClient.put(`/parts/${editorData.value.id}/editor/bulk`, payload)
    ElMessage.success('保存成功')
    visible.value = false
    emit('saved')
  } catch (e) {
    if (e.response?.status === 409) {
      ElMessageBox.confirm(
        '该零件已被其他用户修改，请刷新后重试。是否立即刷新？',
        '数据冲突',
        { type: 'warning' }
      ).then(async () => {
        await loadEditorData()
      }).catch(() => {})
    } else {
      ElMessage.error('保存失败: ' + (e.message || '未知错误'))
    }
  } finally {
    saving.value = false
  }
}

const handleClose = () => {
  emit('update:modelValue', false)
}

watch(() => props.modelValue, (val) => {
  visible.value = val
  if (val && props.partId) {
    loadEditorData()
  }
})

watch(visible, (val) => {
  emit('update:modelValue', val)
})
</script>

<style scoped>
.editor-container { padding: 0; }
.editor-form { padding: 20px; }
.tab-toolbar {
  padding: 12px 16px;
  border-bottom: 1px solid #ebeef5;
  background: #fafafa;
  margin-bottom: 16px;
}
.twp-group {
  margin-bottom: 20px;
  border: 1px solid #ebeef5;
  border-radius: 4px;
  overflow: hidden;
}
.twp-group-header {
  padding: 12px 16px;
  background: #f5f7fa;
  border-bottom: 1px solid #ebeef5;
}
.drawer-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 16px;
  border-top: 1px solid #ebeef5;
}
.text-muted { color: #909399; }
:deep(.el-drawer__body) {
  padding: 0;
  display: flex;
  flex-direction: column;
}
:deep(.el-tabs--border-card) {
  flex: 1;
  display: flex;
  flex-direction: column;
  border: none;
  box-shadow: none;
}
:deep(.el-tabs__content) {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}
</style>
