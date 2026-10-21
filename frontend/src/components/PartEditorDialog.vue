<template>
  <el-drawer
    v-model="visible"
    title="零件详情与编辑"
    :size="isMobile ? '100%' : 'min(1180px, 96vw)'"
    direction="rtl"
    :close-on-click-modal="false"
    destroy-on-close
    class="part-editor-drawer"
  >
    <el-skeleton v-if="loading" :rows="10" animated />
    <template v-else-if="detail">
      <el-alert
        v-if="conflictMessage"
        class="conflict-alert"
        type="warning"
        :closable="false"
        show-icon
        title="此零件已被其他人更新"
      >
        <template #default>
          {{ conflictMessage }} 本地输入已保留；请重新加载最新版本后检查并再次保存。
          <el-button link type="primary" @click="reloadKeepingDraft">重新加载最新版本并保留本地输入</el-button>
          <el-button link type="info" @click="loadEditor">放弃本地输入并重新加载</el-button>
        </template>
      </el-alert>

      <div class="editor-heading">
        <div>
          <strong>{{ baseForm.internal_name || '未命名零件' }}</strong>
          <div class="editor-subtitle">{{ baseForm.customer_part_no || '零件档案' }} · {{ editing ? '编辑中' : '只读档案' }}</div>
        </div>
        <div class="editor-actions">
          <el-button v-if="!editing" @click="visible = false; router.push({ path: '/ppap', query: { company: 'tianyue', part_id: props.partId } })">查看PPAP</el-button>
          <el-tag :type="editing ? 'warning' : 'success'" effect="plain">{{ editing ? '编辑中' : '只读' }}</el-tag>
          <el-button v-if="!editing" type="primary" @click="startEditing"><el-icon><Edit /></el-icon>编辑</el-button>
          <el-button v-else @click="cancelEditing">放弃修改</el-button>
        </div>
      </div>

      <div class="dossier-layout">
      <el-tabs v-model="activeTab" :tab-position="isMobile ? 'top' : 'left'" class="dossier-tabs" :class="{ 'is-read-only': !editing }">
        <el-tab-pane label="主信息" name="base">
          <el-form label-width="112px" :label-position="isMobile ? 'top' : 'right'" :disabled="!editing" class="editor-form">
            <el-divider content-position="left">业务标识</el-divider>
            <el-row :gutter="18">
              <el-col :span="12"><el-form-item label="零件名称"><el-input v-model="baseForm.internal_name" /></el-form-item></el-col>
              <el-col :span="12"><el-form-item label="客户件号"><el-input v-model="baseForm.customer_part_no" clearable @focus="selectInputText" /></el-form-item></el-col>
              <el-col :span="12"><el-form-item label="车型"><el-input v-model="baseForm.vehicle_model" /></el-form-item></el-col>
            </el-row>

            <el-divider content-position="left">材料与图纸</el-divider>
            <el-row :gutter="18">
              <el-col :span="12"><el-form-item label="材料名称"><el-input v-model="baseForm.material_name" /></el-form-item></el-col>
              <el-col :span="12"><el-form-item label="图纸链接"><el-input v-model="baseForm.drawing_url" /></el-form-item></el-col>
              <el-col :span="12"><el-form-item label="规格说明"><el-input :model-value="detail.spec_info || ''" type="textarea" :rows="2" disabled /></el-form-item></el-col>
            </el-row>

            <el-divider content-position="left">TWP 规格</el-divider>
            <div class="twp-header"><strong>TWP 规格</strong><el-button type="primary" plain size="small" :disabled="!toolingParts.length" @click="addTwpSpec">新增 TWP</el-button></div>
            <el-table :data="twpSpecs" border max-height="300" empty-text="暂无 TWP 规格">
              <el-table-column label="关联模具" min-width="190"><template #default="{ row }"><el-select v-model="row.tooling_id" :disabled="Boolean(row.id)"><el-option v-for="tooling in toolingParts" :key="tooling.tooling_id" :value="tooling.tooling_id" :label="toolingLabel(toolingById(tooling.tooling_id))" /></el-select></template></el-table-column>
              <el-table-column label="规格字符串" min-width="145"><template #default="{ row }"><el-input v-model="row.spec_twph" /></template></el-table-column>
              <el-table-column label="T" width="105"><template #default="{ row }"><el-input v-model="row.thickness" type="number" min="0" step="0.001" /></template></el-table-column>
              <el-table-column label="W" width="105"><template #default="{ row }"><el-input v-model="row.width" type="number" min="0" step="0.001" /></template></el-table-column>
              <el-table-column label="P" width="105"><template #default="{ row }"><el-input v-model="row.pitch" type="number" min="0" step="0.001" /></template></el-table-column>
              <el-table-column label="主规格" width="105" align="center"><template #default="{ row }"><el-button size="small" :type="row.is_primary ? 'primary' : 'default'" @click="setTwpPrimary(row)">{{ row.is_primary ? '主规格' : '设为主规格' }}</el-button></template></el-table-column>
              <el-table-column label="操作" width="72" fixed="right"><template #default="{ $index }"><el-button link type="danger" @click="removeTwpSpec($index)">删除</el-button></template></el-table-column>
            </el-table>

            <el-divider content-position="left">生产与状态</el-divider>
            <el-row :gutter="18">
              <el-col :span="8"><el-form-item label="毛重"><el-input-number v-model="baseForm.gross_weight" :min="0" :precision="3" controls-position="right" /></el-form-item></el-col>
              <el-col :span="8"><el-form-item label="净重"><el-input-number v-model="baseForm.net_weight" :min="0" :precision="3" controls-position="right" /></el-form-item></el-col>
              <el-col :span="8"><el-form-item label="零件位置"><el-select v-model="baseForm.part_position" clearable><el-option label="左" value="left" /><el-option label="右" value="right" /><el-option label="中" value="center" /><el-option label="单件" value="single" /></el-select></el-form-item></el-col>
              <el-col :span="8"><el-form-item label="零件状态"><el-select v-model="baseForm.part_status"><el-option label="草稿" value="DRAFT" /><el-option label="打样" value="SAMPLING" /><el-option label="量产" value="MASS_PRODUCTION" /><el-option label="淘汰" value="OBSOLETE" /></el-select></el-form-item></el-col>
              <el-col :span="8"><el-form-item label="PPAP 编号"><el-input v-model="baseForm.ppap_no" /></el-form-item></el-col>
              <el-col :span="8"><el-form-item label="冲床吨位"><el-input v-model="baseForm.press_tonnage" /></el-form-item></el-col>
              <el-col :span="24"><el-form-item label="备注"><el-input v-model="baseForm.remark" type="textarea" :rows="3" /></el-form-item></el-col>
            </el-row>
          </el-form>
        </el-tab-pane>

        <el-tab-pane label="模具关联" name="tooling">
          <el-alert title="连续模始终优先显示；存在连续模时，非连续模不能设为主模。每套模具可有多条 TWP，但每套模具仅一条主规格。" type="info" :closable="false" show-icon />
          <div class="add-row">
            <el-select v-model="newToolingId" filterable placeholder="选择要关联的模具" class="add-select">
              <el-option v-for="tooling in unlinkedToolings" :key="tooling.id" :value="tooling.id" :label="toolingLabel(tooling)" />
            </el-select>
            <el-button type="primary" plain :disabled="!newToolingId" @click="addTooling">关联模具</el-button>
          </div>
          <el-table :data="toolingParts" border max-height="280">
            <el-table-column label="模具" min-width="240"><template #default="{ row }">{{ toolingLabel(toolingById(row.tooling_id)) }}</template></el-table-column>
            <el-table-column label="类型" width="110"><template #default="{ row }"><el-tag :type="isContinuous(row.tooling_id) ? 'success' : 'warning'">{{ isContinuous(row.tooling_id) ? '连续模' : '简易模' }}</el-tag></template></el-table-column>
            <el-table-column label="位置" width="120"><template #default="{ row }"><el-select v-model="row.position" clearable><el-option label="左" value="left" /><el-option label="右" value="right" /><el-option label="中" value="center" /></el-select></template></el-table-column>
            <el-table-column label="顺序" width="110"><template #default="{ row }"><el-input-number v-model="row.sequence" :min="0" controls-position="right" /></template></el-table-column>
            <el-table-column label="主模" width="100" align="center"><template #default="{ row }"><el-button size="small" :type="row.is_primary ? 'primary' : 'default'" :disabled="hasContinuousTooling && !isContinuous(row.tooling_id)" @click="setToolingPrimary(row)">{{ row.is_primary ? '主模' : '设为主模' }}</el-button></template></el-table-column>
            <el-table-column label="操作" width="80" fixed="right"><template #default="{ $index }"><el-button link type="danger" @click="removeTooling($index)">解除</el-button></template></el-table-column>
          </el-table>
          <el-divider content-position="left">左右件关联</el-divider>
          <div class="pairing-row">
            <template v-if="leftRightGroup">
              <div><strong>已关联</strong><span>{{ groupMembersText(leftRightGroup.members) }}</span><small v-if="leftRightGroup.remark">{{ leftRightGroup.remark }}</small></div>
              <el-button link type="danger" @click="deleteDisplayGroup(leftRightGroup)">解除关联</el-button>
            </template>
            <template v-else>
              <span class="muted">未设置左右件关联</span>
              <el-button type="primary" plain @click="openLeftRightDialog">设置左右件</el-button>
            </template>
          </div>
        </el-tab-pane>

        <el-tab-pane label="修改历史" name="history">
          <el-table :data="changeHistory" v-loading="historyLoading" border empty-text="暂无修改历史">
            <el-table-column prop="created_at" label="时间" width="180" />
            <el-table-column prop="username" label="修改人" width="140" />
            <el-table-column prop="action" label="操作" width="100" />
            <el-table-column prop="summary" label="变更内容" min-width="340" />
          </el-table>
        </el-tab-pane>
      </el-tabs>
      <aside class="change-history-rail" aria-label="修改历史">
        <h3>修改历史</h3>
        <div v-if="changeHistory.length" class="history-preview">
          <div v-for="item in changeHistory.slice(0, 4)" :key="`${item.created_at}-${item.summary}`" class="history-preview-item">
            <strong>{{ item.action }}</strong>
            <span>{{ item.summary }}</span>
            <time>{{ item.created_at }}</time>
          </div>
        </div>
        <p v-else class="muted">暂无修改记录</p>
        <el-button text type="primary" @click="activeTab = 'history'">查看完整历史</el-button>
      </aside>
      </div>
    </template>

    <template #footer>
      <el-button @click="visible = false">关闭</el-button>
      <el-button v-if="!editing" type="primary" :disabled="loading || !detail" @click="startEditing"><el-icon><Edit /></el-icon>编辑</el-button>
      <template v-else>
        <el-button @click="cancelEditing">放弃修改</el-button>
        <el-button type="primary" :loading="saving" :disabled="loading || !detail" @click="saveEditor">保存主信息、模具关联与 TWP</el-button>
      </template>
    </template>
  </el-drawer>

  <el-dialog v-model="groupDialogVisible" title="设置左右件" width="520px" append-to-body>
    <el-form label-width="112px">
      <el-form-item label="当前零件位置"><el-radio-group v-model="displayGroupForm.current_position"><el-radio value="left">左件</el-radio><el-radio value="right">右件</el-radio></el-radio-group></el-form-item>
      <el-form-item label="配对客户件号" required><el-input v-model="displayGroupForm.partner_part_number" /></el-form-item>
      <el-form-item label="备注"><el-input v-model="displayGroupForm.remark" type="textarea" /></el-form-item>
    </el-form>
    <template #footer><el-button @click="groupDialogVisible = false">取消</el-button><el-button type="primary" @click="createDisplayGroup">创建并保存</el-button></template>
  </el-dialog>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Edit } from '@element-plus/icons-vue'
