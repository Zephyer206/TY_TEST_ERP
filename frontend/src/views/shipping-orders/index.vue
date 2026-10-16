<template>
  <div class="shipping-page">
    <div class="page-head">
      <div><p class="eyebrow">DELIVERY WORKFLOW</p><h1>发货订单</h1><p class="subhead">从业务下单到标签确认和仓库发货的统一入口。</p></div>
      <el-button type="primary" @click="openCreate"><el-icon><Plus /></el-icon>新建发货订单</el-button>
    </div>
    <div class="filters">
      <el-input v-model="filters.po_no" clearable placeholder="搜索 PO 号" @keyup.enter="loadOrders"><template #prefix><Search /></template></el-input>
      <el-select v-model="filters.order_type" clearable placeholder="订单类型" @change="loadOrders"><el-option label="正式订单" value="formal" /><el-option label="样件订单" value="sample" /></el-select>
      <el-select v-model="filters.status" clearable placeholder="订单状态" @change="loadOrders"><el-option v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select>
      <el-button @click="loadOrders">查询</el-button>
    </div>
    <el-table :data="orders" v-loading="loading" stripe @row-click="openDetail">
      <el-table-column prop="order_no" label="订单号" min-width="190" />
      <el-table-column label="客户 / PO" min-width="220"><template #default="{ row }"><strong>{{ row.temporary_customer_name || customerName(row.customer_id) || '未指定客户' }}</strong><span class="muted">{{ row.po_no || '样件无 PO' }}</span></template></el-table-column>
      <el-table-column label="类型" width="100"><template #default="{ row }"><el-tag size="small" :type="row.order_type === 'sample' ? 'warning' : 'success'">{{ row.order_type === 'sample' ? '样件' : '正式' }}</el-tag></template></el-table-column>
      <el-table-column label="明细" width="90"><template #default="{ row }">{{ row.lines?.length || 0 }} 行</template></el-table-column>
      <el-table-column label="状态" width="150"><template #default="{ row }"><el-tag :type="statusType(row.status)">{{ statusLabel(row.status) }}</el-tag></template></el-table-column>
      <el-table-column label="最后修改" min-width="170"><template #default="{ row }">{{ formatDate(row.last_modified_at) }}</template></el-table-column>
      <el-table-column label="操作" width="110" fixed="right"><template #default="{ row }"><el-button link type="primary" @click.stop="openDetail(row)">查看</el-button></template></el-table-column>
    </el-table>

    <el-dialog v-model="createVisible" title="新建发货订单" width="960px" destroy-on-close>
      <el-form :model="form" label-width="100px" class="order-form">
        <div class="form-grid">
          <el-form-item label="订单类型"><el-radio-group v-model="form.order_type"><el-radio-button value="formal">正式订单</el-radio-button><el-radio-button value="sample">样件订单</el-radio-button></el-radio-group></el-form-item>
          <el-form-item label="客户"><el-input v-model.number="form.customer_id" placeholder="输入客户 ID；样件可留空" /></el-form-item>
          <el-form-item v-if="form.order_type === 'sample'" label="临时客户"><el-input v-model="form.temporary_customer_name" placeholder="样件客户名称" /></el-form-item>
          <el-form-item label="PO 号"><el-input v-model="form.po_no" :placeholder="form.order_type === 'sample' ? '样件可留空' : '正式订单必填'" /></el-form-item>
        </div>
        <div class="line-head"><span>订单明细</span><el-button link type="primary" @click="addLine"><el-icon><Plus /></el-icon>新增明细</el-button></div>
        <div v-for="(line, index) in form.lines" :key="line.key" class="line-row">
          <el-input v-model="line.customer_part_no" placeholder="客户件号" @input="searchParts(Number(index))" @keydown.tab="tabComplete(Number(index))"><template #suffix><el-icon v-if="line.searching" class="is-loading"><Loading /></el-icon></template></el-input>
          <el-select v-model="line.selectedAlias" filterable remote reserve-keyword :remote-method="(query: string) => searchParts(Number(index), query)" placeholder="下拉选择 / Tab 补全" @change="selectPart(Number(index), $event)"><el-option v-for="option in line.options" :key="option.part_customer_alias_id" :label="`${option.customer_part_no} · 可用 ${option.inventory_available_qty ?? 0} 件${option.inventory_location ? ` · ${option.inventory_location}` : ''}`" :value="option" /></el-select>
          <el-input v-model="line.part_name" placeholder="零件名称（默认档案，可修改）" />
          <el-input-number v-model="line.ordered_qty" :min="1" controls-position="right" />
          <el-date-picker v-model="line.planned_ship_date" type="date" value-format="YYYY-MM-DD" placeholder="计划发货日" />
          <el-input v-model="line.remark" placeholder="备注" />
          <el-button text type="danger" aria-label="删除明细" @click="removeLine(Number(index))">删除</el-button>
        </div>
      </el-form>
      <template #footer><el-button @click="createVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="saveDraft">保存草稿</el-button><el-button type="success" :loading="saving" @click="saveAndSubmit">保存并提交</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Loading, Plus, Search } from '@element-plus/icons-vue'
