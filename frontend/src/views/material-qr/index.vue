<template>
  <div class="material-qr-workspace">
    <header class="page-header">
      <div><h1>原材料台账</h1><p>查看物料余重、检验状态与分卷去向</p></div>
      <el-button type="primary" :disabled="!canManage || catalogsLoading || !activeMaterials.length" @click="openInbound">原材料入库</el-button>
    </header>

    <details class="lookup-strip">
      <summary>扫码或批次号快速定位</summary>
      <div class="lookup-controls" aria-label="扫码或批次号查询">
      <el-radio-group v-model="lookupMode" size="small" aria-label="查询方式"><el-radio-button label="qr">扫码内容</el-radio-button><el-radio-button label="number">批次号</el-radio-button></el-radio-group>
      <el-input ref="lookupInput" v-model="lookupText" :placeholder="lookupMode === 'qr' ? '扫描或粘贴 MAT 二维码内容，按 Enter 查询' : '输入完整批次号，按 Enter 查询'" clearable :aria-label="lookupMode === 'qr' ? '原材料二维码内容' : '完整批次号'" @keyup.enter="lookupBatch" />
      <el-button :loading="lookupLoading" @click="lookupBatch">查询批次</el-button>
      </div>
    </details>
    <p v-if="lookupError" class="inline-error" role="alert">{{ lookupError }}</p>
    <el-alert v-if="catalogError" class="notice" type="warning" :closable="false" show-icon><template #title>物料与供应商选项加载失败</template><template #default>{{ catalogError }} <el-button link type="primary" @click="loadCatalogs">重新加载</el-button></template></el-alert>

    <section class="batch-panel" aria-label="原材料批次列表">
      <div class="panel-toolbar">
        <div class="filters"><el-select v-model="filters.materialId" clearable filterable placeholder="全部物料" aria-label="按物料筛选" @change="resetAndLoad"><el-option v-for="material in materials" :key="material.id" :value="material.id" :label="materialLabel(material)" /></el-select><el-select v-model="filters.status" clearable placeholder="全部状态" aria-label="按状态筛选" @change="resetAndLoad"><el-option v-for="(label, value) in statusLabels" :key="value" :value="value" :label="label" /></el-select><el-button :loading="listLoading" @click="loadBatches">刷新</el-button></div>
        <div class="page-summary"><span>本页 <b>{{ rows.length }}</b> 批</span><span>待检 <b>{{ pendingCount }}</b></span><span>余重 <b>{{ weight(pageWeight) }}</b> kg</span></div>
      </div>
      <div v-if="listError" class="region-error" role="alert"><span>{{ listError }}</span><el-button size="small" @click="loadBatches">重试</el-button></div>
      <el-table v-loading="listLoading" :data="rows" row-key="id" stripe max-height="620" empty-text="暂无符合条件的批次，可登记原材料入库" class="batch-table">
        <el-table-column label="物料 / 牌号" min-width="185"><template #default="{ row }"><el-button link type="primary" class="material-name" @click="showDetail(row.id)">{{ materialFor(row.material_id)?.name || '未关联物料' }}</el-button><span class="subline">{{ materialFor(row.material_id)?.grade || '未维护牌号' }}<span v-if="row.parent_batch_id"> · 子卷</span></span></template></el-table-column>
        <el-table-column label="当前余重 kg" width="115" align="right"><template #default="{ row }"><strong class="numeric">{{ weight(row.current_weight) }}</strong></template></el-table-column>
        <el-table-column label="状态" width="104"><template #default="{ row }"><el-tag :type="statusType(row.status)" size="small" effect="plain">{{ statusLabel(row.status) }}</el-tag></template></el-table-column>
        <el-table-column label="规格" min-width="160"><template #default="{ row }">{{ specification(row) }}</template></el-table-column>
        <el-table-column label="入库重量 kg" width="115" align="right"><template #default="{ row }"><span class="numeric">{{ weight(row.gross_weight) }}</span></template></el-table-column>
        <el-table-column label="供应商" min-width="135" show-overflow-tooltip><template #default="{ row }">{{ supplierFor(row.supplier_id)?.name || '—' }}</template></el-table-column>
        <el-table-column label="业务批次" min-width="205"><template #default="{ row }"><span class="batch-number">{{ row.batch_no }}</span></template></el-table-column>
        <el-table-column label="入库时间" width="145"><template #default="{ row }">{{ dateTime(row.received_at || row.created_at) }}</template></el-table-column>
        <el-table-column label="操作" width="168" fixed="right"><template #default="{ row }"><el-button link type="primary" @click="showDetail(row.id)">详情</el-button><el-button v-if="row.status === 'pending_iqc'" link type="primary" :disabled="!canManage" @click="openIqc(row)">IQC</el-button><el-button v-else-if="canSplit(row)" link type="primary" :disabled="!canManage" @click="openSplit(row)">分卷</el-button><el-button link type="primary" :loading="printingId === row.id" @click="previewReprint(row.id)">补打</el-button></template></el-table-column>
      </el-table>
      <footer class="pagination-row"><span>每页 {{ pageSize }} 条<span v-if="!canManage"> · 当前账号可查询，入库、IQC 和分卷需主管权限</span></span><div><el-button :disabled="page === 1 || listLoading" @click="changePage(-1)">上一页</el-button><span class="page-index">第 {{ page }} 页</span><el-button :disabled="rows.length < pageSize || listLoading" @click="changePage(1)">下一页</el-button></div></footer>
    </section>

    <el-dialog v-model="inboundVisible" title="原材料入库" width="610px" class="material-qr-dialog" :close-on-click-modal="!inboundSaving" :close-on-press-escape="!inboundSaving" :show-close="!inboundSaving" @opened="inboundMaterial?.focus()">
      <p class="form-intro">选择物料和供应商后登记实收重量，批次号与二维码由系统生成。</p>
      <el-form label-position="top" @submit.prevent="submitInbound">
        <div class="form-grid"><el-form-item label="物料" required><el-select ref="inboundMaterial" v-model="inbound.materialId" filterable placeholder="选择物料" aria-label="入库物料" @change="applyMaterialDefaults"><el-option v-for="material in activeMaterials" :key="material.id" :value="material.id" :label="materialLabel(material)" /></el-select></el-form-item><el-form-item label="供应商" required><el-select v-model="inbound.supplierId" filterable placeholder="选择供应商" aria-label="入库供应商"><el-option v-for="supplier in activeSuppliers" :key="supplier.id" :value="supplier.id" :label="supplier.name" /></el-select></el-form-item><el-form-item label="实收重量 kg" required><el-input-number v-model="inbound.grossWeight" :min="0.001" :precision="3" :step="1" controls-position="right" aria-label="实收重量 kg" /></el-form-item><el-form-item label="采购单号"><el-input v-model="inbound.poNo" maxlength="100" placeholder="可选" aria-label="采购单号" /></el-form-item><el-form-item label="厚度 mm"><el-input-number v-model="inbound.thickness" :min="0.001" :precision="3" controls-position="right" aria-label="厚度 mm" /></el-form-item><el-form-item label="宽度 mm"><el-input-number v-model="inbound.width" :min="0.001" :precision="3" controls-position="right" aria-label="宽度 mm" /></el-form-item></div>
      </el-form><p v-if="inboundError" class="inline-error" role="alert">{{ inboundError }}</p>
      <template #footer><el-button :disabled="inboundSaving" @click="inboundVisible = false">取消</el-button><el-button type="primary" :loading="inboundSaving" @click="submitInbound">登记入库</el-button></template>
    </el-dialog>

    <el-dialog v-model="iqcVisible" title="来料检验 IQC" width="480px" class="material-qr-dialog" :close-on-click-modal="!iqcSaving" :close-on-press-escape="!iqcSaving" :show-close="!iqcSaving">
      <div class="selected-batch"><strong>{{ materialTitle(iqcTarget) }}</strong><span class="subline">业务批次 {{ iqcTarget?.batch_no }}</span></div><el-form label-position="top"><el-form-item label="检验结果" required><el-radio-group v-model="iqc.result" aria-label="检验结果"><el-radio-button label="passed">合格</el-radio-button><el-radio-button label="failed">不合格</el-radio-button></el-radio-group></el-form-item><el-form-item label="检验说明"><el-input v-model="iqc.notes" type="textarea" :rows="3" maxlength="500" show-word-limit placeholder="记录检验说明" aria-label="检验说明" /></el-form-item></el-form><p v-if="iqcError" class="inline-error" role="alert">{{ iqcError }}</p>
      <template #footer><el-button :disabled="iqcSaving" @click="iqcVisible = false">取消</el-button><el-button type="primary" :loading="iqcSaving" @click="submitIqc">保存检验结果</el-button></template>
    </el-dialog>

    <el-dialog v-model="splitVisible" title="原材料分卷" width="690px" class="material-qr-dialog" :close-on-click-modal="!splitSaving" :close-on-press-escape="!splitSaving" :show-close="!splitSaving">
      <div class="selected-batch"><strong>{{ materialTitle(splitTarget) }}</strong><span class="subline">业务批次 {{ splitTarget?.batch_no }}</span></div><div class="split-balance" aria-live="polite"><span>母卷当前 <b>{{ weight(splitTarget?.current_weight) }}</b> kg</span><span>分出 <b>{{ weight(splitTotal) }}</b> kg</span><span :class="{ 'inline-error': splitRemaining < -0.001 }">分卷后余重 <b>{{ weight(splitRemaining) }}</b> kg</span></div>
      <p class="form-intro">每个子卷生成独立二维码；分出重量与母卷余重合计保持不变。</p>
      <div class="split-editor"><div class="split-head"><span>子卷</span><span>重量 kg *</span><span>宽度 mm</span><span>长度 mm</span><span></span></div><div v-for="(item, index) in splitItems" :key="item.key" class="split-row"><span class="numeric">{{ index + 1 }}</span><el-input-number v-model="item.weight" :min="0.001" :precision="3" controls-position="right" :aria-label="`子卷 ${index + 1} 重量 kg`" /><el-input-number v-model="item.width" :min="0.001" :precision="3" controls-position="right" :aria-label="`子卷 ${index + 1} 宽度 mm`" /><el-input-number v-model="item.length" :min="0.001" :precision="3" controls-position="right" :aria-label="`子卷 ${index + 1} 长度 mm`" /><el-button link type="danger" :disabled="splitItems.length === 1 || splitSaving" :aria-label="`移除子卷 ${index + 1}`" @click="splitItems.splice(index, 1)">移除</el-button></div></div>
      <el-button class="add-split" :disabled="splitSaving || splitItems.length >= 30" @click="addSplit">添加子卷</el-button><p v-if="splitError" class="inline-error" role="alert">{{ splitError }}</p>
      <template #footer><el-button :disabled="splitSaving" @click="splitVisible = false">取消</el-button><el-button type="primary" :loading="splitSaving" :disabled="!splitValid" @click="submitSplit">确认分卷并预览标签</el-button></template>
    </el-dialog>

    <el-dialog v-model="detailVisible" title="原材料详情与追溯" width="940px" class="material-qr-dialog" @closed="detail = null">
      <div v-loading="detailLoading" class="detail-content">
        <div v-if="detailError" class="region-error" role="alert"><span>{{ detailError }}</span><el-button @click="showDetail(detailId)">重试</el-button></div>
        <template v-if="detail">
          <div class="detail-heading"><div><h2>{{ materialTitle(detail.batch) }}</h2><p>{{ detail.batch.supplier_name || '未关联供应商' }}</p><span class="batch-number">业务批次 {{ detail.batch.batch_no }}</span></div><el-tag :type="statusType(detail.batch.status)" effect="plain">{{ statusLabel(detail.batch.status) }}</el-tag></div>
          <dl class="detail-facts"><div><dt>当前余重</dt><dd>{{ weight(detail.batch.current_weight) }} <small>kg</small></dd></div><div><dt>入库重量</dt><dd>{{ weight(detail.batch.gross_weight) }} <small>kg</small></dd></div><div><dt>规格</dt><dd class="fact-small">{{ specification(detail.batch) }}</dd></div><div><dt>入库时间</dt><dd class="fact-small">{{ dateTime(detail.batch.received_at || detail.batch.created_at) }}</dd></div></dl>
          <div class="detail-actions"><el-button v-if="detail.batch.status === 'pending_iqc'" :disabled="!canManage" @click="openIqc(detail.batch)">登记 IQC</el-button><el-button v-if="canSplit(detail.batch)" :disabled="!canManage" @click="openSplit(detail.batch)">分卷</el-button><el-button :loading="printingId === detail.batch.id" @click="previewReprint(detail.batch.id)">预览并补打标签</el-button></div>
          <el-tabs v-model="detailTab">
            <el-tab-pane label="母子与同胞批次" name="family">
              <p v-if="familyError" class="inline-error" role="alert">{{ familyError }} <el-button link @click="loadFamily(detail.batch)">重试</el-button></p>
              <div v-if="parentBatch" class="parent-link"><span>母卷</span><el-button link type="primary" @click="showDetail(parentBatch.id)">{{ materialTitle(parentBatch) }}</el-button><span>余重 {{ weight(parentBatch.current_weight) }} kg</span><span class="batch-number">业务批次 {{ parentBatch.batch_no }}</span></div>
              <h3 class="section-title">{{ detail.batch.parent_batch_id ? '同胞子卷' : '已分出的子卷' }} <span>{{ familyRows.length }} 批</span></h3>
              <el-table v-loading="familyLoading" :data="familyRows" row-key="batch_no" max-height="300" empty-text="暂无其他关联子卷">
                <el-table-column label="物料 / 牌号" min-width="180"><template #default="{ row }"><el-button link type="primary" class="material-name" @click="openFamilyBatch(row)">{{ materialTitle(row) }}</el-button></template></el-table-column>
                <el-table-column label="当前余重 kg" width="125" align="right"><template #default="{ row }"><strong>{{ weight(row.current_weight) }}</strong></template></el-table-column>
                <el-table-column label="状态" width="100"><template #default="{ row }">{{ statusLabel(row.status) }}</template></el-table-column>
                <el-table-column label="规格" min-width="140"><template #default="{ row }">{{ specification(row) }}</template></el-table-column>
                <el-table-column label="业务批次" min-width="205"><template #default="{ row }"><span class="batch-number">{{ row.batch_no }}</span></template></el-table-column>
              </el-table>
            </el-tab-pane>
            <el-tab-pane label="重量与操作流水" name="transactions"><el-table :data="detail.transactions" max-height="320" empty-text="暂无操作流水"><el-table-column label="时间" width="145"><template #default="{ row }">{{ dateTime(row.created_at) }}</template></el-table-column><el-table-column label="操作" width="100"><template #default="{ row }">{{ transactionLabel(row.transaction_type) }}</template></el-table-column><el-table-column label="重量变化 kg" width="120" align="right"><template #default="{ row }">{{ row.quantity_change > 0 ? '+' : '' }}{{ weight(row.quantity_change) }}</template></el-table-column><el-table-column label="操作后 kg" width="110" align="right"><template #default="{ row }">{{ weight(row.weight_after) }}</template></el-table-column><el-table-column label="操作人 ID" prop="operator_id" width="100" /><el-table-column label="说明" prop="notes" min-width="210" show-overflow-tooltip /></el-table></el-tab-pane>
            <el-tab-pane label="检验与采购" name="inspection"><dl class="identity-facts"><dt>IQC 结果</dt><dd>{{ detail.batch.iqc_result === 'passed' ? '合格' : detail.batch.iqc_result === 'failed' ? '不合格' : '未检验' }}</dd><dt>检验时间</dt><dd>{{ dateTime(detail.batch.iqc_time) }}</dd><dt>检验说明</dt><dd>{{ detail.batch.iqc_notes || '—' }}</dd><dt>采购单号</dt><dd>{{ detail.batch.po_no || '—' }}</dd></dl></el-tab-pane>
            <el-tab-pane label="追溯标识" name="identity"><dl class="identity-facts"><dt>业务批次</dt><dd class="batch-number">{{ detail.batch.batch_no }}</dd><dt>已保存二维码内容</dt><dd class="qr-content">{{ detail.batch.qr_code || '未保存二维码' }}</dd></dl></el-tab-pane>
          </el-tabs>
        </template>
      </div>
      <template #footer><el-button @click="detailVisible = false">关闭</el-button></template>
    </el-dialog>

    <el-dialog v-model="printVisible" :title="printTitle" width="780px" class="material-qr-dialog">
      <p class="form-intro">核对物料、规格与重量后按 100% 比例打印，关闭浏览器页眉页脚。标签二维码沿用已保存的追溯身份。</p><p v-if="printError" class="inline-error" role="alert">{{ printError }}</p>
      <div class="label-preview"><article v-for="label in printLabels" :key="label.batch_no" class="material-qr-label"><div class="label-information"><h3>{{ materialTitle(label) }}</h3><p>{{ specification(label) }}</p><p class="label-weight">当前重量 <strong>{{ weight(label.current_weight) }} kg</strong></p><p>{{ label.supplier_name || '未关联供应商' }}</p><p class="label-batch">业务批次 {{ label.batch_no }}</p><p v-if="label.parent_batch_no" class="label-batch">母卷批次 {{ label.parent_batch_no }}</p><details class="label-identity"><summary>查看追溯标识</summary><code>{{ label.qr_code }}</code></details></div><img v-if="qrImage(label)" :src="qrImage(label)" :alt="`${materialTitle(label)}，业务批次 ${label.batch_no} 二维码`" /></article></div>
      <template #footer><el-button @click="printVisible = false">关闭预览</el-button><el-button type="primary" :disabled="!printLabels.length || printLabels.some(label => !qrImage(label))" @click="printLabelsNow">打开系统打印</el-button></template>
    </el-dialog>
    <Teleport to="body"><section id="material-qr-print-sheet" :data-print-active="printVisible" aria-hidden="true"><component :is="'style'" v-if="printVisible">@page { size: A4; margin: 12mm; }</component><article v-for="label in printLabels" :key="label.batch_no" class="material-qr-paper-label"><div><h3>{{ materialTitle(label) }}</h3><p>{{ specification(label) }}</p><p class="paper-weight">重量 <strong>{{ weight(label.current_weight) }} kg</strong></p><p>{{ label.supplier_name || '未关联供应商' }}</p><p class="paper-batch">业务批次 {{ label.batch_no }}</p><p v-if="label.parent_batch_no" class="paper-batch">母卷 {{ label.parent_batch_no }}</p><code>{{ label.qr_code }}</code></div><img v-if="qrImage(label)" :src="qrImage(label)" alt="" /></article></section></Teleport>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { materialQrApi } from '@/api/materialQr'