import { useMobileViewport } from '@/composables/useMobileViewport'
import { partsApi, partDisplayGroupsApi } from '@/api/parts'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  partId: { type: [Number, String], default: null },
})
const emit = defineEmits(['update:modelValue', 'saved'])
const isMobile = useMobileViewport()
const router = useRouter()

const visible = ref(false)
const loading = ref(false)
const saving = ref(false)
const activeTab = ref('base')
const editing = ref(false)
const detail = ref(null)
const toolingParts = ref([])
const twpSpecs = ref([])
const deletedToolingPartIds = ref([])
const deletedSpecIds = ref([])
const newToolingId = ref(null)
const conflictMessage = ref('')
const allDisplayGroups = ref([])
const groupDialogVisible = ref(false)
const historyLoading = ref(false)
const changeHistory = ref([])

const baseForm = reactive({})
const displayGroupForm = reactive({ group_key: '', display_name: '', remark: '', current_position: 'left', partner_part_number: '', member_part_numbers: '' })

const BASE_FIELDS = [
  'internal_name', 'customer_part_no', 'vehicle_model',
  'material_name', 'drawing_url',
  'gross_weight', 'net_weight', 'part_position', 'part_status', 'remark',
  'press_tonnage', 'ppap_no',
]
const DECIMAL_FIELDS = new Set(['thickness', 'width', 'pitch', 'height', 'gross_weight', 'net_weight'])
const NUMERIC_BASE_FIELDS = new Set([...DECIMAL_FIELDS])