import { createShippingOrder, getShippingOrder, listShippingOrders, searchCustomerParts, submitShippingOrder, updateShippingOrder } from '@/api/shippingOrders'

const route = useRoute(); const router = useRouter(); const loading = ref(false); const saving = ref(false); const createVisible = ref(false); const editingId = ref<number | null>(null)
const orders = ref<any[]>([]); const customers = ref<Record<number, string>>({})
const filters = reactive({ po_no: '', order_type: '', status: '' })
const statusOptions = [{ value: 'draft', label: '草稿' }, { value: 'pending', label: '待处理' }, { value: 'ready_to_ship', label: '待发货' }, { value: 'partially_shipped', label: '部分发货' }, { value: 'completed', label: '已完成' }, { value: 'cancelled', label: '已取消' }]
const newLine = () => ({ key: `${Date.now()}-${Math.random()}`, customer_part_no: '', part_name: '', part_id: null, part_customer_alias_id: null, inventory_available_qty: 0, inventory_location: null, ordered_qty: 1, planned_ship_date: '', remark: '', selectedAlias: null as any, options: [] as any[], searching: false })
const form = reactive<any>({ order_type: 'formal', customer_id: null, temporary_customer_name: '', po_no: '', lines: [newLine()] })
const customerName = (id: number) => customers.value[id]
const formatDate = (value?: string) => value ? new Date(value).toLocaleString('zh-CN') : '-'
const statusLabel = (value: string) => statusOptions.find(item => item.value === value)?.label || value
const statusType = (value: string) => ({ draft: 'info', pending: 'warning', ready_to_ship: 'success', partially_shipped: 'warning', completed: 'success', cancelled: 'danger' } as any)[value] || 'info'
const loadOrders = async () => { loading.value = true; try { const result: any = await listShippingOrders({ ...filters }); orders.value = result.items || [] } catch (error: any) { ElMessage.error(error?.message || '订单加载失败') } finally { loading.value = false } }
const openCreate = () => { editingId.value = null; Object.assign(form, { order_type: 'formal', customer_id: null, temporary_customer_name: '', po_no: '', lines: [newLine()] }); createVisible.value = true }
const openEdit = async (id: number) => { const data: any = await getShippingOrder(id); editingId.value = id; Object.assign(form, { order_type: data.order_type, customer_id: data.customer_id, temporary_customer_name: data.temporary_customer_name || '', po_no: data.po_no || '', lines: (data.lines || []).map((line: any) => ({ ...newLine(), customer_part_no: line.customer_part_no_snapshot, part_name: line.part_name_snapshot, part_id: line.part_id, part_customer_alias_id: line.part_customer_alias_id, ordered_qty: line.ordered_qty, planned_ship_date: line.planned_ship_date, remark: line.remark || '' })) }); createVisible.value = true }
const addLine = () => form.lines.push(newLine()); const removeLine = (index: number) => { if (form.lines.length > 1) form.lines.splice(index, 1) }
const searchParts = async (index: number, query?: string) => { const line = form.lines[index]; const value = (query ?? line.customer_part_no).trim(); if (!form.customer_id || value.length < 1) { line.options = []; return }; line.searching = true; try { line.options = await searchCustomerParts(form.customer_id, value) } catch { line.options = [] } finally { line.searching = false } }
const tabComplete = (index: number) => { const line = form.lines[index]; if (!line.selectedAlias && line.options.length === 1) selectPart(index, line.options[0]) }
const selectPart = (index: number, option: any) => { const line = form.lines[index]; if (!option) return; line.selectedAlias = option; line.customer_part_no = option.customer_part_no; line.part_id = option.part_id; line.part_customer_alias_id = option.part_customer_alias_id; line.inventory_available_qty = option.inventory_available_qty ?? 0; line.inventory_location = option.inventory_location || null; if (!line.part_name) line.part_name = option.part_name || option.customer_part_name || '' }
const payload = () => ({ order_type: form.order_type, customer_id: form.customer_id || null, temporary_customer_name: form.temporary_customer_name || null, po_no: form.po_no || null, lines: form.lines.map((line: any) => ({ customer_part_no: line.customer_part_no, part_id: line.part_id, part_customer_alias_id: line.part_customer_alias_id, part_name: line.part_name, ordered_qty: line.ordered_qty, planned_ship_date: line.planned_ship_date, remark: line.remark || null })) })
const saveDraft = async () => { saving.value = true; try { const result: any = editingId.value ? await updateShippingOrder(editingId.value, payload()) : await createShippingOrder(payload()); ElMessage.success('草稿已保存'); createVisible.value = false; await loadOrders(); router.push(`/shipping-orders/${result.id}`) } catch (error: any) { ElMessage.error(error?.message || '保存失败') } finally { saving.value = false } }
const saveAndSubmit = async () => { saving.value = true; try { const result: any = editingId.value ? await updateShippingOrder(editingId.value, payload()) : await createShippingOrder(payload()); try { await submitShippingOrder(result.id, {}) } catch (error: any) { const detail = error?.response?.data?.detail; if (detail?.code === 'DUPLICATE_CUSTOMER_PO' || detail?.code === 'UNREGISTERED_CUSTOMER_PARTS') { await ElMessageBox.confirm(detail.message, '提交提醒'); const confirmPayload = { confirm_duplicate_po: detail.code === 'DUPLICATE_CUSTOMER_PO', confirm_unregistered_customer_parts: detail.code === 'UNREGISTERED_CUSTOMER_PARTS' }; await submitShippingOrder(result.id, confirmPayload) } else throw error }; ElMessage.success('订单已提交'); createVisible.value = false; await loadOrders(); router.push(`/shipping-orders/${result.id}`) } catch (error: any) { ElMessage.error(error?.response?.data?.detail?.message || error?.message || '提交失败') } finally { saving.value = false } }
const openDetail = (row: any) => router.push(`/shipping-orders/${row.id}`)
onMounted(async () => { await loadOrders(); if (route.query.edit) await openEdit(Number(route.query.edit)) })
</script>