import { authApi } from '@/api/auth'
import type { BatchStatus, BatchTraceResponse, MaterialBatchResponse, MaterialBatchDetailResponse, MaterialBatchScanResponse, MaterialResponse, SupplierResponse } from '@/types/legacyQr'

type BatchRow = MaterialBatchResponse | MaterialBatchDetailResponse
type SplitRow = { key: number; weight: number | undefined; width: number | undefined; length: number | undefined }
type MaterialIdentity = { material_id?: number | null; material_name?: string | null; material_grade?: string | null }
type MaterialDimensions = { thickness?: number | null; width?: number | null; length?: number | null }
const actorLevel = ref(0)
const canManage = computed(() => actorLevel.value >= 2)
const statusLabels: Record<string, string> = { pending_iqc: '待 IQC', available: '可用', in_use: '使用中', partial: '部分余料', exhausted: '已耗尽', rejected: '检验不合格', scrapped: '已报废' }
const materials = ref<MaterialResponse[]>([]), suppliers = ref<SupplierResponse[]>([])
const activeMaterials=computed(()=>materials.value.filter(item=>item.is_active)), activeSuppliers=computed(()=>suppliers.value.filter(item=>item.is_active))
const catalogsLoading = ref(false), catalogError = ref('')
const rows = ref<MaterialBatchResponse[]>([]), page = ref(1), pageSize = 50
const listLoading = ref(false), listError = ref('')
const filters = reactive({ materialId: undefined as number | undefined, status: '' as BatchStatus | '' })
const lookupMode = ref('qr'), lookupText = ref(''), lookupLoading = ref(false), lookupError = ref('')
const lookupInput = ref<{ focus: () => void }>(), inboundMaterial = ref<{ focus: () => void }>()
const pendingCount = computed(() => rows.value.filter(row => row.status === 'pending_iqc').length)
const pageWeight = computed(() => rows.value.reduce((total, row) => total + row.current_weight, 0))
const detailVisible = ref(false), detailLoading = ref(false), detailError = ref(''), detailId = ref(0), detailTab = ref('family')
const detail = ref<BatchTraceResponse | null>(null)
const familyRows = ref<MaterialBatchScanResponse[]>([]), parentBatch = ref<MaterialBatchScanResponse | null>(null), familyLoading = ref(false), familyError = ref('')
const inboundVisible = ref(false), inboundSaving = ref(false), inboundError = ref('')
const inbound = reactive({ materialId: undefined as number | undefined, supplierId: undefined as number | undefined, grossWeight: undefined as number | undefined, thickness: undefined as number | undefined, width: undefined as number | undefined, poNo: '' })
const iqcVisible = ref(false), iqcSaving = ref(false), iqcError = ref(''), iqcTarget = ref<BatchRow | null>(null)
const iqc = reactive({ result: 'passed' as 'passed' | 'failed', notes: '' })
const splitVisible = ref(false), splitSaving = ref(false), splitError = ref(''), splitTarget = ref<BatchRow | null>(null), splitItems = ref<SplitRow[]>([])
let splitKey = 0
const splitTotal = computed(() => splitItems.value.reduce((total, row) => total + (row.weight || 0), 0))
const splitRemaining = computed(() => (splitTarget.value?.current_weight || 0) - splitTotal.value)
const splitValid = computed(() => !!splitItems.value.length && splitItems.value.every(item => positive(item.weight)) && splitRemaining.value >= -0.001)
const printVisible = ref(false), printTitle = ref('原材料标签预览'), printingId = ref<number | null>(null), printLabels = ref<MaterialBatchScanResponse[]>([]), printError = ref('')
let detailRequest = 0, familyRequest = 0, listRequest = 0