const toolingContext = computed(() => detail.value?.available_toolings || [])
const toolingById = id => toolingContext.value.find(item => item.id === id)
  || toolingParts.value.find(item => item.tooling_id === id)
  || { id, tooling_number: null, tooling_no: null, tooling_name: '', mold_type: '', is_continuous: false }
const isContinuous = id => Boolean(toolingById(id).is_continuous)
const hasContinuousTooling = computed(() => toolingParts.value.some(item => isContinuous(item.tooling_id)))
const unlinkedToolings = computed(() => toolingContext.value.filter(item => !toolingParts.value.some(link => link.tooling_id === item.id)))
const currentDisplayGroups = computed(() => allDisplayGroups.value.filter(group => group.members?.some(member => member.part_id === Number(props.partId))))
const leftRightGroup = computed(() => currentDisplayGroups.value.find(group => group.group_type === 'left_right' && group.is_active) || null)

const copy = value => JSON.parse(JSON.stringify(value))
const nullableText = value => value === '' || value === undefined ? null : value
const nullableNumber = value => value === '' || value === undefined || value === null ? null : Number(value)
const selectInputText = event => {
  const input = event?.target
  if (input && typeof input.select === 'function') input.select()
}
const toolingLabel = tooling => {
  if (!tooling) return '模具号不可用'
  const number = tooling.tooling_number || tooling.tooling_no || '模具号不可用'
  const name = tooling.tooling_name ? ` · ${tooling.tooling_name}` : ''
  return `${tooling.is_continuous ? '连续模' : (tooling.mold_type || '简易模')} · ${number}${name}`
}
const partMemberLabel = member => [member.customer_part_no, member.part_name].filter(Boolean).join(' · ') || '客户件号不可用'
const groupMembersText = members => (members || []).map(member => `${partMemberLabel(member)}${member.position ? `（${member.position === 'left' ? '左' : member.position === 'right' ? '右' : member.position}）` : ''}`).join('，')
const sortTooling = () => toolingParts.value.sort((left, right) => {
  const continuousOrder = Number(isContinuous(right.tooling_id)) - Number(isContinuous(left.tooling_id))
  return continuousOrder || (left.sequence || 0) - (right.sequence || 0) || left.tooling_id - right.tooling_id
})
const sortSpecs = () => twpSpecs.value.sort((left, right) => left.tooling_id - right.tooling_id || Number(right.is_primary) - Number(left.is_primary) || (left.id || 0) - (right.id || 0))

