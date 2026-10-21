<template>
  <div v-loading="store.loading || store.busy" class="quality-v1">
    <header class="quality-page-header"><div><p class="quality-eyebrow">不良品 / 返工模</p><h1>返工模档案</h1><p class="quality-caption">记录做过的返工模，查询适用零件、存放位置与历次返工结果。</p></div><el-button v-if="store.can('mold')" type="primary" :icon="Plus" @click="openForm()">新增返工模</el-button></header>
    <el-alert v-if="store.loadError" :title="store.loadError" type="error" :closable="false"><el-button @click="store.reload">重试读取服务器台账</el-button></el-alert>
    <section class="quality-stats quality-mold-stats" aria-label="返工模概览"><article><span>返工模档案</span><strong>{{ store.molds.length }}<small>副</small></strong><p>按适用零件号建档</p></article><article><span>当前可用</span><strong>{{ store.molds.filter(row => row.availability === 'available').length }}<small>副</small></strong><p>开发查询后确认任务模具就绪</p></article><article><span>关联不良记录</span><strong>{{ relatedCount }}<small>条</small></strong><p>返工结果随品质验收更新</p></article></section>
    <section class="quality-panel"><div class="quality-toolbar quality-mold-toolbar"><el-input v-model="search" :prefix-icon="Search" clearable aria-label="搜索返工模" placeholder="搜索零件号或存放位置" /><el-select v-model="availability" clearable placeholder="可用状态" aria-label="筛选返工模状态"><el-option v-for="(label, key) in availabilityLabels" :key="key" :label="label" :value="key" /></el-select><span class="quality-toolbar-total">共 {{ filteredMolds.length }} 副返工模</span></div>
      <el-table :data="filteredMolds" row-key="id" @row-click="openDetail">
        <el-table-column label="照片" width="85"><template #default="{ row }"><el-image v-if="row.photos.length" class="quality-mold-thumbnail" :src="row.photos[0]" fit="cover" :preview-src-list="row.photos" preview-teleported @click.stop /><span v-else class="quality-photo-placeholder"><el-icon><Picture /></el-icon></span></template></el-table-column>
        <el-table-column label="适用零件号" min-width="190"><template #default="{ row }"><button type="button" class="quality-part-link" @click.stop="openDetail(row)">{{ row.partNo }}</button><div class="quality-secondary">{{ partDescription(row.partNo) }}</div></template></el-table-column>
        <el-table-column label="存放位置" prop="location" min-width="200"><template #default="{ row }">{{ row.location || '未填写' }}</template></el-table-column>
        <el-table-column label="可用状态" width="130"><template #default="{ row }"><el-tag :type="row.availability === 'available' ? 'success' : 'warning'" size="small">{{ availabilityLabels[row.availability as ReworkMold['availability']] }}</el-tag></template></el-table-column>
        <el-table-column label="关联记录 / 返工结果" min-width="230"><template #default="{ row }"><span>{{ row.defectIds.length }} 条不良记录</span><div class="quality-secondary">{{ moldResult(row) }}</div></template></el-table-column>
        <el-table-column label="操作" width="130" fixed="right"><template #default="{ row }"><el-button link type="primary" @click.stop="openDetail(row)">详情</el-button><el-button v-if="store.can('mold')" link type="primary" @click.stop="openForm(row)">编辑</el-button></template></el-table-column>
        <template #empty><el-empty description="暂无符合条件的返工模"><el-button v-if="store.can('mold')" @click="openForm()">建立返工模档案</el-button></el-empty></template>
      </el-table><div class="quality-table-footer"><span>关联记录用于追溯返工结果，模具是否就绪由开发在对应任务中确认。</span></div>
    </section>

    <el-drawer v-model="detailVisible" :title="selected ? `${selected.partNo} · 返工模详情` : '返工模详情'" size="min(690px, 100vw)" class="quality-drawer">
      <template v-if="selected"><section class="quality-detail-section"><h3>返工模信息</h3><dl class="quality-details-grid"><div><dt>零件号</dt><dd class="quality-number">{{ selected.partNo }}</dd></div><div><dt>可用状态</dt><dd><el-tag :type="selected.availability === 'available' ? 'success' : 'warning'" size="small">{{ availabilityLabels[selected.availability] }}</el-tag></dd></div><div><dt>存放位置</dt><dd>{{ selected.location || '未填写' }}</dd></div></dl></section><section class="quality-detail-section"><h3>照片</h3><div v-if="selected.photos.length" class="quality-photo-gallery"><el-image v-for="(photo, index) in selected.photos" :key="index" :src="photo" :preview-src-list="selected.photos" :initial-index="index" fit="cover" preview-teleported :alt="`${selected.partNo} 返工模照片 ${index + 1}`" /></div><div v-else class="quality-photo-empty"><el-icon><Picture /></el-icon><span>尚未添加照片</span></div></section><section class="quality-detail-section"><h3>关联不良记录及返工结果 <small>{{ linkedRecords.length }} 条</small></h3><div v-for="record in linkedRecords" :key="record.id" class="quality-linked-record"><div><router-link :to="{ path: '/nonconforming', query: { record: record.id } }">{{ record.no }} <el-icon><ArrowRight /></el-icon></router-link><el-tag size="small">{{ statusLabels[record.status] }}</el-tag></div><p>{{ record.customer }} · {{ record.description }}</p><div class="quality-linked-results"><span>不良 {{ number(record.quantity) }} 件</span><span>验收合格 {{ number(record.acceptedQty) }} 件</span><span>剩余 {{ number(remainingQty(record)) }} 件</span></div><p v-if="record.actualDate" class="quality-secondary">实际完成 {{ record.actualDate }}</p></div><el-empty v-if="!linkedRecords.length" description="尚未关联不良记录" :image-size="65" /></section></template>
      <template #footer><el-button @click="detailVisible = false">关闭</el-button><el-button v-if="selected && store.can('mold')" type="primary" @click="openForm(selected)">编辑返工模</el-button></template>
    </el-drawer>

    <el-dialog v-model="formVisible" :title="form.id ? '编辑返工模档案' : '新增返工模'" width="min(650px, 94vw)" class="quality-dialog" :close-on-click-modal="false"><el-form label-position="top" @submit.prevent="saveForm"><el-form-item label="零件号" required><el-autocomplete v-model="form.partNo" :fetch-suggestions="suggestParts" placeholder="输入适用零件号" @input="clearInvalidLinks" /></el-form-item><div class="quality-form-grid"><el-form-item label="存放位置"><el-input v-model="form.location" placeholder="如：返工模架 A-01" maxlength="100" /></el-form-item><el-form-item label="可用状态" required><el-select v-model="form.availability"><el-option v-for="(label, key) in availabilityLabels" :key="key" :label="label" :value="key" /></el-select></el-form-item></div><el-form-item label="关联不良记录"><el-select v-model="form.defectIds" multiple filterable placeholder="选择此零件的返工记录"><el-option v-for="record in linkOptions" :key="record.id" :label="`${record.no} · ${record.customer} · ${statusLabels[record.status]}`" :value="record.id" /></el-select><div class="quality-field-help">仅关联同一零件号的返工记录；结果从对应记录汇总。</div></el-form-item><el-form-item label="照片"><div class="quality-photo-editor"><div v-for="(photo, index) in form.photos" :key="index" class="quality-photo-edit-item"><img :src="photo" :alt="`返工模照片 ${index + 1}`" /><button type="button" :aria-label="`移除照片 ${index + 1}`" @click="form.photos.splice(index, 1)"><el-icon><Close /></el-icon></button></div><label v-if="form.photos.length < 4" class="quality-photo-upload" for="rework-mold-photos"><el-icon><Plus /></el-icon><span>{{ uploading ? '读取中…' : '添加照片' }}</span><input id="rework-mold-photos" type="file" accept="image/jpeg,image/png,image/webp" multiple :disabled="uploading" @change="readPhotos" /></label></div><div class="quality-field-help">最多 4 张，每张不超过 500KB，支持 JPG、PNG、WebP。</div></el-form-item><el-alert v-if="formError" :title="formError" type="error" :closable="false" show-icon /></el-form><template #footer><el-button @click="formVisible = false">取消</el-button><el-button type="primary" :disabled="uploading" @click="saveForm">保存返工模</el-button></template></el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { ArrowRight, Close, Picture, Plus, Search } from '@element-plus/icons-vue'