<style scoped>
.shipping-page { padding: 22px; min-width: 0; }
.page-head { display: flex; justify-content: space-between; align-items: center; gap: 16px; margin-bottom: 16px; }
.eyebrow { margin: 0 0 4px; color: var(--zephyr-primary); font-size: 11px; font-weight: 700; letter-spacing: .08em; }
.page-head h1 { margin: 0; color: var(--zephyr-ink); font-size: 26px; }
.subhead { margin: 6px 0 0; color: #748087; font-size: 13px; }
.filters { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; padding: 12px; border: 1px solid var(--zephyr-border); border-radius: 8px; background: var(--zephyr-surface); }
.filters .el-input { width: 230px; }
.filters .el-select { width: 150px; }
.muted { display: block; margin-top: 4px; color: #879197; font-size: 12px; }
.order-form { max-height: 60vh; overflow: auto; }
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 4px 18px; }
.line-head { display: flex; justify-content: space-between; align-items: center; margin: 12px 0 8px; font-weight: 650; }
.line-row { display: grid; grid-template-columns: 1fr 1.1fr 1.5fr 125px 160px 1fr 44px; gap: 6px; align-items: center; margin-bottom: 8px; }
.line-row .el-input-number, .line-row .el-date-editor { width: 100%; }
@media (max-width: 1100px) { .line-row { grid-template-columns: 1fr 1fr 1fr 110px 150px; }.line-row > :nth-child(6) { grid-column: span 2; } }
@media (max-width: 700px) { .page-head, .filters { flex-direction: column; }.filters .el-input, .filters .el-select { width: 100%; }.form-grid { grid-template-columns: 1fr; }.line-row { grid-template-columns: 1fr 1fr; }.line-row > :nth-child(3), .line-row > :nth-child(6) { grid-column: span 2; } }
</style>