const applyDetail = response => {
  detail.value = response
  BASE_FIELDS.forEach(field => {
    // The editor contract exposes the internal name as part_name.
    const value = field === 'internal_name' ? response.internal_name ?? response.part_name ?? null : response[field] ?? null
    baseForm[field] = NUMERIC_BASE_FIELDS.has(field) ? nullableNumber(value) : value
  })
  toolingParts.value = response.tooling_associations.map(item => copy(item))
  twpSpecs.value = response.twp_specs.map(item => {
    const spec = copy(item)
    DECIMAL_FIELDS.forEach(field => {
      if (field in spec) spec[field] = nullableNumber(spec[field])
    })
    return spec
  })
  deletedToolingPartIds.value = []
  deletedSpecIds.value = []
  newToolingId.value = null
  sortTooling()
  sortSpecs()
}

const loadGroups = async () => {
  try {
    const displayGroups = await partDisplayGroupsApi.list({ limit: 200 })
    allDisplayGroups.value = displayGroups || []
  } catch (error) {
    ElMessage.error(`获取左右件关联失败：${error.message || '未知错误'}`)
  }
}

const loadHistory = async () => {
  if (!props.partId) return
  historyLoading.value = true
  try {
    changeHistory.value = await partsApi.editorHistory(props.partId)
  } catch (error) {
    ElMessage.error(`获取修改历史失败：${error.message || '未知错误'}`)
  } finally {
    historyLoading.value = false
  }
}

