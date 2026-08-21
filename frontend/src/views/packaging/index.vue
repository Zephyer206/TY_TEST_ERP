<template>
  <div class="packaging-container">
    <div class="list-view-toolbar">
      <div class="list-title-block">
        <el-button type="primary" @click="openCreate"><el-icon><Plus /></el-icon>包装登记</el-button>
        <h1>包装</h1>
      </div>
      <div class="search-control"><el-icon><Search /></el-icon><el-input v-model="filter.search" placeholder="搜索包装号、零件编号或零件名称" clearable /></div>
      <div class="filter-controls">
        <el-select v-model="filter.status" placeholder="状态" clearable><el-option v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select>
        <el-button @click="fetchRecords">筛选</el-button>
        <el-button text @click="resetFilter">重置</el-button>
        <el-button class="view-toggle" text circle aria-label="列表视图" title="列表视图"><el-icon><Menu /></el-icon></el-button>
      </div>
    </div>

    <div class="record-summary">
      <span>{{ filteredRecords.length }} 条记录</span>
      <span>待检 {{ recordCounts.scanned }} · 已入库 {{ recordCounts.passed }} · 不合格 {{ recordCounts.rejected }}</span>
    </div>

    <el-table :data="pagedRecords" v-loading="loading" stripe>
      <el-table-column prop="package_no" label="包装号" min-width="180" />
      <el-table-column label="零件" min-width="200"><template #default="{ row }"><span>{{ partLabel(row) }}</span></template></el-table-column>
      <el-table-column prop="box_no" label="箱号" min-width="130"><template #default="{ row }">{{ row.box_no || '-' }}</template></el-table-column>
      <el-table-column prop="package_qty" label="包装数量" width="110" align="right"><template #default="{ row }">{{ row.package_qty }} 件</template></el-table-column>
      <el-table-column label="状态" width="110" align="center"><template #default="{ row }"><el-tag :type="statusType(row.status)">{{ statusLabel(row.status) }}</el-tag></template></el-table-column>
      <el-table-column label="登记时间" min-width="160"><template #default="{ row }">{{ formatDate(row.scanned_at) }}</template></el-table-column>
      <el-table-column label="全检时间" min-width="160"><template #default="{ row }">{{ formatDate(row.inspected_at) }}</template></el-table-column>
      <el-table-column label="操作" width="120" fixed="right"><template #default="{ row }"><el-button v-if="row.status === 'scanned'" link type="primary" size="small" @click="openInspect(row)">全检</el-button><el-button v-else link type="primary" size="small" @click="openDetail(row)">查看</el-button></template></el-table-column>
    </el-table>

    <div class="pagination"><el-pagination v-model:current-page="page.current" v-model:page-size="page.size" :total="filteredRecords.length" :page-sizes="[20, 50, 100]" layout="total, sizes, prev, pager, next" @size-change="page.current = 1" /></div>

    <el-dialog v-model="createVisible" title="包装登记" width="540px" destroy-on-close>
      <el-form ref="createFormRef" :model="createForm" :rules="createRules" label-width="88px">
        <el-form-item label="零件" prop="part_id"><el-select v-model="createForm.part_id" filterable placeholder="搜索并选择零件" style="width: 100%"><el-option v-for="part in partChoices" :key="part.id" :value="part.id" :label="partOptionLabel(part)" /></el-select></el-form-item>
        <el-form-item label="包装数量" prop="package_qty"><el-input-number v-model="createForm.package_qty" :min="1" controls-position="right" style="width: 100%" /></el-form-item>
        <el-form-item label="箱号"><el-input v-model="createForm.box_no" placeholder="选填" /></el-form-item>
        <el-form-item label="备注"><el-input v-model="createForm.notes" type="textarea" :rows="3" placeholder="选填" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="createVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="createRecord">登记</el-button></template>
    </el-dialog>

    <el-dialog v-model="inspectVisible" title="包装全检" width="500px" destroy-on-close>
      <el-descriptions :column="1" border class="inspect-record"><el-descriptions-item label="包装号">{{ activeRecord?.package_no }}</el-descriptions-item><el-descriptions-item label="零件">{{ activeRecord ? partLabel(activeRecord) : '-' }}</el-descriptions-item><el-descriptions-item label="数量">{{ activeRecord?.package_qty }} 件</el-descriptions-item></el-descriptions>
      <el-form ref="inspectFormRef" :model="inspectForm" :rules="inspectRules" label-width="88px" class="dialog-form"><el-form-item label="全检结果" prop="passed"><el-radio-group v-model="inspectForm.passed"><el-radio :value="true">合格入库</el-radio><el-radio :value="false">不合格</el-radio></el-radio-group></el-form-item><el-form-item label="检验备注"><el-input v-model="inspectForm.notes" type="textarea" :rows="3" placeholder="选填" /></el-form-item></el-form>
      <template #footer><el-button @click="inspectVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="submitInspection">确认全检</el-button></template>
    </el-dialog>

    <el-dialog v-model="detailVisible" title="包装记录" width="520px"><el-descriptions v-if="activeRecord" :column="1" border><el-descriptions-item label="包装号">{{ activeRecord.package_no }}</el-descriptions-item><el-descriptions-item label="零件">{{ partLabel(activeRecord) }}</el-descriptions-item><el-descriptions-item label="箱号">{{ activeRecord.box_no || '-' }}</el-descriptions-item><el-descriptions-item label="数量">{{ activeRecord.package_qty }} 件</el-descriptions-item><el-descriptions-item label="状态">{{ statusLabel(activeRecord.status) }}</el-descriptions-item><el-descriptions-item label="登记时间">{{ formatDate(activeRecord.scanned_at) }}</el-descriptions-item><el-descriptions-item label="全检备注">{{ activeRecord.inspection_notes || '-' }}</el-descriptions-item></el-descriptions></el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Menu, Plus, Search } from '@element-plus/icons-vue'
