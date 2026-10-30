<template>
  <el-dialog v-model="visible" class="quote-dialog" :title="draft ? `${draft.id} · 报价` : '报价'" width="min(900px, 94vw)" destroy-on-close>
    <template v-if="draft">
      <div class="quote-summary">
        <div><strong>{{ draft.customer }}</strong><span>{{ draft.projectName }}</span></div>
        <el-tag size="small" :type="draft.status === '已报价' ? 'success' : 'warning'">{{ draft.status }}</el-tag>
      </div>
      <section class="quote-section">
        <div class="section-heading"><strong>推荐方案与模具</strong><span>开发模具费来自技术评审，项目可按客户折扣或直接确定最终价</span></div>
        <div class="quote-grid">
          <label><span>报价路径</span><el-select v-model="draft.path" style="width:100%"><el-option v-for="item in quotePaths" :key="item" :label="item" :value="item" /></el-select></label>
          <label><span>模具类型</span><el-input v-model="draft.toolingType" placeholder="如：连续模、简易模" /></label>
          <label><span>模具周期 (天)</span><el-input-number v-model="draft.toolingLeadTime" :min="0" :precision="0" controls-position="right" style="width:100%" /></label>
        </div>
        <div class="tooling-pricing-grid">
          <div class="development-tooling">
            <span id="development-tooling-label">开发模具费 (元)</span>
            <output aria-labelledby="development-tooling-label">{{ draft.developmentToolingCost == null ? '未提供' : formatToolingPrice(draft.developmentToolingCost) }}</output>
            <small>技术评审 · 只读</small>
          </div>
          <label for="tooling-discount"><span>客户折扣 (折)</span><el-input-number id="tooling-discount" :model-value="toolingDiscount" :min="0" :max="10" :step="0.1" :precision="4" :disabled="!canDiscountTooling" :placeholder="canDiscountTooling ? '可直接填写最终价' : '请直接定价'" aria-label="客户折扣 (折)" aria-describedby="tooling-pricing-hint" controls-position="right" @update:model-value="updateToolingDiscount" /></label>
          <label for="final-tooling-price"><span>最终模具报价 (元)</span><el-input-number id="final-tooling-price" :model-value="draft.toolingCost" :min="0" :max="9999999999.99" :precision="2" placeholder="填写客户最终价" aria-label="最终模具报价 (元)" aria-describedby="tooling-pricing-hint" controls-position="right" @update:model-value="updateToolingPrice" /></label>
        </div>
        <div id="tooling-pricing-hint" class="tooling-pricing-hint"><span>{{ toolingPricingHint }}</span><strong v-if="toolingSaving > 0">优惠 {{ formatToolingPrice(toolingSaving) }}</strong></div>
      </section>
      <section class="quote-section material-technical-section">
        <div class="section-heading"><strong>材料与技术参数</strong><span>下拉框显示材料库价格，下方填写本次报价最终值，技术参数来自审核资料</span></div>
        <div class="material-tech-row">
          <label class="material-picker"><span>材料名</span><div class="material-picker-row"><el-select v-model="selectedMaterialCode" filterable clearable placeholder="选择材料" @change="handleMaterialChange"><el-option v-for="item in materials" :key="item.code" :label="materialLabel(item)" :value="item.code" /></el-select><el-button title="新增材料" aria-label="新增材料" :icon="Plus" @click="openMaterialCreate" /><el-button title="编辑材料" aria-label="编辑材料" :icon="Edit" :disabled="!selectedMaterial" @click="openMaterialEdit" /><el-button title="删除材料" aria-label="删除材料" :icon="Delete" type="danger" plain :disabled="!selectedMaterial" @click="removeSelectedMaterial" /></div></label>
          <div class="technical-inline">
            <span class="technical-inline-title">技术审核参数</span>
            <div v-for="part in draft.parts" :key="part.id" class="technical-inline-part">
              <span class="mono">{{ part.customerPartNo || '-' }}</span><span>TWP {{ formatTwp(part) }}</span><strong>{{ formatUtilization(part.utilization) }}</strong>
            </div>
          </div>
        </div>
        <div class="material-data-grid">
          <label><span>本次报价密度 (g/cm³)</span><el-input-number v-model="draft.materialDensity" :min="0" :precision="4" :formatter="formatInputNumber" controls-position="right" style="width:100%" /></label>
          <label><span>本次报价原料价 (元/kg)</span><el-input-number v-model="draft.materialUnitPrice" :min="0" :precision="4" :formatter="formatInputNumber" controls-position="right" style="width:100%" /></label>
          <label><span>本次报价废料价 (元/kg)</span><el-input-number v-model="draft.materialScrapPrice" :min="0" :precision="4" :formatter="formatInputNumber" controls-position="right" style="width:100%" /></label>
        </div>
        <div class="technical-table-heading">
          <div><strong>技术审核资料</strong><span>冲床参数来自技术评审，只读；材料成本按本次报价计算</span></div>
          <el-button size="small" :icon="Refresh" :loading="syncingPress" :disabled="!canSyncPress || saving" @click="syncPress">同步冲床资料</el-button>
        </div>
        <p class="press-sync-note">{{ canSyncPress ? '技术评审更新后可同步冲床类型、吨位及双轴属性，已填写的报价和费用保留。' : '报价已锁定，保留原技术审核快照。' }}</p>
        <el-table :data="draft.parts" size="small" border>
          <el-table-column label="零件号" min-width="170"><template #default="{ row }"><span class="mono">{{ row.customerPartNo || '-' }}</span></template></el-table-column>
          <el-table-column label="冲床类型 / 吨位" min-width="150"><template #default="{ row }"><span class="technical-value">{{ formatQuotePress(row) }}</span><small>{{ quotePressNote(row) }}</small></template></el-table-column>
          <el-table-column label="毛料重量 (g/件)" width="145"><template #default="{ row }"><span class="technical-value">{{ formatWeight(materialWeight(row, 'gross')) }}</span></template></el-table-column>
          <el-table-column label="净料重量 (g/件)" width="145"><template #default="{ row }"><span class="technical-value">{{ formatWeight(materialWeight(row, 'net')) }}</span></template></el-table-column>
          <el-table-column label="材料净成本 (元/件)" width="155"><template #default="{ row }"><span class="technical-value">{{ formatCurrency(materialCost(row)) }}</span></template></el-table-column>
        </el-table>
      </section>
      <section class="quote-section pricing-cost-section">
        <div class="section-heading"><strong>报价费用</strong><span>根据本次报价调整各项费用，作为最终报价的成本与利润组成</span></div>
        <div class="pricing-cost-grid">
          <label><span>共用表面收费规则</span><el-select v-model="sharedSurfaceRuleId" clearable placeholder="留空按本次报价手填" @change="changeSurfaceRule"><el-option v-for="rule in sharedSurfaceRules" :key="rule.id" :value="rule.id" :label="`${rule.name} · ${rule.rate} ${rule.unit}`" /></el-select></label>
          <label><span>{{sharedSurfaceRuleId ? '本次报价手填费用（已由规则替代）' : '表面处理 (元/件)'}}</span><el-input-number :key="sharedSurfaceRuleId || 'manual-surface'" v-model="draft.surfaceTreatmentFee" :disabled="Boolean(sharedSurfaceRuleId)" :min="0" :precision="4" :formatter="formatInputNumber" controls-position="right" style="width:100%" /></label>
          <label><span>全检包装 (元/件)</span><el-input-number v-model="draft.inspectionFee" :min="0" :precision="4" :formatter="formatInputNumber" controls-position="right" style="width:100%" /></label>
          <label><span>运费 (元/件)</span><el-input-number v-model="draft.freightFee" :min="0" :precision="4" :formatter="formatInputNumber" controls-position="right" style="width:100%" /></label>
          <label><span>管理费用 (元/件)</span><el-input-number v-model="draft.managementFee" :min="0" :precision="4" :formatter="formatInputNumber" controls-position="right" style="width:100%" /></label>
          <label><span>利润率 (%)</span><el-input-number v-model="draft.profitMargin" :min="0" :max="100" :precision="2" :formatter="formatInputNumber" controls-position="right" style="width:100%" /></label>
        </div>
        <div class="pricing-cost-summary"><span>材料净成本 {{ formatCurrency(draft.parts.length ? materialCost(draft.parts[0]) : undefined) }}</span><span>费用合计 {{ formatCurrency(additionalCost) }}</span><strong>成本小计 {{ formatCurrency(costSubtotal) }}</strong></div>
      </section>
      <section class="quote-section">
        <div class="section-heading"><strong>零件报价</strong><span>左右件仍属于同一报价组，产品报价分别填写</span></div>
        <el-table :data="draft.parts" size="small" border>
          <el-table-column label="零件号" min-width="150"><template #default="{ row }"><span class="mono">{{ row.customerPartNo }}</span></template></el-table-column>
          <el-table-column prop="name" label="零件名称" min-width="150" />
          <el-table-column label="表面费用 (元/件)" width="140"><template #default="{row}">{{formatCurrency(surfaceFeeOf(row))}}</template></el-table-column>
          <el-table-column label="技术资料" min-width="170"><template #default="{ row }"><span>{{ row.material || '-' }}</span><small>{{ row.thickness || '-' }}mm · {{ row.cavityCount || '-' }}穴<span v-if="row.pairLabel"> · 左右件</span></small></template></el-table-column>
          <el-table-column label="产品报价 (元/件)" width="180"><template #default="{ row }"><el-input-number v-model="row.price" :aria-label="`${row.customerPartNo} 产品报价 (元/件)`" :min="0" :precision="4" :formatter="formatInputNumber" controls-position="right" style="width:150px" /></template></el-table-column>
          <el-table-column label="年用量" width="110"><template #default="{ row }"><el-input-number v-model="row.annualUsage" :min="0" :precision="0" controls-position="right" style="width:100px" /></template></el-table-column>
        </el-table>
        <div class="quote-total"><span>预计年度销售额</span><strong>¥{{ annualTotal.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }}</strong></div>
      </section>
      <label class="note-field"><span>报价备注</span><el-input v-model="draft.quoteNote" type="textarea" :rows="2" placeholder="可填写报价有效期、特殊商务条件或说明" /></label>
    </template>
    <template #footer><div class="quote-footer"><span v-if="draft" class="footer-total">预计年销售额 <strong>¥{{ annualTotal.toLocaleString('zh-CN', { maximumFractionDigits: 2 }) }}</strong></span><div class="quote-footer-actions"><el-button @click="visible = false">取消</el-button><el-button type="primary" :loading="saving" :disabled="syncingPress" @click="save">保存报价</el-button></div></div></template>
  </el-dialog>

  <el-dialog v-model="materialDialogVisible" :title="materialEditId ? '编辑材料' : '新增材料'" width="min(520px, 92vw)" append-to-body destroy-on-close>
    <el-form ref="materialFormRef" :model="materialForm" :rules="materialRules" label-width="92px">
      <el-form-item label="材料名" prop="name"><el-input v-model="materialForm.name" placeholder="例如 SUS301/304" /></el-form-item>
      <el-form-item label="材料分类"><el-input v-model="materialForm.category" placeholder="例如 不锈钢" /></el-form-item>
      <div class="material-metrics">
        <el-form-item label="密度"><el-input-number v-model="materialForm.density" :min="0" :precision="4" :formatter="formatInputNumber" controls-position="right" style="width:100%" /></el-form-item>
        <el-form-item label="原料价"><el-input-number v-model="materialForm.default_price" :min="0" :precision="4" :formatter="formatInputNumber" controls-position="right" style="width:100%" /></el-form-item>
        <el-form-item label="废料价"><el-input-number v-model="materialForm.scrap_price" :min="0" :precision="4" :formatter="formatInputNumber" controls-position="right" style="width:100%" /></el-form-item>
      </div>
    </el-form>
    <template #footer><el-button @click="materialDialogVisible = false">取消</el-button><el-button type="primary" :loading="materialSaving" @click="saveMaterial">保存材料</el-button></template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch, onBeforeUnmount } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete, Edit, Plus, Refresh } from '@element-plus/icons-vue'