const loadEditor = async () => {
  if (!props.partId) return
  loading.value = true
  editing.value = false
  conflictMessage.value = ''
  try {
    const response = await partsApi.editorDetail(props.partId)
    applyDetail(response)
    void loadGroups()
    void loadHistory()
  } catch (error) {
    ElMessage.error(`获取编辑资料失败：${error.message || '未知错误'}`)
    visible.value = false
  } finally {
    loading.value = false
  }
}

const cancelEditing = async () => {
  await loadEditor()
  editing.value = false
}

const startEditing = async () => {
  if (!detail.value) return
  editing.value = true
  if (toolingContext.value.length) return
  try {
    const response = await partsApi.editorDetail(props.partId, { include_tooling_catalog: true })
    detail.value = { ...detail.value, available_toolings: response.available_toolings || [] }
  } catch (error) {
    ElMessage.error(`获取可选模具失败：${error.message || '未知错误'}`)
  }
}

const editorSnapshot = () => ({ base: copy(baseForm), tooling: copy(toolingParts.value), specs: copy(twpSpecs.value), deletedToolings: [...deletedToolingPartIds.value], deletedSpecs: [...deletedSpecIds.value] })
const reloadKeepingDraft = async () => {
  const draft = editorSnapshot()
  loading.value = true
  try {
    const response = await partsApi.editorDetail(props.partId)
    applyDetail(response)
    Object.assign(baseForm, draft.base)
    toolingParts.value = draft.tooling
    twpSpecs.value = draft.specs
    deletedToolingPartIds.value = draft.deletedToolings
    deletedSpecIds.value = draft.deletedSpecs
    sortTooling()
    sortSpecs()
    void loadGroups()
    void loadHistory()
    conflictMessage.value = ''
    ElMessage.success('已加载最新版本，保留了本地输入；请核对后再次保存')
  } catch (error) {
    ElMessage.error(`重新加载失败：${error.message || '未知错误'}`)
  } finally {
    loading.value = false
  }
}

const addTooling = () => {
  const toolingId = Number(newToolingId.value)
  if (!toolingId || toolingParts.value.some(item => item.tooling_id === toolingId)) return
  const shouldBePrimary = toolingParts.value.length === 0 || (isContinuous(toolingId) && !hasContinuousTooling.value)
  if (shouldBePrimary) toolingParts.value.forEach(item => { item.is_primary = false })
  toolingParts.value.push({ tooling_id: toolingId, position: null, sequence: toolingParts.value.length, is_primary: shouldBePrimary })
  newToolingId.value = null
  sortTooling()
}
const removeTooling = index => {
  const [removed] = toolingParts.value.splice(index, 1)
  if (removed?.id) deletedToolingPartIds.value.push(removed.id)
  twpSpecs.value = twpSpecs.value.filter(spec => {
    if (spec.tooling_id !== removed.tooling_id) return true
    if (spec.id) deletedSpecIds.value.push(spec.id)
    return false
  })
  if (!toolingParts.value.some(item => item.is_primary) && toolingParts.value.length) setToolingPrimary(toolingParts.value[0])
}
const setToolingPrimary = row => {
  if (hasContinuousTooling.value && !isContinuous(row.tooling_id)) {
    ElMessage.warning('存在连续模时，只有连续模可以设为主模')
    return
  }
  toolingParts.value.forEach(item => { item.is_primary = item === row })
}
const addTwpSpec = () => {
  const firstTooling = toolingParts.value[0]
  if (!firstTooling) return
  const alreadyPrimary = twpSpecs.value.some(spec => spec.tooling_id === firstTooling.tooling_id && spec.is_primary)
  twpSpecs.value.push({ tooling_id: firstTooling.tooling_id, spec_twph: null, thickness: null, width: null, pitch: null, is_primary: !alreadyPrimary })
  sortSpecs()
}
const removeTwpSpec = index => {
  const [removed] = twpSpecs.value.splice(index, 1)
  if (removed?.id) deletedSpecIds.value.push(removed.id)
}
const setTwpPrimary = row => {
  twpSpecs.value.forEach(item => { if (item.tooling_id === row.tooling_id) item.is_primary = item === row })
}