import { get, post } from '@/utils/request'

type PackageStatus = 'scanned' | 'inspecting' | 'passed' | 'rejected' | 'shipped'
type PackagingRecord = { id: number; package_no: string; part_id: number; part_number?: string | null; part_name?: string | null; package_qty: number; box_no?: string | null; status: PackageStatus; inspected_at?: string | null; inspection_notes?: string | null; scanned_at: string }
type PartChoice = { id: number; part_number?: string | null; internal_name?: string | null; customer_product_no?: string | null }

const loading = ref(false)
const saving = ref(false)
const createVisible = ref(false)
const inspectVisible = ref(false)
const detailVisible = ref(false)
const createFormRef = ref()
const inspectFormRef = ref()
const records = ref<PackagingRecord[]>([])
const partChoices = ref<PartChoice[]>([])
const activeRecord = ref<PackagingRecord | null>(null)
const filter = reactive({ search: '', status: '' })
const page = reactive({ current: 1, size: 20 })
const createForm = reactive({ part_id: undefined as number | undefined, package_qty: 1, box_no: '', notes: '' })
const inspectForm = reactive({ passed: true, notes: '' })
const statusOptions = [{ value: 'scanned', label: '待全检' }, { value: 'passed', label: '已入库' }, { value: 'rejected', label: '不合格' }, { value: 'shipped', label: '已发货' }]
const createRules = { part_id: [{ required: true, message: '请选择零件', trigger: 'change' }], package_qty: [{ required: true, message: '请输入包装数量', trigger: 'blur' }] }
const inspectRules = { passed: [{ required: true, message: '请选择全检结果', trigger: 'change' }] }