import { formatQuotePress, mapQuoteGroup, quotePressNote, type QuoteGroup } from './data'
import { materialsApi } from '@/api/dictionary'
import { quoteGroupsApi } from '@/api/quoteGroups'
import { costingApi } from '@/api/costing'
import type { ChargeRule } from '@/types/costing'

const props = defineProps<{ modelValue: boolean; group: QuoteGroup | null }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean]; saved: [group: QuoteGroup] }>()
const quotePaths: QuoteGroup['path'][] = ['待确定方案', '仅打样', '先打样后开量产模具', '直接开量产模具']
const draft = ref<QuoteGroup | null>(null)
const sharedSurfaceRuleId = ref<number>()
const sharedSurfaceRules = ref<ChargeRule[]>([])
const changeSurfaceRule = () => { if (draft.value) draft.value.surfaceRuleSnapshot = null }
const saving = ref(false)
const syncingPress = ref(false)
const canSyncPress = computed(() => Boolean(props.group?.backendId) && !['已提交审批', '已审批', '已定点'].includes(props.group?.status || ''))
const syncPress = async () => {
  if (!props.group?.backendId || !draft.value || !canSyncPress.value || syncingPress.value || saving.value) return
  const groupId = props.group.backendId
  syncingPress.value = true
  try {
    const updated = mapQuoteGroup(await quoteGroupsApi.syncPress(groupId))
    if (props.group?.backendId !== groupId || draft.value?.backendId !== groupId) return
    Object.assign(props.group, updated)
    const parts = new Map(updated.parts.map(part => [part.id, part]))
    // A technical refresh must preserve every unsaved commercial value in the dialog.
    draft.value.parts = draft.value.parts.map(part => {
      const source = parts.get(part.id)
      return source ? { ...part, pressTonnage: source.pressTonnage, pressTypeKey: source.pressTypeKey,
        pressTypeLabel: source.pressTypeLabel, pressIsDualAxis: source.pressIsDualAxis,
        pressTonnageSource: source.pressTonnageSource } : part
    })
    ElMessage.success('冲床资料已同步，报价和费用保持不变')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '同步冲床资料失败')
  } finally {
    syncingPress.value = false
  }
}
const toolingDiscount = ref<number | undefined>()
const canDiscountTooling = computed(() => Number(draft.value?.developmentToolingCost) > 0)
const formatToolingPrice = (value: number) => `¥${value.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
const discountForToolingPrice = (price: number | undefined | null) => {
  const base = draft.value?.developmentToolingCost
  if (!base || price == null || !Number.isFinite(price) || price < 0 || price > base) return undefined
  return Number((price / base * 10).toFixed(4))
}
const updateToolingDiscount = (value: number | undefined | null) => {
  toolingDiscount.value = value ?? undefined
  if (!draft.value || !canDiscountTooling.value || value == null || !Number.isFinite(value) || value < 0 || value > 10) return
  // Calculate from integer cents so half-cent results round to the nearest cent.
  const baseCents = Math.round(draft.value.developmentToolingCost! * 100)
  draft.value.toolingCost = Math.round(baseCents * value / 10 + 1e-7) / 100
}
const updateToolingPrice = (value: number | undefined | null) => {
  if (!draft.value) return
  draft.value.toolingCost = value as number
  toolingDiscount.value = discountForToolingPrice(value)
}
const toolingSaving = computed(() => {
  if (draft.value?.developmentToolingCost == null || draft.value.toolingCost == null) return 0
  return Math.max(0, draft.value.developmentToolingCost - draft.value.toolingCost)
})
const toolingPricingHint = computed(() => {
  if (draft.value?.developmentToolingCost == null) return '开发尚未提供完整模具费，请直接填写最终价。'
  if (!canDiscountTooling.value) return '开发模具费为 0 元，请直接填写最终价。'
  if (draft.value.toolingCost > draft.value.developmentToolingCost) return '当前为直接定价，最终价高于开发模具费。'
  return '输入 8 即为 8 折；也可直接填写最终价，0 元表示免收。'
})
type MaterialRecord = { id: number; code: string; name: string; name_cn?: string | null; density?: number | null; category?: string | null; default_price?: number | null; scrap_price?: number | null }
const materials = ref<MaterialRecord[]>([])
const selectedMaterialCode = ref('')
const materialDialogVisible = ref(false)
const materialEditId = ref<number | null>(null)
const materialSaving = ref(false)
const materialFormRef = ref()
const materialForm = reactive({ code: '', name: '', name_cn: '', category: '', density: undefined as number | undefined, default_price: undefined as number | undefined, scrap_price: undefined as number | undefined })
const materialRules = {
  name: [{ required: true, message: '请输入材料名', trigger: 'blur' }],
}
const visible = computed({ get: () => props.modelValue, set: value => emit('update:modelValue', value) })
const cloneGroup = (group: QuoteGroup) => JSON.parse(JSON.stringify(group)) as QuoteGroup
const normalizeMaterialName = (value: string) => value.replace(/\s+/g, '').toLowerCase()
const formatPrice = (value: number | null | undefined) => {
  if (value == null || !Number.isFinite(Number(value))) return ''
  return Number(value).toFixed(4).replace(/\.?0+$/, '')
}
const formatInputNumber = (value: string | number | undefined) => {
  if (value == null || value === '') return ''
  return String(value).replace(/\.?0+$/, '')
}
const formatTechnicalNumber = (value: string | number | undefined) => {
  if (value == null || value === '') return ''
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return String(value)
  return numeric.toFixed(4).replace(/\.?0+$/, '')
}
const formatTwp = (part: QuoteGroup['parts'][number]) => {
  const values = [part.thickness, part.width, part.pitch].map(formatTechnicalNumber)
  return values.every(Boolean) ? values.join(' × ') : values.filter(Boolean).join(' × ') || '-'
}
const formatUtilization = (value: string | number | undefined) => {
  const formatted = formatTechnicalNumber(value)
  return formatted ? `${formatted}%` : '-'
}
const parseNumber = (value: string | number | undefined) => {
  if (value === undefined || value === null || value === '') return undefined
  const numeric = Number(value)
  return Number.isFinite(numeric) ? numeric : undefined
}
const materialWeight = (part: QuoteGroup['parts'][number], mode: 'gross' | 'net') => {
  const thickness = parseNumber(part.thickness)
  const width = parseNumber(part.width)
  const pitch = parseNumber(part.pitch)
  const density = parseNumber(draft.value?.materialDensity)
  const utilization = parseNumber(part.utilization)
  if ([thickness, width, pitch, density].some(value => value == null) || !thickness || !width || !pitch || !density) return undefined
  const gross = thickness * width * pitch * density / 1000
  if (mode === 'gross') return gross
  if (utilization == null) return undefined
  return gross * utilization / 100
}
const sharedMaterialResults = ref<Record<number, {material: {amount: string | null}; surface_amount: string | null}>>({})
const materialCost = (part: QuoteGroup['parts'][number]) => {
  const value = sharedMaterialResults.value[part.id]?.material.amount
  return value == null ? undefined : Number(value)
}
const surfaceFeeOf = (part: QuoteGroup['parts'][number]) => {
  const value = sharedMaterialResults.value[part.id]?.surface_amount
  return value == null ? undefined : Number(value)
}
let materialPreviewTimer: ReturnType<typeof setTimeout> | undefined
let materialPreviewGeneration = 0
watch(() => [props.modelValue, draft.value?.materialDensity, draft.value?.materialUnitPrice, sharedSurfaceRuleId.value,
  draft.value?.surfaceRuleSnapshot, draft.value?.surfaceTreatmentFee,
  draft.value?.materialScrapPrice, draft.value?.parts.map(p => [p.id,p.thickness,p.width,p.pitch,p.utilization])], () => {
  clearTimeout(materialPreviewTimer)
  const generation = ++materialPreviewGeneration
  sharedMaterialResults.value = {}
  if (!props.modelValue || !draft.value) return
  materialPreviewTimer = setTimeout(async () => {
    const quote = draft.value
    if (!quote) return
    try {
      const rows = await Promise.all(quote.parts.map(async part => {
        const result = await costingApi.quotationPreview({material:{thickness:parseNumber(part.thickness)??null,
          width:parseNumber(part.width)??null,pitch:parseNumber(part.pitch)??null,
          density:quote.materialDensity??null,material_price:quote.materialUnitPrice??null,
          scrap_price:quote.materialScrapPrice??null,utilization_pct:parseNumber(part.utilization)??null},
          surface_fee:quote.surfaceTreatmentFee??null,surface_rule_id:sharedSurfaceRuleId.value??null,
          surface_rule_snapshot:quote.surfaceRuleSnapshot??null})
        return [part.id,result] as const
      }))
      if (generation === materialPreviewGeneration) sharedMaterialResults.value = Object.fromEntries(rows)
    } catch {
      if (generation === materialPreviewGeneration) sharedMaterialResults.value = {}
    }
  }, 200)
}, {deep:true})
onBeforeUnmount(() => { clearTimeout(materialPreviewTimer); materialPreviewGeneration++ })
const formatWeight = (value: number | undefined) => value == null ? '-' : formatTechnicalNumber(value)
const formatCurrency = (value: number | undefined) => value == null ? '-' : `¥${formatTechnicalNumber(value)}`
const materialLabel = (item: MaterialRecord) => {
  const prices = [
    item.default_price == null ? '' : `原料 ¥${formatPrice(item.default_price)}/kg`,
    item.scrap_price == null ? '' : `废料 ¥${formatPrice(item.scrap_price)}/kg`,
  ].filter(Boolean)
  return prices.length ? `${item.name} · ${prices.join(' · ')}` : item.name
}
const materialCodeForName = (name: string) => {
  const normalized = name
    .trim()
    .toUpperCase()
    .replace(/[^A-Z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')

  return (normalized || 'MAT').slice(0, 38) + '-' + Date.now()
}
const selectedMaterial = computed(() => materials.value.find(item => item.code === selectedMaterialCode.value))
const syncSelectedMaterial = () => {
  if (!draft.value?.material) {
    selectedMaterialCode.value = ''
    if (draft.value) {
      draft.value.materialDensity = undefined
      draft.value.materialScrapPrice = undefined
    }
    return
  }
  const target = normalizeMaterialName(draft.value.material)
  const material = materials.value.find(item => [item.code, item.name, item.name_cn || ''].some(value => normalizeMaterialName(value) === target))
    || materials.value.find(item => [item.code, item.name, item.name_cn || ''].some(value => {
      const normalized = normalizeMaterialName(value)
      return normalized.includes(target) || target.includes(normalized)
    }))
  selectedMaterialCode.value = material?.code || ''
  if (!material) {
    draft.value.materialDensity = undefined
    draft.value.materialScrapPrice = undefined
    return
  }
  if (Number(draft.value.materialUnitPrice) <= 0 && material.default_price != null) draft.value.materialUnitPrice = Number(material.default_price)
  if (draft.value.materialDensity == null && material.density != null) draft.value.materialDensity = Number(material.density)
  if (draft.value.materialScrapPrice == null && material.scrap_price != null) draft.value.materialScrapPrice = Number(material.scrap_price)
}
const loadMaterials = async () => {
  try {
    const data = await materialsApi.list<MaterialRecord[]>({ is_active: true, limit: 500 })
    materials.value = Array.isArray(data) ? data : []
    syncSelectedMaterial()
  } catch {
    materials.value = []
  }
}
const handleMaterialChange = (code: string) => {
  const material = materials.value.find(item => item.code === code)
  if (!draft.value) return
  if (!material) {
    draft.value.material = ''
    draft.value.materialDensity = undefined
    draft.value.materialUnitPrice = 0
    draft.value.materialScrapPrice = undefined
    return
  }
  draft.value.material = material.name
  draft.value.materialDensity = material.density == null ? undefined : Number(material.density)
  draft.value.materialUnitPrice = material.default_price == null ? 0 : Number(material.default_price)
  draft.value.materialScrapPrice = material.scrap_price == null ? undefined : Number(material.scrap_price)
}
const resetMaterialForm = () => Object.assign(materialForm, { code: '', name: '', name_cn: '', category: '', density: undefined, default_price: undefined, scrap_price: undefined })
const openMaterialCreate = () => {
  materialEditId.value = null
  resetMaterialForm()
  materialDialogVisible.value = true
}
const openMaterialEdit = () => {
  if (!selectedMaterial.value) return
  materialEditId.value = selectedMaterial.value.id
  Object.assign(materialForm, { code: selectedMaterial.value.code, name: selectedMaterial.value.name, name_cn: '', category: selectedMaterial.value.category || '', density: selectedMaterial.value.density ?? undefined, default_price: selectedMaterial.value.default_price ?? undefined, scrap_price: selectedMaterial.value.scrap_price ?? undefined })
  materialDialogVisible.value = true
}
const saveMaterial = async () => {
  await materialFormRef.value?.validate()
  materialSaving.value = true
  const materialName = materialForm.name.trim()
  const payload = { name: materialName, category: materialForm.category.trim() || null, density: materialForm.density ?? null, default_price: materialForm.default_price ?? null, scrap_price: materialForm.scrap_price ?? null }
  try {
    const saved = materialEditId.value
      ? await materialsApi.update<MaterialRecord>(materialEditId.value, payload)
      : await materialsApi.create<MaterialRecord>({ code: materialCodeForName(materialName), ...payload })
    await loadMaterials()
    selectedMaterialCode.value = saved.code
    handleMaterialChange(saved.code)
    materialDialogVisible.value = false
    ElMessage.success(materialEditId.value ? '材料已更新' : '材料已创建')
  } catch (error: any) {
    ElMessage.error(error?.message || '材料保存失败')
  } finally {
    materialSaving.value = false
  }
}
const removeSelectedMaterial = async () => {
  const material = selectedMaterial.value
  if (!material) return
  try {
    await ElMessageBox.confirm(`删除材料“${material.name}”后，它将不再出现在材料选择中。`, '确认删除材料', { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' })
    await materialsApi.remove(material.id)
    selectedMaterialCode.value = ''
    if (draft.value) {
      draft.value.material = ''
      draft.value.materialDensity = undefined
      draft.value.materialUnitPrice = 0
      draft.value.materialScrapPrice = undefined
    }
    await loadMaterials()
    ElMessage.success('材料已删除')
  } catch (error: any) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error(error?.message || '材料删除失败')
  }
}
watch(() => [props.group, props.modelValue], () => {
  if (props.modelValue && props.group) {
    draft.value = cloneGroup(props.group)
    sharedSurfaceRuleId.value = draft.value.surfaceRuleSnapshot?.id
    void costingApi.catalog().then(result => { sharedSurfaceRules.value = result.treatments.filter(r => (r.calc_mode==='manual'&&r.unit==='元/件')||(r.calc_mode==='net_weight'&&r.unit==='元/kg')) }).catch(() => { sharedSurfaceRules.value=[] })
    toolingDiscount.value = discountForToolingPrice(draft.value.toolingCost)
    draft.value.materialDensity = draft.value.materialDensity == null ? undefined : Number(draft.value.materialDensity)
    draft.value.materialUnitPrice = Number(draft.value.materialUnitPrice) || 0
    draft.value.materialScrapPrice = draft.value.materialScrapPrice == null ? undefined : Number(draft.value.materialScrapPrice)
    draft.value.surfaceTreatmentFee = Number(draft.value.surfaceTreatmentFee || 0)
    draft.value.inspectionFee = Number(draft.value.inspectionFee || 0)
    draft.value.packagingFee = Number(draft.value.packagingFee || 0)
    draft.value.freightFee = Number(draft.value.freightFee || 0)
    draft.value.managementFee = Number(draft.value.managementFee || 0)
    draft.value.profitMargin = Number(draft.value.profitMargin || 0)
    draft.value.toolingLeadTime = Number(draft.value.toolingLeadTime) || Number(draft.value.parts[0]?.toolingLeadTime) || 0
    draft.value.parts = draft.value.parts.map(part => ({ ...part, price: Number(part.price) || 0, annualUsage: Number(part.annualUsage) || 0 }))
    void loadMaterials()
  }
}, { immediate: true })
const annualTotal = computed(() => draft.value?.parts.reduce((sum, part) => sum + Number(part.price || 0) * Number(part.annualUsage || 0), 0) || 0)
const additionalCost = computed(() => {
  const quote = draft.value
  if (!quote) return 0
  const surface = quote.parts[0] ? surfaceFeeOf(quote.parts[0]) : undefined
  if (surface == null) return undefined
  return surface + Number(quote.inspectionFee || 0) + Number(quote.packagingFee || 0) + Number(quote.freightFee || 0) + Number(quote.managementFee || 0)
})
const costSubtotal = computed(() => {
  const material = draft.value?.parts.length ? materialCost(draft.value.parts[0]) : undefined
  return material == null || additionalCost.value == null ? undefined : material + additionalCost.value
})
const save = async () => {
  if (syncingPress.value || saving.value) return
  if (!draft.value || !props.group || !props.group.backendId) return ElMessage.error('报价组尚未落库，无法保存')
  if (draft.value.path === '待确定方案') return ElMessage.warning('请选择报价路径')
  if (!draft.value.toolingType.trim()) return ElMessage.warning('请填写模具类型')
  if (draft.value.toolingCost == null || !Number.isFinite(draft.value.toolingCost) || draft.value.toolingCost < 0) return ElMessage.warning('请填写有效的最终模具报价，免收请填 0')
  if (draft.value.parts.some(part => Number(part.price) <= 0)) return ElMessage.warning('请填写每个零件的产品报价')
  saving.value = true
  try {
    const saved = await quoteGroupsApi.update(props.group.backendId, {
      quote_path: draft.value.path,
      tooling_type: draft.value.toolingType.trim(),
      tooling_cost: Number(draft.value.toolingCost || 0),
      tooling_lead_time: Number(draft.value.toolingLeadTime || 0),
      tooling_life: Number(draft.value.toolingLife || 0),
      material_name: draft.value.material || null,
      material_density: draft.value.materialDensity ?? null,
      material_unit_price: Number(draft.value.materialUnitPrice || 0),
      material_scrap_price: draft.value.materialScrapPrice ?? null,
      surface_treatment_fee: Number(draft.value.surfaceTreatmentFee || 0),
      surface_rule_id: sharedSurfaceRuleId.value ?? null,
      refresh_surface_rule: Boolean(sharedSurfaceRuleId.value && !draft.value.surfaceRuleSnapshot),
      inspection_fee: Number(draft.value.inspectionFee || 0),
      packaging_fee: Number(draft.value.packagingFee || 0),
      freight_fee: Number(draft.value.freightFee || 0),
      management_fee: Number(draft.value.managementFee || 0),
      profit_margin: Number(draft.value.profitMargin || 0),
      material_adjustment: 0,
      quote_note: draft.value.quoteNote || '',
      items: draft.value.parts.map(part => ({ product_price: Number(part.price || 0), annual_usage: Number(part.annualUsage || 0) })),
    })
    Object.assign(props.group, mapQuoteGroup(saved))
    emit('saved', props.group)
    ElMessage.success('报价已保存')
    visible.value = false
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '保存报价失败')
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.quote-summary, .section-heading, .quote-total, .technical-table-heading { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.quote-summary { padding: 12px 14px; border: 1px solid var(--zephyr-border-soft); border-radius: 8px; background: var(--zephyr-surface-muted); }
.quote-summary > div { display: flex; align-items: baseline; flex-wrap: wrap; gap: 5px 12px; min-width: 0; }
.quote-summary strong { font-size: 15px; }
.quote-summary span, .section-heading span, .technical-table-heading span { color: var(--zephyr-muted); font-size: 12px; }
.quote-section { margin-top: 22px; padding-bottom: 22px; border-bottom: 1px solid var(--zephyr-border-soft); }
.section-heading { align-items: flex-start; flex-direction: column; gap: 4px; margin-bottom: 14px; }
.section-heading strong, .technical-table-heading strong { color: var(--zephyr-ink); font-size: 14px; font-weight: 600; }
.technical-table-heading { flex-wrap: wrap; margin: 16px 0 8px; }
.technical-table-heading strong { font-size: 12px; }
.technical-table-heading > div { display: grid; gap: 4px; }
.press-sync-note { margin: 0 0 10px; color: var(--zephyr-muted); font-size: 12px; line-height: 1.6; }
.quote-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
.tooling-pricing-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); align-items: start; gap: 12px; margin-top: 16px; }
.tooling-pricing-grid label, .development-tooling { display: grid; gap: 6px; min-width: 0; }
.tooling-pricing-grid label > span, .development-tooling > span { color: var(--zephyr-muted); font-size: 12px; }
.tooling-pricing-grid :deep(.el-input-number) { width: 100%; }
.development-tooling output { display: flex; align-items: center; min-height: 32px; padding: 0 10px; border-radius: 6px; background: var(--zephyr-surface-muted); color: var(--zephyr-ink); font-family: var(--zephyr-font-mono); font-size: 14px; font-variant-numeric: tabular-nums; overflow-wrap: anywhere; }
.development-tooling small { font-size: 11px; }
.tooling-pricing-hint { display: flex; justify-content: space-between; flex-wrap: wrap; gap: 6px 12px; margin-top: 10px; color: var(--zephyr-muted); font-size: 12px; line-height: 1.6; }
.tooling-pricing-hint strong { color: var(--zephyr-ink); font-weight: 500; font-variant-numeric: tabular-nums; }
.quote-grid label, .note-field, .material-picker, .material-data-grid label, .pricing-cost-grid label { display: grid; gap: 6px; min-width: 0; }
.quote-grid label > span, .note-field > span, .material-picker > span, .pricing-cost-grid label > span, .material-data-grid label > span { color: var(--zephyr-muted); font-size: 12px; }
.material-tech-row { display: grid; grid-template-columns: minmax(330px, 1.2fr) minmax(0, 1fr); gap: 16px; align-items: end; margin-bottom: 14px; }
.material-data-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
.material-picker-row { display: flex; align-items: center; gap: 6px; min-width: 0; }
.material-picker-row :deep(.el-select) { min-width: 0; flex: 1; }
.material-picker-row :deep(.el-button) { flex: none; width: 32px; margin-left: 0; padding: 8px; }
.technical-inline { min-width: 0; min-height: 40px; padding: 8px 10px; border-radius: 6px; background: var(--zephyr-surface-muted); display: flex; flex-direction: column; gap: 5px; overflow-x: auto; }
.technical-inline-title { color: var(--zephyr-muted); font-size: 12px; white-space: nowrap; }
.technical-inline-part { display: flex; align-items: center; gap: 8px; white-space: nowrap; color: var(--zephyr-muted); font-size: 12px; }
.technical-inline-part strong { color: var(--zephyr-ink); font-family: var(--zephyr-font-mono); }
.material-metrics { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin-top: 2px; }
.material-metrics :deep(.el-form-item) { display: block; margin-bottom: 0; }
.material-metrics :deep(.el-form-item__label) { display: block; width: auto !important; height: auto; padding: 0; margin-bottom: 6px; color: var(--zephyr-muted); line-height: 18px; text-align: left; }
.material-metrics :deep(.el-form-item__content) { margin-left: 0 !important; }
.material-metrics :deep(.el-input-number) { width: 100% !important; }
.pricing-cost-grid { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 12px; }
.pricing-cost-summary { display: flex; justify-content: flex-end; align-items: center; flex-wrap: wrap; gap: 6px 18px; margin-top: 14px; color: var(--zephyr-muted); font-size: 12px; font-variant-numeric: tabular-nums; }
.pricing-cost-summary strong { color: var(--zephyr-ink); }
.quote-section :deep(.el-table) { border-radius: 6px; }
.quote-section :deep(.el-table td), .quote-section :deep(.el-table th) { padding: 7px 0; }
.quote-section small { display: block; color: var(--zephyr-muted); font-size: 12px; }
.mono, .technical-value { font-family: var(--zephyr-font-mono); font-size: 12px; font-variant-numeric: tabular-nums; }
.technical-value { color: var(--zephyr-ink); }
.quote-total { justify-content: flex-end; flex-wrap: wrap; margin-top: 12px; color: var(--zephyr-muted); font-size: 12px; }
.quote-total strong { color: var(--zephyr-ink); font-family: var(--zephyr-font-mono); font-size: 16px; font-variant-numeric: tabular-nums; }
.note-field { margin-top: 20px; }
.note-field :deep(.el-textarea__inner) { box-shadow: 0 0 0 1px var(--zephyr-border) inset; }
.quote-footer { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.footer-total { color: var(--zephyr-muted); font-size: 12px; text-align: left; }
.footer-total strong { display: inline-block; color: var(--zephyr-ink); font-family: var(--zephyr-font-mono); font-size: 14px; font-variant-numeric: tabular-nums; }
.quote-footer-actions { flex: none; margin-left: auto; white-space: nowrap; }
@media (max-width: 760px) {
  .quote-grid, .pricing-cost-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .material-tech-row { grid-template-columns: 1fr; }
}
@media (max-width: 520px) {
  .quote-grid, .tooling-pricing-grid, .material-data-grid, .pricing-cost-grid { grid-template-columns: 1fr; }
  .material-metrics { grid-template-columns: 1fr; gap: 10px; }
  .technical-table-heading { align-items: flex-start; flex-direction: column; gap: 4px; }
  .quote-footer { flex-wrap: wrap; gap: 10px; }
  .footer-total { display: flex; align-items: center; justify-content: space-between; gap: 8px; width: 100%; }
}
</style>