const validateDraft = () => {
  const toolingIds = new Set()
  for (const tooling of toolingParts.value) {
    if (!tooling.tooling_id || toolingIds.has(tooling.tooling_id)) return '模具关联必须选择有效且不重复的模具'
    toolingIds.add(tooling.tooling_id)
  }
  const linkedToolingIds = new Set(toolingParts.value.map(item => item.tooling_id))
  for (const spec of twpSpecs.value) {
    if (!linkedToolingIds.has(spec.tooling_id)) return '每条 TWP 必须关联到当前零件已关联的模具'
  }
  if (hasContinuousTooling.value && toolingParts.value.some(item => item.is_primary && !isContinuous(item.tooling_id))) return '存在连续模时，非连续模不能设为主模'
  return null
}
const basePayload = () => Object.fromEntries(BASE_FIELDS.map(field => [field, DECIMAL_FIELDS.has(field) ? nullableNumber(baseForm[field]) : nullableText(baseForm[field])]))
const bulkPayload = () => ({
  expected_updated_at: detail.value.updated_at,
  tooling_parts: toolingParts.value.map(item => ({ id: item.id || undefined, tooling_id: Number(item.tooling_id), position: nullableText(item.position), sequence: Number(item.sequence || 0), is_primary: Boolean(item.is_primary) })),
  delete_tooling_part_ids: [...new Set(deletedToolingPartIds.value)],
  twp_specs: twpSpecs.value.map(item => ({ id: item.id || undefined, tooling_id: Number(item.tooling_id), spec_twph: nullableText(item.spec_twph), thickness: nullableNumber(item.thickness), width: nullableNumber(item.width), pitch: nullableNumber(item.pitch), is_primary: Boolean(item.is_primary) })),
  delete_spec_ids: [...new Set(deletedSpecIds.value)],
})
const serverMessage = data => typeof data?.detail === 'string' ? data.detail : data?.detail?.detail || data?.message || '保存失败'
const handleConflict = data => {
  const detailMessage = typeof data?.detail === 'object' ? data.detail.detail : data?.detail
  conflictMessage.value = detailMessage || '服务器版本与当前编辑版本不一致'
  ElMessage.warning('保存未完成：此零件已被其他人更新')
}
const saveEditor = async () => {
  if (!editing.value) return
  const invalid = validateDraft()
  if (invalid) return ElMessage.warning(invalid)
  saving.value = true
  conflictMessage.value = ''
  try {
    const baseResponse = await partsApi.updateEditorRaw(props.partId, { ...basePayload(), updated_at: detail.value.updated_at })
    if (baseResponse.status === 409) return handleConflict(baseResponse.data)
    if (baseResponse.status >= 400) throw new Error(serverMessage(baseResponse.data))
    detail.value.updated_at = baseResponse.data.updated_at

    const bulkResponse = await partsApi.updateEditorBulkRaw(props.partId, bulkPayload())
    if (bulkResponse.status === 409) return handleConflict(bulkResponse.data)
    if (bulkResponse.status >= 400) throw new Error(serverMessage(bulkResponse.data))
    await loadEditor()
    emit('saved')
    ElMessage.success('零件主信息、模具关联与 TWP 已保存')
  } catch (error) {
    ElMessage.error(error.message || '保存失败')
  } finally {
    saving.value = false
  }
}