import { useNonconformingPreview } from '@/stores/nonconformingPreview'
import { useCompanyStore } from '@/stores/company'
import { hasReworkHistory, remainingQty, statusLabels, type ReworkMold } from '@/domain/nonconforming'
import '@/styles/nonconforming.css'

const store = useNonconformingPreview(); const company = useCompanyStore()
onMounted(() => { void store.reload() })
const search = ref(''); const availability = ref('')
const availabilityLabels = { available: '可用', maintenance: '维修中', unavailable: '不可用' }
const number = (value: number) => new Intl.NumberFormat('zh-CN').format(value)
const filteredMolds = computed(() => store.molds.filter(row => (!search.value || `${row.partNo} ${row.location}`.toLowerCase().includes(search.value.trim().toLowerCase())) && (!availability.value || row.availability === availability.value)))
const relatedCount = computed(() => new Set(store.molds.flatMap(row => row.defectIds)).size)
const partDescription = (partNo: string) => { const row = store.records.find(record => record.partNo === partNo); return row ? `${row.customer} · ${row.partName}` : '返工模' }
const moldResult = (mold: ReworkMold) => { const linked = store.records.filter(row => mold.defectIds.includes(row.id)); return linked.length ? `验收合格 ${number(linked.reduce((sum, row) => sum + row.acceptedQty, 0))} 件 · 已关闭 ${linked.filter(row => row.status === 'closed').length} 条` : '尚未关联返工结果' }
const detailVisible = ref(false); const selectedId = ref(''); const selected = computed(() => store.molds.find(row => row.id === selectedId.value))
const linkedRecords = computed(() => store.records.filter(row => selected.value?.defectIds.includes(row.id)))
function openDetail(row: ReworkMold) { selectedId.value = row.id; detailVisible.value = true }
const blankMold = (): ReworkMold => ({ id: '', company: company.selectedCompany, partNo: '', location: '', availability: 'available', photos: [], defectIds: [] })
const form = reactive<ReworkMold>(blankMold()); const formVisible = ref(false); const formError = ref(''); const uploading = ref(false)
function openForm(row?: ReworkMold) { Object.assign(form, row ? JSON.parse(JSON.stringify(row)) : blankMold()); formError.value = ''; formVisible.value = true }
const linkOptions = computed(() => store.records.filter(row => row.partNo === form.partNo && hasReworkHistory(row)))
function clearInvalidLinks() { form.defectIds = form.defectIds.filter(id => linkOptions.value.some(row => row.id === id)) }
function suggestParts(query: string, callback: (items: Array<{ value: string }>) => void) { const parts = new Set([...store.records.map(row => row.partNo), ...store.molds.map(row => row.partNo)]); callback([...parts].filter(part => part.toLowerCase().includes(query.toLowerCase())).slice(0, 15).map(value => ({ value }))) }
async function readPhotos(event: Event) {
  const input = event.target as HTMLInputElement; const files = Array.from(input.files || []); formError.value = ''
  if (files.length + form.photos.length > 4) { formError.value = '最多保存四张照片'; input.value = ''; return }
  if (files.some(file => !['image/jpeg', 'image/png', 'image/webp'].includes(file.type) || file.size > 500 * 1024)) { formError.value = '请选择不超过 500KB 的 JPG、PNG 或 WebP 照片'; input.value = ''; return }
  uploading.value = true
  try { const photos = await Promise.all(files.map(file => new Promise<string>((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(String(reader.result)); reader.onerror = () => reject(new Error('照片读取失败，请重新选择')); reader.readAsDataURL(file) }))); form.photos.push(...photos) }
  catch (error) { formError.value = error instanceof Error ? error.message : '照片读取失败' }
  finally { uploading.value = false; input.value = '' }
}
async function saveForm() { try { await store.saveMold(JSON.parse(JSON.stringify(form))); formVisible.value = false; ElMessage.success('返工模档案已保存') } catch (error) { formError.value = error instanceof Error ? error.message : '保存失败' } }
</script>