const filteredRecords = computed(() => {
  const keyword = filter.search.trim().toLowerCase()
  return records.value.filter(record => !keyword || [record.package_no, record.part_number, record.part_name].some(value => value?.toLowerCase().includes(keyword)))
})
const pagedRecords = computed(() => filteredRecords.value.slice((page.current - 1) * page.size, page.current * page.size))
const recordCounts = computed(() => ({ scanned: records.value.filter(item => item.status === 'scanned').length, passed: records.value.filter(item => item.status === 'passed').length, rejected: records.value.filter(item => item.status === 'rejected').length }))
const partLabel = (record: PackagingRecord) => record.part_number ? `${record.part_number}${record.part_name ? ` ${record.part_name}` : ''}` : (record.part_name || '未命名零件')
const partOptionLabel = (part: PartChoice) => part.part_number ? `${part.part_number}${part.internal_name ? ` ${part.internal_name}` : ''}` : (part.internal_name || part.customer_product_no || '未命名零件')
const statusLabel = (status: PackageStatus) => ({ scanned: '待全检', inspecting: '检验中', passed: '已入库', rejected: '不合格', shipped: '已发货' }[status] || status)
const statusType = (status: PackageStatus) => ({ scanned: 'warning', inspecting: 'primary', passed: 'success', rejected: 'danger', shipped: 'info' }[status] || 'info')
const formatDate = (value?: string | null) => value ? new Date(value).toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) : '-'

const fetchRecords = async () => { loading.value = true; try { records.value = await get<PackagingRecord[]>('/packaging/records', { status: filter.status || undefined, skip: 0, limit: 100 }); page.current = 1 } catch (error: any) { records.value = []; ElMessage.error(error?.message || '获取包装记录失败') } finally { loading.value = false } }
const resetFilter = () => { Object.assign(filter, { search: '', status: '' }); fetchRecords() }
const loadPartChoices = async () => { try { const items = await get<PartChoice[]>('/parts', { skip: 0, limit: 500 }); partChoices.value = Array.isArray(items) ? items : [] } catch { partChoices.value = [] } }
const openCreate = async () => { Object.assign(createForm, { part_id: undefined, package_qty: 1, box_no: '', notes: '' }); createVisible.value = true; if (!partChoices.value.length) await loadPartChoices() }
const openInspect = (record: PackagingRecord) => { activeRecord.value = record; Object.assign(inspectForm, { passed: true, notes: '' }); inspectVisible.value = true }
const openDetail = (record: PackagingRecord) => { activeRecord.value = record; detailVisible.value = true }
const createRecord = async () => { await createFormRef.value?.validate(); saving.value = true; try { await post('/packaging/scan', { part_id: createForm.part_id, package_qty: createForm.package_qty, box_no: createForm.box_no || null, notes: createForm.notes || null }); ElMessage.success('包装已登记'); createVisible.value = false; await fetchRecords() } catch (error: any) { ElMessage.error(error?.message || '包装登记失败') } finally { saving.value = false } }
const submitInspection = async () => { if (!activeRecord.value) return; await inspectFormRef.value?.validate(); saving.value = true; try { await post(`/packaging/inspect/${activeRecord.value.id}`, inspectForm); ElMessage.success('全检结果已保存'); inspectVisible.value = false; await fetchRecords() } catch (error: any) { ElMessage.error(error?.message || '全检失败') } finally { saving.value = false } }

onMounted(fetchRecords)
</script>

<style scoped>
.packaging-container { min-width: 0; padding: 20px; }
.list-view-toolbar { display: grid; grid-template-columns: auto minmax(240px, 1fr) auto; align-items: center; gap: 14px; min-height: 58px; margin-bottom: 10px; padding: 8px 0; }
.list-title-block { display: flex; align-items: center; gap: 10px; min-width: 150px; }.list-title-block h1 { margin: 0; color: #4a4850; font-size: 20px; font-weight: 600; }
.search-control { display: flex; align-items: center; gap: 8px; width: min(480px, 100%); padding: 4px 10px; border: 1px solid #cbc9d1; border-radius: 3px; background: #fff; color: #7a7782; }.search-control :deep(.el-input__wrapper) { padding: 0; box-shadow: none; }
.filter-controls { display: flex; align-items: center; justify-content: flex-end; gap: 6px; }.filter-controls :deep(.el-select) { width: 116px; }.view-toggle { color: #625780; }
.record-summary { display: flex; justify-content: space-between; margin: 0 0 8px; color: #777580; font-size: 12px; }.record-summary span:last-child { color: #96939e; }.pagination { display: flex; justify-content: flex-end; margin-top: 16px; }.dialog-form { margin-top: 18px; }
@media (max-width: 960px) { .list-view-toolbar { grid-template-columns: 1fr; }.filter-controls { justify-content: flex-start; flex-wrap: wrap; } }
</style>