const openLeftRightDialog = () => {
  const currentNumber = String(detail.value.customer_part_no || '').trim()
  Object.assign(displayGroupForm, { group_key: `pair:${currentNumber || 'part'}-${Date.now()}`, display_name: '', remark: '', current_position: 'left', partner_part_number: '', member_part_numbers: currentNumber })
  groupDialogVisible.value = true
}
const createDisplayGroup = async () => {
  const key = String(displayGroupForm.group_key || '').trim()
  if (!key) return ElMessage.warning('请填写分组键')
  const partnerNumber = String(displayGroupForm.partner_part_number || '').trim()
  const currentNumber = String(detail.value.customer_part_no || '').trim()
  if (!currentNumber) return ElMessage.warning('当前零件缺少客户件号，无法建立左右件关联')
  if (!partnerNumber || partnerNumber === currentNumber) return ElMessage.warning('请填写另一件零件的客户件号')
  const currentIsLeft = displayGroupForm.current_position === 'left'
  const members = [{ customer_part_no: currentNumber, position: currentIsLeft ? 'left' : 'right', sequence: 0 }, { customer_part_no: partnerNumber, position: currentIsLeft ? 'right' : 'left', sequence: 1 }]
  try {
    await partDisplayGroupsApi.create({ group_type: 'left_right', group_key: key, display_name: null, remark: nullableText(displayGroupForm.remark), members })
    groupDialogVisible.value = false
    await loadGroups()
    emit('saved')
    ElMessage.success('左右件关联已保存')
  } catch (error) { ElMessage.error(error.message || '创建显示分组失败') }
}
const deleteDisplayGroup = async group => {
  try {
    await ElMessageBox.confirm(`删除分组“${group.group_key}”将同时移除其全部成员关系，是否继续？`, '确认删除', { type: 'warning' })
    await partDisplayGroupsApi.remove(group.id)
    await loadGroups()
    emit('saved')
    ElMessage.success('左右件关联已解除')
  } catch (error) { if (error !== 'cancel' && error !== 'close') ElMessage.error(error.message || '删除显示分组失败') }
}

watch(() => props.modelValue, value => {
  visible.value = value
  if (value && props.partId) loadEditor()
})
watch(() => props.partId, value => { if (visible.value && value) loadEditor() })
watch(visible, value => emit('update:modelValue', value))
</script>