function positive(value: number | undefined | null): value is number { return typeof value === 'number' && Number.isFinite(value) && value > 0 }
function weight(value: number | null | undefined) { return value == null || !Number.isFinite(value) ? '—' : value.toLocaleString('zh-CN', { minimumFractionDigits: 3, maximumFractionDigits: 3 }) }
function dimension(value: number | null | undefined) { return value == null ? '—' : value.toLocaleString('zh-CN', { maximumFractionDigits: 3 }) }
function dateTime(value: string | null | undefined) { if (!value) return '—'; const date = new Date(value); return Number.isNaN(date.getTime()) ? '—' : new Intl.DateTimeFormat('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false }).format(date) }
function statusLabel(status: string) { return statusLabels[status] || status }
function statusType(status: string): 'success' | 'warning' | 'danger' | 'info' { return status === 'available' ? 'success' : ['pending_iqc', 'partial', 'in_use'].includes(status) ? 'warning' : ['rejected', 'scrapped'].includes(status) ? 'danger' : 'info' }
function canSplit(batch: BatchRow) { return ['available', 'partial'].includes(batch.status) && batch.current_weight > 0 }
function materialFor(id: number | null | undefined) { return materials.value.find(item => item.id === id) }
function supplierFor(id: number | null | undefined) { return suppliers.value.find(item => item.id === id) }
function materialTitle(batch: MaterialIdentity | null | undefined) {
  const material = materialFor(batch?.material_id)
  const name = batch?.material_name || material?.name || '未关联物料'
  const grade = batch?.material_grade || material?.grade
  return grade ? `${name} · ${grade}` : name
}
function specification(batch: MaterialDimensions) {
  const values = [['厚', batch.thickness], ['宽', batch.width], ['长', batch.length]] as const
  const parts = values.filter(([, value]) => value != null).map(([label, value]) => `${label} ${dimension(value)}`)
  return parts.length ? `${parts.join(' × ')} mm` : '未维护规格'
}
function materialLabel(material: MaterialResponse) { return `${material.name} · ${material.grade} (${material.material_no})` }
function transactionLabel(value: string) { return ({ receive: '入库', iqc: '来料检验', split: '分卷', consume: '领用消耗', scrap: '报废' } as Record<string, string>)[value] || value }
function errorText(error: unknown, fallback: string) { const status = (error as { status?: number })?.status; if (status === 403) return '当前账号没有执行此操作的权限。'; if (status === 404) return '批次或关联资料不存在，请刷新后重试。'; if (status === 409) return '批次状态已变化，请刷新后重试。'; const detailText = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail; const known: Record<string, string> = { 'Material not found': '所选物料已不存在，请重新选择。', 'Supplier not found': '所选供应商已不存在，请重新选择。', 'Gross weight is required': '请输入实收重量。', 'At least one split is required': '请至少填写一个子卷。' }; if (typeof detailText === 'string' && known[detailText]) return known[detailText]; if (typeof detailText === 'string' && detailText.startsWith('Split weight exceeds')) return '分出重量超过母卷当前余重，请刷新母卷后重新填写。'; if (typeof detailText === 'string' && detailText.startsWith('Batch not splittable')) return '该批次当前状态不能分卷，请刷新后重试。'; return fallback }
async function allPages<T>(loader: (params: { skip: number; limit: number }) => Promise<T[]>) { const result: T[] = []; for (let skip = 0; ; skip += 100) { const items = await loader({ skip, limit: 100 }); result.push(...items); if (items.length < 100) return result } }
async function loadCatalogs() { catalogsLoading.value = true; catalogError.value = ''; try { const results = await Promise.all([allPages(params => materialQrApi.listMaterials({...params,include_inactive:true})), allPages(params => materialQrApi.listSuppliers(params))]); materials.value = results[0]; suppliers.value = results[1] } catch (error) { catalogError.value = errorText(error, '请检查连接后重试。') } finally { catalogsLoading.value = false } }
async function loadBatches() { const request=++listRequest; listLoading.value = true; listError.value = ''; try { const result = await materialQrApi.listBatches({ material_id: filters.materialId, status: filters.status || undefined, skip: (page.value - 1) * pageSize, limit: pageSize }); if(request===listRequest)rows.value=result } catch (error) { if(request!==listRequest)return; listError.value = errorText(error, '原材料批次加载失败，请重试。'); rows.value = [] } finally { if(request===listRequest)listLoading.value = false } }
function resetAndLoad() { page.value = 1; void loadBatches() }
function changePage(delta: number) { page.value += delta; void loadBatches() }
async function lookupBatch() { if (lookupLoading.value) return; lookupError.value = ''; const text = lookupText.value.trim(); if (!text) { lookupError.value = lookupMode.value === 'qr' ? '请扫描或粘贴原材料二维码内容。' : '请输入完整批次号。'; lookupInput.value?.focus(); return } lookupLoading.value = true; try { if (lookupMode.value === 'number') { const batch = await materialQrApi.getBatchByNo(text); await showDetail(batch.id) } else { const match = /^MAT:([1-9]\d*):\d{8}(?:\d{6})?(?::.*)?$/.exec(text); const id = match ? Number(match[1]) : NaN; if (!Number.isSafeInteger(id) || id <= 0) { lookupError.value = '此处仅接受有效的 MAT 原材料二维码。'; return } const batch = await materialQrApi.scanQr(id); if (batch.qr_code !== text) { lookupError.value = '扫码内容与该批次已保存的二维码不一致，请核对标签。'; return } await showDetail(batch.id) } } catch (error) { lookupError.value = errorText(error, '未找到该批次，请核对完整二维码或批次号。') } finally { lookupLoading.value = false } }
async function showDetail(id: number) { const request = ++detailRequest; ++familyRequest; detailVisible.value = true; detailLoading.value = true; detailError.value = ''; detail.value = null; detailId.value = id; detailTab.value = 'family'; familyRows.value = []; parentBatch.value = null; try { const result = await materialQrApi.getTraceability(id); if (request !== detailRequest) return; detail.value = result; await loadFamily(result.batch) } catch (error) { if (request === detailRequest) detailError.value = errorText(error, '批次详情加载失败，请重试。') } finally { if (request === detailRequest) detailLoading.value = false } }
async function loadFamily(batch: MaterialBatchDetailResponse) { const request=++familyRequest; const current=()=>request===familyRequest && detail.value?.batch.id===batch.id; familyLoading.value=true; familyError.value=''; try { if(batch.parent_batch_id){ const result=await materialQrApi.scanChild(batch.id); if(!current())return; parentBatch.value=result.parent_batch; familyRows.value=result.sibling_batches } else { const result=await materialQrApi.listChildren(batch.id); if(!current())return; parentBatch.value=null; familyRows.value=result } } catch(error){if(current())familyError.value=errorText(error,'关联批次加载失败。')} finally {if(current())familyLoading.value=false} }
async function openFamilyBatch(row: MaterialBatchScanResponse) { try { const batch = await materialQrApi.getBatchByNo(row.batch_no); await showDetail(batch.id) } catch (error) { familyError.value = errorText(error, '此历史子卷暂无独立台账，请使用二维码内容核对标签。') } }
function openInbound() { Object.assign(inbound, { materialId: undefined, supplierId: undefined, grossWeight: undefined, thickness: undefined, width: undefined, poNo: '' }); inboundError.value = ''; inboundVisible.value = true }
function applyMaterialDefaults() { const material = materialFor(inbound.materialId); if (!material) return; inbound.thickness = material.thickness || undefined; inbound.width = material.width || undefined; inbound.supplierId = material.supplier_id && activeSuppliers.value.some(item => item.id === material.supplier_id) ? material.supplier_id : undefined }
async function submitInbound() { if (inboundSaving.value) return; inboundError.value = ''; if (!inbound.materialId || !inbound.supplierId || !positive(inbound.grossWeight)) { inboundError.value = '请选择物料、供应商，并输入大于零的实收重量。'; return } inboundSaving.value = true; try { const batch = await materialQrApi.createInbound({ material_id: inbound.materialId, supplier_id: inbound.supplierId, gross_weight: inbound.grossWeight, thickness: inbound.thickness, width: inbound.width, po_no: inbound.poNo.trim() || undefined }); inboundVisible.value = false; ElMessage.success('原材料已入库，等待 IQC 检验'); await loadBatches(); await showDetail(batch.id) } catch (error) { inboundError.value = errorText(error, '入库未成功，请核对资料后重试。') } finally { inboundSaving.value = false } }
function openIqc(batch: BatchRow) { iqcTarget.value = batch; iqc.result = 'passed'; iqc.notes = ''; iqcError.value = ''; iqcVisible.value = true }
async function refreshAfterWrite(id: number) { await loadBatches(); if (detailVisible.value && detailId.value === id) await showDetail(id) }
async function submitIqc() { if (iqcSaving.value || !iqcTarget.value) return; iqcSaving.value = true; iqcError.value = ''; const id = iqcTarget.value.id; try { await materialQrApi.updateIqc(id, { result: iqc.result, notes: iqc.notes.trim() || undefined }); iqcVisible.value = false; ElMessage.success('IQC 检验结果已保存'); await refreshAfterWrite(id) } catch (error) { iqcError.value = errorText(error, '检验结果未保存，请刷新批次后重试。') } finally { iqcSaving.value = false } }
function addSplit() { splitItems.value.push({ key: ++splitKey, weight: undefined, width: splitTarget.value?.width || undefined, length: splitTarget.value?.length || undefined }) }
function openSplit(batch: BatchRow) { splitTarget.value = batch; splitItems.value = []; addSplit(); splitError.value = ''; splitVisible.value = true }
async function submitSplit() { if (splitSaving.value || !splitTarget.value || !splitValid.value) return; splitSaving.value = true; splitError.value = ''; const id = splitTarget.value.id; try { const labels = await materialQrApi.split(id, { splits: splitItems.value.map(item => ({ weight: item.weight!, width: item.width, length: item.length })) }); splitVisible.value = false; printLabels.value = labels; printTitle.value = '分卷成功 · 子卷标签预览'; printError.value = ''; printVisible.value = true; ElMessage.success(`已生成 ${labels.length} 个子卷`); await refreshAfterWrite(id) } catch (error) { splitError.value = errorText(error, '分卷未成功，请刷新母卷余重后重试。') } finally { splitSaving.value = false } }
function qrImage(label: MaterialBatchScanResponse) { return label.qr_image_base64?.startsWith('data:image/png;base64,') ? label.qr_image_base64 : '' }
async function previewReprint(id: number) { if (printingId.value != null) return; printingId.value = id; try { const label = await materialQrApi.reprintQr(id); printLabels.value = [label]; printTitle.value = '原材料标签补打'; printError.value = qrImage(label) ? '' : '该批次没有可打印二维码，请核对原始资料。'; printVisible.value = true } catch (error) { ElMessage.error(errorText(error, '标签预览加载失败，请重试。')) } finally { printingId.value = null } }
async function printLabelsNow() { printError.value = ''; await nextTick(); const images = [...document.querySelectorAll<HTMLImageElement>('#material-qr-print-sheet img')]; try { await Promise.all(images.map(image => image.decode())); window.print() } catch { printError.value = '二维码图像未加载完成，请重新打开预览后重试。' } }
onMounted(() => { void authApi.current().then(actor => { actorLevel.value = actor.role_level }).catch(() => { actorLevel.value = 0 }); void loadCatalogs(); void loadBatches() })
</script>

<style scoped>
.material-qr-workspace { padding: 4px 0 16px; color: var(--zephyr-text); }
.page-header { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 18px; }
h1 { margin: 0; font-size: 22px; font-weight: 600; letter-spacing: -.02em; color: var(--zephyr-ink); }
.page-header p { margin: 4px 0 0; font-size: 12px; color: var(--zephyr-muted); }
.lookup-strip { display: flex; gap: 8px; align-items: center; padding: 12px 16px; background: var(--zephyr-primary-soft); border: 1px solid var(--zephyr-primary-border); border-radius: 8px; margin-bottom: 16px; }
.lookup-strip > .el-input { flex: 1; max-width: 660px; }
.notice { margin: 12px 0; }
.batch-panel { border: 1px solid var(--zephyr-border); border-radius: 8px; padding: 16px; background: var(--zephyr-surface); box-shadow: var(--zephyr-shadow-sm); }
.panel-toolbar, .filters, .page-summary, .pagination-row, .pagination-row > div { display: flex; align-items: center; gap: 12px; }
.panel-toolbar { justify-content: space-between; flex-wrap: wrap; margin-bottom: 12px; }
.filters .el-select { width: 190px; }.filters .el-select + .el-select { width: 140px; }
.page-summary { color: var(--zephyr-muted); font-size: 12px; gap: 20px; }.page-summary b { color: var(--zephyr-ink); font-weight: 600; font-variant-numeric: tabular-nums; }
.subline { display: block; color: var(--zephyr-muted); font-size: 11px; line-height: 1.6; }.batch-number { white-space: normal; text-align: left; font-family: var(--zephyr-font-mono); font-size: 12px; }
.pagination-row { justify-content: space-between; margin-top: 14px; color: var(--zephyr-muted); font-size: 12px; }.page-index { white-space: nowrap; }
.inline-error { color: var(--zephyr-danger); font-size: 12px; margin: 10px 0; overflow-wrap: anywhere; }.region-error { display: flex; align-items: center; justify-content: space-between; gap: 12px; background: var(--el-color-danger-light-9); padding: 10px 12px; border-radius: 6px; margin-bottom: 12px; color: var(--zephyr-danger); }
.form-intro { color: var(--zephyr-muted); font-size: 12px; margin: 0 0 16px; line-height: 1.7; }.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0 16px; }.form-grid .el-select, .form-grid .el-input-number { width: 100%; }.selected-batch { font: 600 13px var(--zephyr-font-mono); margin: 0 0 18px; overflow-wrap: anywhere; color: var(--zephyr-ink); }
.split-balance { display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap; border-block: 1px solid var(--zephyr-border-soft); padding: 12px 0; margin-bottom: 12px; font-size: 12px; }.split-balance b { font-variant-numeric: tabular-nums; }.split-balance .inline-error { margin: 0; }.split-editor { overflow-x: auto; }.split-row, .split-head { display: grid; grid-template-columns: 36px 1.2fr 1fr 1fr 42px; align-items: center; gap: 8px; min-width: 550px; }.split-head { font-size: 12px; color: var(--zephyr-muted); margin-bottom: 8px; }.split-row { margin-bottom: 10px; }.split-row .el-input-number { width: 100%; }.add-split { margin-top: 4px; }
.detail-content { min-height: 220px; }.detail-heading { display: flex; align-items: start; justify-content: space-between; gap: 16px; }.detail-heading h2 { font: 600 16px var(--zephyr-font-mono); overflow-wrap: anywhere; margin: 0 0 6px; color: var(--zephyr-ink); }.detail-heading span { color: var(--zephyr-muted); font-size: 12px; }.detail-facts { display: grid; grid-template-columns: repeat(4, 1fr); padding: 16px 0; margin: 16px 0; gap: 16px; border-block: 1px solid var(--zephyr-border-soft); }.detail-facts dt { color: var(--zephyr-muted); font-size: 12px; margin-bottom: 6px; }.detail-facts dd { margin: 0; color: var(--zephyr-ink); font-size: 22px; font-variant-numeric: tabular-nums; }.detail-facts dd small { font-size: 12px; font-weight: 400; color: var(--zephyr-muted); }.detail-facts .fact-small { font-size: 13px; padding-top: 7px; }.detail-actions { display: flex; gap: 8px; margin-bottom: 12px; }.detail-actions .el-button + .el-button { margin-left: 0; }.section-title { font-size: 13px; margin: 12px 0; font-weight: 600; }.section-title span { font-weight: 400; color: var(--zephyr-muted); margin-left: 8px; }.parent-link { display: flex; gap: 12px; flex-wrap: wrap; align-items: center; background: var(--zephyr-surface-muted); padding: 10px 12px; border-radius: 6px; font-size: 12px; }.parent-link > span { color: var(--zephyr-muted); }.qr-content { font: 11px var(--zephyr-font-mono); overflow-wrap: anywhere; }.identity-facts { display: grid; grid-template-columns: 160px 1fr; gap: 12px; margin: 12px 0; }.identity-facts dt { color: var(--zephyr-muted); font-size: 12px; }.identity-facts dd { margin: 0; white-space: pre-wrap; }
.label-preview { display: grid; gap: 12px; max-height: 55vh; overflow: auto; padding: 12px; background: var(--zephyr-canvas); border-radius: 8px; }.material-qr-label { display: flex; gap: 16px; padding: 16px; border: 1px solid var(--zephyr-border); background: white; border-radius: 6px; }.material-qr-label img { width: 144px; height: 144px; object-fit: contain; flex-shrink: 0; image-rendering: pixelated; }.material-qr-label h3 { font-size: 13px; margin: 0 0 8px; font-family: var(--zephyr-font-mono); overflow-wrap: anywhere; }.material-qr-label p { font-size: 12px; margin: 4px 0; }.material-qr-label code { display: block; font-size: 10px; overflow-wrap: anywhere; }
.lookup-strip { display: block; background: var(--zephyr-surface-muted); border-color: var(--zephyr-border-soft); padding: 10px 16px; }
.lookup-strip > summary, .label-identity > summary { cursor: pointer; color: var(--zephyr-muted); font-size: 12px; width: fit-content; }
.lookup-strip > summary:focus-visible, .label-identity > summary:focus-visible { outline: 2px solid var(--zephyr-primary); outline-offset: 3px; border-radius: 2px; }
.lookup-controls { display: flex; gap: 8px; align-items: center; padding-top: 12px; }
.lookup-controls > .el-input { flex: 1; max-width: 660px; }
.material-name { font-weight: 600; white-space: normal; text-align: left; }
.batch-number { color: var(--zephyr-muted); font: 11px var(--zephyr-font-mono); overflow-wrap: anywhere; }
.selected-batch { font-family: inherit; }
.selected-batch > strong { font-size: 15px; }.selected-batch > .subline { margin-top: 6px; font-family: var(--zephyr-font-mono); font-weight: 400; }
.detail-heading h2 { font-family: inherit; font-size: 19px; font-weight: 600; letter-spacing: -.01em; }
.detail-heading p { margin: 0 0 6px; font-size: 12px; color: var(--zephyr-muted); }
.label-information { flex: 1; min-width: 0; }
.material-qr-label h3 { font: 600 17px var(--zephyr-font); }
.material-qr-label .label-weight { margin: 10px 0; }.label-weight strong { font-size: 18px; font-variant-numeric: tabular-nums; }
.material-qr-label .label-batch { color: var(--zephyr-muted); font-size: 11px; overflow-wrap: anywhere; }
.label-identity { margin-top: 10px; }.label-identity code { margin-top: 6px; color: var(--zephyr-muted); }
@media (max-width: 900px) { .page-summary { width: 100%; }.detail-facts { grid-template-columns: 1fr 1fr; }.lookup-strip { flex-wrap: wrap; }.lookup-strip > .el-input { flex-basis: calc(100% - 110px); max-width: none; }.pagination-row { flex-wrap: wrap; }.filters { flex-wrap: wrap; } }
@media (max-width: 900px) { .lookup-controls { flex-wrap: wrap; }.lookup-controls > .el-input { flex-basis: calc(100% - 110px); max-width: none; } }
@media (max-width: 560px) { .page-header { align-items: start; }.batch-panel { padding: 12px; }.form-grid { grid-template-columns: 1fr; }.detail-actions { flex-wrap: wrap; }.material-qr-label { flex-direction: column; align-items: center; }.identity-facts { grid-template-columns: 1fr; gap: 6px; }.identity-facts dd { margin-bottom: 10px; } }
</style>

<style>
.material-qr-dialog { max-width: calc(100vw - 32px); }
#material-qr-print-sheet { display: none; }
@media print {
  body:has(#material-qr-print-sheet[data-print-active="true"]) { margin: 0; }
  body:has(#material-qr-print-sheet[data-print-active="true"]) > *:not(#material-qr-print-sheet) { display: none !important; }
  #material-qr-print-sheet[data-print-active="true"] { display: grid !important; grid-template-columns: 1fr 1fr; gap: 6mm; color: #000; font-family: 'Microsoft YaHei', sans-serif; }
  .material-qr-paper-label { display: flex; align-items: center; gap: 3mm; border: .2mm solid #000; padding: 3mm; min-height: 40mm; break-inside: avoid; box-sizing: border-box; }
  .material-qr-paper-label img { flex: 0 0 32mm; width: 32mm; height: 32mm; object-fit: contain; image-rendering: pixelated; }
  .material-qr-paper-label > div { flex: 1; min-width: 0; }.material-qr-paper-label h3 { margin: 0 0 2mm; font-size: 10pt; overflow-wrap: anywhere; }.material-qr-paper-label p { margin: 1mm 0; font-size: 7pt; overflow-wrap: anywhere; }.material-qr-paper-label .paper-weight { font-size: 9pt; font-variant-numeric: tabular-nums; margin: 2mm 0; }.material-qr-paper-label .paper-batch { font-size: 6pt; }.material-qr-paper-label code { display: block; font-size: 6pt; overflow-wrap: anywhere; }
}
</style>
