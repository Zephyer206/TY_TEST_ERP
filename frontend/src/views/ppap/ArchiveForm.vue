<template>
  <el-dialog v-model="visible" :title="archive ? '编辑PPAP档案' : '新建PPAP档案'" width="820px" class="ppap-form-dialog" :close-on-click-modal="false" :close-on-press-escape="!saving" :show-close="!saving">
    <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon />
    <el-form label-position="top" @submit.prevent="save">
      <div class="ppap-form-grid">
        <el-form-item label="客户" required><el-select v-model="draft.customer_key" filterable placeholder="选择当前公司客户" aria-label="PPAP客户" :disabled="saving || Boolean(archive?.submissions.length)" @change="changeCustomer"><el-option v-for="c in customers" :key="c.key" :label="c.name" :value="c.key" /></el-select></el-form-item>
        <el-form-item label="负责人" required><el-input v-model="draft.owner" maxlength="100" aria-label="PPAP负责人" :disabled="saving" /></el-form-item>
      </div>
      <el-form-item label="档案名称" required><el-input v-model="draft.name" maxlength="500" aria-label="PPAP档案名称" placeholder="模具号（件号）产品名 PPAP 模具类型" :disabled="saving" /><el-button link type="primary" :disabled="saving || !selected.length" @click="makeName">按关联明细生成名称</el-button></el-form-item>
      <div class="ppap-form-grid">
        <el-form-item label="计划提交日期"><el-date-picker v-model="draft.planned_date" type="date" value-format="YYYY-MM-DD" aria-label="计划提交日期" :disabled="saving" /></el-form-item>
        <el-form-item label="所属公司"><el-input :model-value="company === 'tianyue' ? '天越' : '盖博'" disabled /></el-form-item>
      </div>
      <el-form-item label="关联零件 / 安装包">
        <div class="ppap-link-picker"><el-select v-model="picked" filterable remote :remote-method="searchReferences" :loading="searching" :disabled="saving || !draft.customer_key" placeholder="输入件号或产品名搜索，选择后添加" aria-label="关联对象"><el-option v-for="r in references" :key="r.key" :label="`${r.kind === 'package' ? '安装包' : '零件'} · ${r.part_no} · ${r.name}`" :value="r.key" /></el-select><el-button :disabled="saving || !picked" @click="addReference">添加关联</el-button></div>
      </el-form-item>
      <div v-for="(item, index) in selected" :key="item.key" class="ppap-link-editor">
        <div class="ppap-section-line"><strong>{{ item.part_no }} · {{ item.name }}</strong><el-button link type="danger" :disabled="saving" :aria-label="`移除关联${item.part_no}`" @click="selected.splice(index, 1)">移除</el-button></div>
        <div class="ppap-form-grid three"><el-form-item label="模具号"><el-input v-model="item.tooling_no" maxlength="200" :disabled="saving" /></el-form-item><el-form-item label="模具类型"><el-input v-model="item.mold_type" maxlength="100" :disabled="saving" /></el-form-item><el-form-item label="图纸版本"><el-input v-model="item.drawing_version" maxlength="100" :disabled="saving" /></el-form-item></div>
      </div>
      <el-form-item label="备注"><el-input v-model="draft.remark" type="textarea" :rows="2" maxlength="6000" :disabled="saving" /></el-form-item>
    </el-form>
    <template #footer><el-button :disabled="saving" @click="visible = false">取消</el-button><el-button type="primary" :loading="saving" @click="save">保存档案</el-button></template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ppapApi, type PpapArchiveInput, type PpapDetail, type PpapLink } from '@/api/ppap'
import type { CompanyKey } from '@/stores/company'
const props = defineProps<{ modelValue: boolean; company: CompanyKey; archive: PpapDetail | null; defaultOwner: string }>()
const emit = defineEmits<{ 'update:modelValue': [boolean]; saved: [PpapDetail] }>()
const visible = computed({ get: () => props.modelValue, set: v => emit('update:modelValue', v) })
const draft = ref<PpapArchiveInput>({ name: '', customer_key: '', owner: '', planned_date: null, remark: '', links: [] })
const selected = ref<PpapLink[]>([])
const customers = ref<{ key: string; name: string }[]>([])
const references = ref<PpapLink[]>([])
const picked = ref(''), saving = ref(false), searching = ref(false), error = ref('')
let referenceRequest = 0
watch(() => props.modelValue, async open => {
  if (!open) return
  error.value = ''; picked.value = ''; references.value = []
  const a = props.archive
  draft.value = { name: a?.name || '', customer_key: a?.customer_key || '', owner: a?.owner || props.defaultOwner, planned_date: a?.planned_date || null, remark: a?.remark || '', links: [] }
  selected.value = (a?.links || []).map(item => ({ ...item }))
  try { customers.value = (await ppapApi.options({ company: props.company })).customers; if (draft.value.customer_key) await searchReferences('') } catch (e) { error.value = (e as Error).message }
})
async function searchReferences(search: string) {
  if (!draft.value.customer_key) return
  const request = ++referenceRequest
  searching.value = true
  try { const result = await ppapApi.options({ company: props.company, customer_key: draft.value.customer_key, search }); if (request === referenceRequest) references.value = result.references } catch (e) { if (request === referenceRequest) error.value = (e as Error).message } finally { if (request === referenceRequest) searching.value = false }
}
function changeCustomer() { selected.value = []; picked.value = ''; void searchReferences('') }
function addReference() {
  const item = references.value.find(r => r.key === picked.value)
  if (!item || selected.value.some(r => r.key === item.key)) return
  selected.value.push({ ...item, drawing_version: item.drawing_version || '', tooling_no: item.tooling_no || '', mold_type: item.mold_type || '' })
  picked.value = ''
  if (!draft.value.name) makeName()
}
function makeName() {
  const item = selected.value[0]
  if (!item) return
  draft.value.name = `${item.tooling_no}${item.part_no ? `(${item.part_no})` : ''}${item.name}${selected.value.length > 1 ? ` 等${selected.value.length}项` : ''} PPAP${item.mold_type ? ` ${item.mold_type}` : ''}`.trim()
}
async function save() {
  if (saving.value) return
  if (!draft.value.customer_key || !draft.value.name.trim() || !draft.value.owner.trim()) { error.value = '请填写客户、档案名称和负责人'; return }
  saving.value = true; error.value = ''
  const company = props.company
  try {
    const payload: PpapArchiveInput = { ...draft.value, links: selected.value.map(({ key, drawing_version, tooling_no, mold_type }) => ({ key, drawing_version, tooling_no, mold_type })) }
    const result = props.archive ? await ppapApi.update(company, props.archive.id, { ...payload, revision: props.archive.revision }) : await ppapApi.create(company, payload)
    emit('saved', result); visible.value = false
  } catch (e) { error.value = (e as Error).message } finally { saving.value = false }
}
</script>