<style scoped>
.editor-heading { display: flex; justify-content: space-between; align-items: center; gap: 16px; margin: 0 0 14px; padding: 14px 16px; border: 1px solid var(--zephyr-border); border-radius: 6px; background: var(--zephyr-surface-muted); }
.editor-heading strong { margin-right: 12px; color: #252a30; font-size: 20px; font-weight: 650; }
.editor-subtitle { margin-top: 4px; color: var(--zephyr-muted); font-size: 12px; }
.editor-actions { display: flex; align-items: center; gap: 8px; }
.dossier-layout { display: grid; grid-template-columns: minmax(0, 1fr) 240px; gap: 16px; min-height: 0; }
.dossier-tabs { min-width: 0; padding-right: 2px; }
.dossier-tabs :deep(.el-tabs__header) { position: sticky; top: 0; align-self: start; margin-right: 14px; }
.dossier-tabs :deep(.el-tabs__item) { justify-content: flex-start; min-width: 118px; height: 36px; padding: 0 12px; font-size: 13px; }
.dossier-tabs :deep(.el-tabs__active-bar) { background-color: var(--zephyr-primary); }
.dossier-tabs :deep(.el-tabs__item.is-active) { color: var(--zephyr-primary); font-weight: 650; }
.dossier-tabs.is-read-only :deep(.el-tab-pane :is(.el-input, .el-select, .el-input-number, .el-button, .el-checkbox, .el-radio-group)) { pointer-events: none; }
.dossier-tabs.is-read-only :deep(.el-tab-pane .el-input__wrapper), .dossier-tabs.is-read-only :deep(.el-tab-pane .el-select__wrapper) { background: var(--zephyr-surface-muted); }
.change-history-rail { align-self: start; max-height: calc(100vh - 170px); overflow: auto; padding: 14px; border: 1px solid var(--zephyr-border); border-radius: 6px; background: var(--zephyr-surface-muted); }
.change-history-rail h3 { margin: 0 0 12px; color: var(--zephyr-ink); font-size: 14px; font-weight: 650; }
.history-preview { display: grid; gap: 10px; }
.history-preview-item { display: grid; gap: 3px; padding-top: 10px; border-top: 1px solid #e4e8ea; }
.history-preview-item:first-child { padding-top: 0; border-top: 0; }
.history-preview-item strong { color: var(--zephyr-primary); font-size: 12px; }
.history-preview-item span, .history-preview-item time { color: var(--zephyr-muted); font-size: 11px; line-height: 1.45; }
.editor-form { padding: 2px 8px 8px; }
.field-hint, .muted { color: #909399; font-size: 12px; }
.field-hint { line-height: 18px; }
.conflict-alert { margin-bottom: 14px; }
.add-row, .twp-header, .pairing-row { display: flex; align-items: center; gap: 10px; margin: 14px 0; }
.twp-header { justify-content: space-between; margin-top: 18px; }
.pairing-row { justify-content: space-between; min-height: 42px; padding: 0 12px; border: 1px solid #e0e4e8; border-radius: 6px; background: var(--zephyr-surface-muted); }
.pairing-row > div { display: flex; align-items: baseline; flex-wrap: wrap; gap: 8px; min-width: 0; }
.pairing-row strong { color: var(--zephyr-ink); font-size: 13px; }
.pairing-row span { color: #5e6970; font-size: 13px; overflow-wrap: anywhere; }
.pairing-row small { color: #909399; font-size: 12px; }
.add-select { width: 360px; }
h4 { margin: 22px 0 10px; color: #30343a; font-size: 14px; }
:deep(.el-input-number), :deep(.el-select) { width: 100%; }
:global(.part-editor-drawer .el-drawer__header) { min-height: 64px; margin-bottom: 0; padding: 0 24px; border-bottom: 1px solid #e2e6e9; color: #252a30; font-size: 18px; font-weight: 650; }
:global(.part-editor-drawer .el-drawer__body) { padding: 22px 24px 28px; background: #fff; }
:global(.part-editor-drawer .el-drawer__footer) { display: flex; justify-content: flex-end; gap: 8px; padding: 14px 24px; border-top: 1px solid #e2e6e9; background: #fff; }
:deep(.el-tabs__header) { margin-bottom: 18px; }
:deep(.el-tabs__item) { height: 40px; font-size: 13px; }
:deep(.el-tabs__item.is-active) { color: #1e7b69; font-weight: 650; }
:deep(.el-tabs__active-bar) { background-color: #2f9e89; }
:deep(.el-divider__text) { color: #5e6771; font-size: 12px; font-weight: 650; }
:deep(.el-table) { --el-table-header-bg-color: #f7f8f9; --el-table-row-hover-bg-color: #f0f8f6; --el-table-border-color: #e2e6e9; border: 1px solid #e0e4e8; border-radius: 6px; overflow: hidden; }
@media (max-width: 1023px) {
  .dossier-layout { grid-template-columns: 1fr; }
  .change-history-rail { max-height: none; order: 2; }
}
@media (max-width: 720px) {
  .editor-heading, .editor-actions, .add-row, .twp-header, .pairing-row { align-items: stretch; flex-direction: column; }
  .dossier-tabs :deep(.el-tabs__header) { position: static; width: 100%; margin: 0 0 10px; }
  .dossier-tabs :deep(.el-tabs__nav-wrap) { overflow-x: auto; }
  .dossier-tabs :deep(.el-tabs__item) { min-width: auto; }
  .add-select { width: 100%; }
  :global(.part-editor-drawer .el-drawer__body) { padding: 16px; }
  :global(.part-editor-drawer .el-drawer__footer) { padding: 12px 16px; }
  .editor-heading strong { font-size: 18px; overflow-wrap: anywhere; }
  .editor-actions { flex-direction: row; align-items: center; justify-content: space-between; }
  .editor-form { padding: 0; }
  .editor-form :deep(.el-col) { flex: 0 0 100%; max-width: 100%; }
  .dossier-tabs :deep(.el-tabs__header) { float: none; }
  :global(.part-editor-drawer .el-drawer__header) { padding: 0 16px; }
  :global(.part-editor-drawer .el-drawer__footer) { padding-bottom: calc(12px + env(safe-area-inset-bottom)); flex-wrap: wrap; }
}
</style>
