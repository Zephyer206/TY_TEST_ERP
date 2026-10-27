<template>
  <main class="qr-workspace">
    <header class="page-heading">
      <div><h1>产品框管理</h1><p>查看产品、订单、数量与工艺，扫码可快速定位。</p></div>
      <el-button :aria-expanded="labelsOpen" aria-controls="product-label-manager" @click="labelsOpen = !labelsOpen">标签管理</el-button>
    </header>
    <el-alert v-if="pageError" :title="pageError" type="error" :closable="false" show-icon class="page-alert">
      <template #default><el-button link @click="loadPool">重新加载</el-button></template>
    </el-alert>
    <details class="scan-strip">
      <summary>扫码快速定位</summary>
      <div class="scan-controls" aria-label="扫码查询">
      <label for="product-qr-scan">快速定位</label>
      <el-input id="product-qr-scan" ref="scanInput" v-model="scanText" placeholder="扫描或粘贴标签二维码，按回车查询" clearable :disabled="scanning" @keyup.enter="scan" />
      <el-button :loading="scanning" @click="scan">查询框</el-button>
      </div>
    </details>
    <section class="current-panel" aria-label="当前产品框" aria-live="polite">
        <div class="section-heading"><div><h2>{{ current?.box?.product_name_snapshot || (current?.box ? `产品 ${current.box.product_code}` : '当前产品框') }}</h2><p v-if="current?.box?.customer_part_no" class="part-number">客户件号 {{ current.box.customer_part_no }}</p><p v-else-if="current && !current.box" class="trace-code">{{ poolStatus(current.pool_item.pool_status) }}标签 {{ current.pool_item.public_code }}</p></div><el-button v-if="current" link @click="clearCurrent">清除</el-button></div>
        <div v-if="!current" class="empty-current"><p>定位产品框后，查看产品、订单、当前数量和工艺。</p><el-button link @click="labelsOpen = true">也可从标签管理选择已有标签</el-button></div>
        <template v-else>
          <div v-if="current.box" class="box-detail">
            <div class="business-summary"><div class="quantity"><span>当前数量</span><strong>{{ current.box.current_qty.toLocaleString() }} <small>件</small></strong></div><dl><dt>客户</dt><dd>{{ current.box.customer_name_snapshot || '未维护' }}</dd><dt>实际产品</dt><dd>{{ current.box.product_code }}</dd><dt>使用状态</dt><dd>{{ lifecycleStatus(current.box.lifecycle_status) }}</dd></dl></div>
            <dl class="process-facts"><dt>所属订单</dt><dd>{{ orderLabel(current.box.order_id) }}</dd><dt>当前工艺</dt><dd>{{ current.box.current_process_code || '尚未开始' }}</dd><dt>下一工艺</dt><dd>{{ current.box.next_process_code || '未指定' }}</dd></dl>
            <div class="business-actions"><el-button v-if="canMetadata" @click="openMetadata">编辑标签信息</el-button><el-button v-if="canPrint" :loading="printing" @click="preparePrint(current.pool_item)">补打标签</el-button></div>
          </div>
          <form v-else-if="canWarehouseBind && current.allowed_actions.includes('bind')" class="binding-form" @submit.prevent="bindCurrent">
            <h3>为当前框绑定订单</h3><p class="quiet-note">当前标签未绑定。核对实物与订单后确认，绑定后不能更换。</p>
            <label for="bind-order">生产订单</label>
            <el-select id="bind-order" v-model="orderId" filterable clearable placeholder="选择订单" :loading="ordersLoading" :disabled="binding" @change="loadContext"><el-option v-for="order in orders" :key="order.id" :label="`${order.plan_no || '订单 #' + order.id} · ${order.total_qty ?? '未配置'} 件`" :value="order.id" /></el-select>
            <p v-if="ordersError" class="inline-error" role="alert">{{ ordersError }} <el-button link @click="loadOrders">重试</el-button></p>
            <label for="bind-product">实际产品 / 件号</label>
            <el-select id="bind-product" v-model="productId" :loading="contextLoading" :disabled="!context || binding" placeholder="选择已配置产品"><el-option v-for="product in context?.products.filter(p => p.binding_allowed) || []" :key="product.id" :disabled="!product.can_bind" :value="product.id" :label="`${product.product_code} · ${product.part_name || product.customer_part_no || '未维护名称'} · 目标 ${product.target_qty} 件`" /></el-select>
            <p v-if="contextError" class="inline-error" role="alert">{{ contextError }}</p>
            <p v-if="configurationGaps.length" class="inline-error">订单配置未完整：{{ configurationGaps.join('、') }}</p>
            <p v-if="selectedProduct?.route" class="route-summary">路线 {{ selectedProduct.route.route_code }} · v{{ selectedProduct.route.revision }}<br>{{ selectedProduct.route.steps.map(s => s.name || s.code).join(' → ') }}</p>
            <el-button type="primary" native-type="submit" :disabled="!selectedProduct?.can_bind || !!configurationGaps.length || contextLoading" :loading="binding" class="wide-button">确认绑定此订单</el-button>
          </form>
          <p v-else class="quiet-note">当前标签尚未绑定。请由有权限的仓库人员操作；生产绑定需先扫描机台并选单。</p>
          <details class="identity-details"><summary>标签与追溯标识</summary><dl><dt>标签编号</dt><dd class="trace-code">{{ current.pool_item.public_code }}</dd><dt>标签状态</dt><dd>{{ poolStatus(current.pool_item.pool_status) }}</dd><dt>扫码内容</dt><dd class="trace-code">{{ current.pool_item.qr_payload }}</dd><template v-if="current.box"><dt>绑定时间</dt><dd>{{ formatTime(current.box.bound_at) }}</dd></template></dl></details>
        </template>
        <p v-if="actionError" class="inline-error" role="alert">{{ actionError }}</p>
    </section>
      <section v-show="labelsOpen" id="product-label-manager" class="pool-panel" aria-label="标签管理">
        <div class="section-heading"><div><h2>标签管理 <span>{{ total.toLocaleString() }} 项</span></h2><p>标签用于实物定位与追溯，可在此生成、选择或补打。</p></div><div class="label-actions"><el-button v-if="canGenerate" @click="generateVisible = true">批量生成</el-button>
          <el-button :disabled="!selectedIds.length || !canPrint" :loading="printing" @click="preparePrint()">打印已选 {{ selectedIds.length || '' }}</el-button>
        </div></div>
        <form class="filter-bar" @submit.prevent="searchPool">
          <el-select v-model="filters.pool_status" aria-label="绑定状态" clearable placeholder="全部状态" @change="searchPool"><el-option label="未绑定" value="unused" /><el-option label="已绑定" value="bound" /></el-select>
          <el-input v-model="filters.print_batch_no" aria-label="生成批次" placeholder="生成批次" clearable @clear="searchPool" />
          <el-button native-type="submit">筛选</el-button><el-button v-if="filters.pool_status || filters.print_batch_no" link @click="resetFilters">重置</el-button>
        </form>
        <el-table v-loading="loading" :data="items" row-key="id" :height="360" empty-text="当前范围没有标签，可调整筛选或生成标签" table-layout="fixed">
          <el-table-column width="48"><template #header><el-checkbox aria-label="选择本页二维码" :model-value="pageSelected" :indeterminate="pagePartSelected" @change="togglePage" /></template><template #default="{ row }"><el-checkbox :aria-label="'选择 ' + row.public_code" :model-value="selectedIds.includes(row.id)" @change="toggleItem(row.id)" /></template></el-table-column>
          <el-table-column label="标签编号" min-width="200"><template #default="{ row }"><button type="button" class="code-link" @click="inspect(row)">{{ row.public_code }}</button><small class="row-subtitle">{{ row.print_batch_no }}</small></template></el-table-column>
          <el-table-column label="状态" width="90"><template #default="{ row }"><span :class="['status', row.pool_status]">{{ poolStatus(row.pool_status) }}</span></template></el-table-column>
          <el-table-column label="确认次数" width="90" align="right"><template #default="{ row }">{{ row.print_count }}</template></el-table-column>
          <el-table-column label="首次确认" width="155"><template #default="{ row }">{{ formatTime(row.printed_at) }}</template></el-table-column>
          <el-table-column label="操作" width="85"><template #default="{ row }"><el-button link :disabled="!canPrint || printing" @click="preparePrint(row)">补打</el-button></template></el-table-column>
        </el-table>
        <footer class="table-footer"><span>已选 {{ selectedIds.length }} 项 <el-button v-if="selectedIds.length" link @click="selectedIds = []">清空</el-button></span><el-pagination v-model:current-page="page" :page-size="pageSize" :total="total" layout="prev, pager, next" @current-change="loadPool" /></footer>
        <p class="quiet-note">打印数据不会增加次数；请按实际打印结果确认。<span v-if="actor"> 当前操作权限：{{ department(actor.dept) }} LV{{ actor.role_level }}。</span></p>
      </section>
    <el-dialog v-model="generateVisible" title="批量生成二维码" width="440px" :close-on-click-modal="false" :close-on-press-escape="!generating" :show-close="!generating">
      <el-form label-position="top" @submit.prevent="generateBatch"><el-form-item label="生成数量"><el-input-number v-model="generateCount" :min="1" :max="batchLimit" :step="1" step-strictly :disabled="generating" aria-label="生成数量" /></el-form-item><p class="quiet-note">单次最多 {{ batchLimit }} 项。每个标签拥有独立编号，绑定和补打不会改变编号。</p><p v-if="generateError" class="inline-error" role="alert">{{ generateError }}</p></el-form>
      <template #footer><el-button :disabled="generating" @click="generateVisible = false">取消</el-button><el-button type="primary" :loading="generating" @click="generateBatch">生成并选中</el-button></template>
    </el-dialog>
    <el-dialog v-model="metadataVisible" title="编辑标签信息" width="480px" :close-on-click-modal="false" :close-on-press-escape="!savingMetadata" :show-close="!savingMetadata">
      <p class="quiet-note">唯一编号、订单和实际产品保持原绑定；下次补打使用更新后的标签信息。</p>
      <el-form label-position="top" @submit.prevent="saveMetadata"><el-form-item label="客户名称快照"><el-input v-model="metadata.customer_name_snapshot" maxlength="200" :disabled="savingMetadata || !metadataReady" /></el-form-item><el-form-item label="客户件号"><el-input v-model="metadata.customer_part_no" maxlength="100" :disabled="savingMetadata || !metadataReady" /></el-form-item><el-form-item label="下一工艺"><el-select v-model="metadata.next_process_code" clearable placeholder="未指定" :disabled="savingMetadata || !metadataReady"><el-option v-for="step in metadataSteps" :key="step.code" :label="step.name ? `${step.name}（${step.code}）` : step.code" :value="step.code" /></el-select></el-form-item></el-form>
      <p v-if="metadataError" class="inline-error" role="alert">{{ metadataError }}</p><template #footer><el-button :disabled="savingMetadata" @click="metadataVisible = false">取消</el-button><el-button :disabled="savingMetadata" @click="reloadMetadata">重新读取</el-button><el-button type="primary" :disabled="!metadataReady" :loading="savingMetadata" @click="saveMetadata">保存信息</el-button></template>
    </el-dialog>
    <QrPrintDialog v-model="printVisible" :job="printJob" @confirmed="printConfirmed" />
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { productBoxesApi as api } from '@/api/productBoxes'
import { productionApi } from '@/api/production'
import type { PoolPage, ProductBoxScan, ProductQrPoolItem, ProductQrContext, QrCapability, QrId, QrPrintJob } from '@/types/productBox'
import QrPrintDialog from './QrPrintDialog.vue'
import { qrError } from './messages'

const loading = ref(false), pageError = ref(''), items = ref<ProductQrPoolItem[]>([]), total = ref(0), page = ref(1), pageSize = 50
const filters = ref({ pool_status: '', print_batch_no: '' }), selectedIds = ref<QrId[]>([])
const actor = ref<PoolPage['actor'] | null>(null), caps = ref<QrCapability[]>([]), batchLimit = ref(500)
const canGenerate = computed(() => !!actor.value && caps.value.includes('qr.generate') && (actor.value.role_level === 4 ? caps.value.includes('qr.admin') : actor.value.dept === 'prod' && actor.value.role_level >= 2))
const canPrint = computed(() => !!actor.value && caps.value.includes('qr.print') && (actor.value.role_level === 4 || ['prod','warehouse'].includes(actor.value.dept)))
const canWarehouseBind = computed(() => actor.value?.dept === 'warehouse' && caps.value.includes('qr.bind'))
const canMetadata = computed(() => !!current.value?.box && caps.value.includes('qr.metadata') && !!actor.value && ['prod','warehouse','sales'].includes(actor.value.dept))
const current = ref<ProductBoxScan | null>(null), scanText = ref(''), scanning = ref(false), actionError = ref('')
const labelsOpen = ref(false)
const scanInput = ref<{ focus: () => void }>(), generationKey = ref(''), generateCount = ref(20), generateVisible = ref(false), generating = ref(false), generateError = ref('')
const printing = ref(false), printJob = ref<QrPrintJob | null>(null), printVisible = ref(false)
const orders = ref<Array<{ id: number; plan_no: string; total_qty: number | null }>>([]), ordersLoading = ref(false), ordersError = ref('')
const orderId = ref<number>(), productId = ref<QrId>(), context = ref<ProductQrContext | null>(null), contextLoading = ref(false), contextError = ref(''), binding = ref(false)
const selectedProduct = computed(() => context.value?.products.find(p => p.id === productId.value))
const configurationGaps = computed(() => [...new Set([...(context.value?.missing_configuration || []), ...(selectedProduct.value?.missing_configuration || [])])].map(gapName))
const metadataVisible = ref(false), savingMetadata = ref(false), metadataContextLoading = ref(false), metadataError = ref(''), metadataVersion = ref(0), metadataContext = ref<ProductQrContext | null>(null)
const metadata = ref({ customer_name_snapshot: '', customer_part_no: '', next_process_code: '' })
const metadataLoaded = ref(false), metadataLoadedBoxId = ref<QrId | null>(null)
let metadataReadSequence = 0
const metadataReady = computed(() => metadataVisible.value && metadataLoaded.value && !metadataContextLoading.value && metadataLoadedBoxId.value === current.value?.box?.id)
watch(metadataVisible, visible => { if (!visible) resetMetadata() }, { flush: 'sync' })
watch(() => current.value?.box?.id, (id, previous) => {
  if (id !== previous) { resetMetadata(); metadataVisible.value = false }
}, { flush: 'sync' })
const metadataSteps = computed(() => { const box = current.value?.box, product = metadataContext.value?.products.find(p => p.id === box?.order_product_id); const steps = product?.route?.steps || []; return steps.slice(box?.current_process_code ? steps.findIndex(s => s.code === box.current_process_code) + 1 : 0) })
const pageSelected = computed(() => items.value.length > 0 && items.value.every(i => selectedIds.value.includes(i.id)))
const pagePartSelected = computed(() => !pageSelected.value && items.value.some(i => selectedIds.value.includes(i.id)))
const key = () => crypto.randomUUID()
watch(generateCount, () => { generationKey.value = '' })
function department(value: string) { return ({ prod:'生产', warehouse:'仓库', sales:'业务', quality:'质量', engineering:'工程' } as Record<string,string>)[value] || value }
function gapName(value: string) { return ({business_owner:'业务负责人',route:'工艺路线',machine_process_targets:'机台工艺目标',target_qty:'产品目标量',order_context:'订单配置',products:'实际产品'} as Record<string,string>)[value] || value }
function poolStatus(value: string) { return ({unused:'未绑定',bound:'已绑定',void:'已停用'} as Record<string,string>)[value] || value }
function lifecycleStatus(value: string) { return ({active:'使用中',empty:'空框',closed:'已结束',scrapped:'已报废'} as Record<string,string>)[value] || value }
function orderLabel(id: number) { return orders.value.find(order => order.id === id)?.plan_no || `订单 #${id}` }
function formatTime(value: string | null) { return value ? new Intl.DateTimeFormat('zh-CN',{timeZone:'Asia/Hong_Kong',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false}).format(new Date(value)) : '未确认' }
let poolSequence=0
async function loadPool() { const request=++poolSequence; loading.value = true; pageError.value = ''; try { const result = await api.listPool({pool_status: filters.value.pool_status as 'unused'|'bound'|'void' || undefined,print_batch_no:filters.value.print_batch_no || undefined,page:page.value,page_size:pageSize}); if(request!==poolSequence)return; items.value=result.items; total.value=result.total; actor.value=result.actor; caps.value=result.capabilities; batchLimit.value=result.batch_limit } catch(error) { if(request===poolSequence){ pageError.value=qrError(error); items.value=[]; total.value=0; caps.value=[] } } finally { if(request===poolSequence)loading.value=false } }
function searchPool() { page.value=1; void loadPool() }
function resetFilters() { filters.value={pool_status:'',print_batch_no:''}; searchPool() }
function toggleItem(id: QrId) { selectedIds.value=selectedIds.value.includes(id)?selectedIds.value.filter(i=>i!==id):[...selectedIds.value,id] }
function togglePage(value: boolean | string | number) { const ids=new Set(selectedIds.value); items.value.forEach(item=>value?ids.add(item.id):ids.delete(item.id)); selectedIds.value=[...ids] }
function clearCurrent() { if(binding.value || savingMetadata.value)return; ++contextSequence; contextLoading.value=false; current.value=null; actionError.value=''; scanText.value=''; orderId.value=undefined; productId.value=undefined; context.value=null; scanInput.value?.focus() }
async function scan() { if(!scanText.value.trim() || scanning.value || binding.value || savingMetadata.value) return; ++contextSequence; contextLoading.value=false; scanning.value=true; actionError.value=''; current.value=null; context.value=null; orderId.value=undefined; productId.value=undefined; try { current.value=await api.scan(scanText.value.trim()); if(!current.value.box && canWarehouseBind.value) await loadOrders() } catch(error) { actionError.value=qrError(error) } finally { scanning.value=false } }
async function inspect(item: ProductQrPoolItem) { if(scanning.value||binding.value||savingMetadata.value)return; scanText.value=item.qr_payload; await scan(); if(current.value) labelsOpen.value=false }
async function generateBatch() { if(generating.value) return; generating.value=true; generateError.value=''; generationKey.value ||= key(); try { const result=await api.generateBatch({count:generateCount.value,idempotency_key:generationKey.value}); selectedIds.value=result.items.map(i=>i.id); filters.value={pool_status:'',print_batch_no:result.print_batch_no}; page.value=1; generateVisible.value=false; generationKey.value=''; await loadPool(); ElMessage.success(`已生成并选中 ${result.count} 项`) } catch(error) { generateError.value=qrError(error) } finally { generating.value=false } }
async function preparePrint(item?: ProductQrPoolItem) { if(printing.value) return; printing.value=true; pageError.value=''; try { printJob.value=item ? await api.reprint(item.id,{idempotency_key:key()}) : await api.printData({item_ids:selectedIds.value,idempotency_key:key()}); printVisible.value=true } catch(error) { pageError.value=qrError(error) } finally { printing.value=false } }
async function printConfirmed() { await loadPool(); if(current.value) { try { current.value=await api.scan(current.value.pool_item.qr_payload) } catch(error) { actionError.value=qrError(error) } } }
async function loadOrders() { ordersLoading.value=true; ordersError.value=''; try { const result: typeof orders.value=[]; for(let skip=0;;skip+=100){ const batch=await productionApi.listPlans({skip,limit:100}); result.push(...batch); if(batch.length<100)break } orders.value=[...new Map(result.map(order=>[order.id,order])).values()] } catch(error) { ordersError.value=qrError(error) } finally { ordersLoading.value=false } }
let contextSequence=0
async function loadContext() { const sequence=++contextSequence, id=orderId.value, poolId=current.value?.pool_item.id; context.value=null; contextError.value=''; productId.value=undefined; if(!id) { contextLoading.value=false; return } contextLoading.value=true; try { const result=await api.qrContext(id); if(sequence!==contextSequence || poolId!==current.value?.pool_item.id) return; context.value=result; const allowed=result.products.filter(p=>p.binding_allowed&&p.can_bind); if(allowed.length===1) productId.value=allowed[0].id } catch(error) { if(sequence===contextSequence) contextError.value=qrError(error) } finally { if(sequence===contextSequence) contextLoading.value=false } }
async function bindCurrent() { if(!current.value || current.value.box || !productId.value || binding.value) return; binding.value=true; actionError.value=''; try { current.value=await api.bind({qr_payload:current.value.pool_item.qr_payload,order_product_id:productId.value,idempotency_key:key()}); await loadPool(); ElMessage.success('已绑定订单，当前数量为 0 件') } catch(error) { actionError.value=qrError(error) } finally { binding.value=false } }
function resetMetadata() {
  ++metadataReadSequence
  metadataLoaded.value = false
  metadataLoadedBoxId.value = null
  metadataContextLoading.value = false
  metadataVersion.value = 0
  metadataContext.value = null
  metadataError.value = ''
  metadata.value = { customer_name_snapshot: '', customer_part_no: '', next_process_code: '' }
}
async function openMetadata() {
  if (!current.value?.box || savingMetadata.value) return
  metadataVisible.value = true
  await reloadMetadata()
}
async function reloadMetadata() {
  if (savingMetadata.value) return
  resetMetadata()
  const target = current.value
  if (!target?.box || !metadataVisible.value) return
  const sequence = metadataReadSequence, boxId = target.box.id, poolId = target.pool_item.id
  const isCurrent = () => sequence === metadataReadSequence && metadataVisible.value && current.value?.box?.id === boxId && current.value.pool_item.id === poolId
  metadataContextLoading.value = true
  try {
    const refreshed = await api.scan(target.pool_item.qr_payload)
    if (!isCurrent()) return
    if (!refreshed.box || refreshed.box.id !== boxId || refreshed.pool_item.id !== poolId) throw new Error('当前框已变化，请重新打开编辑。')
    const box = refreshed.box
    const orderContext = await api.qrContext(box.order_id)
    if (!isCurrent()) return
    if (orderContext.order_id !== box.order_id) throw new Error('订单资料与当前框不一致，请重新读取。')
    current.value = refreshed
    metadataVersion.value = box.version
    metadataContext.value = orderContext
    metadata.value = { customer_name_snapshot: box.customer_name_snapshot || '', customer_part_no: box.customer_part_no || '', next_process_code: box.next_process_code || '' }
    metadataLoadedBoxId.value = boxId
    metadataLoaded.value = true
  } catch (error) {
    if (isCurrent()) metadataError.value = qrError(error)
  } finally {
    if (sequence === metadataReadSequence) metadataContextLoading.value = false
  }
}
async function saveMetadata() {
  if (!metadataReady.value || !current.value?.box || metadataLoadedBoxId.value !== current.value.box.id || savingMetadata.value) return
  const boxId = metadataLoadedBoxId.value
  savingMetadata.value = true
  metadataError.value = ''
  try {
    const result = await api.updateMetadata(boxId, { ...metadata.value, next_process_code: metadata.value.next_process_code || null, expected_version: metadataVersion.value, idempotency_key: key() })
    if (current.value?.box?.id === boxId) current.value.box = result
    metadataVisible.value = false
    ElMessage.success('标签信息已保存，二维码身份保持不变')
  } catch (error) { metadataError.value = qrError(error) }
  finally { savingMetadata.value = false }
}
onMounted(loadPool)
</script>

<style scoped>
.qr-workspace{padding:24px;color:var(--zephyr-ink)}.page-heading,.section-heading,.table-footer{display:flex;justify-content:space-between;align-items:center;gap:16px}.page-heading{margin-bottom:20px}h1{font-size:22px;line-height:1.3;margin:0 0 6px}h2{font-size:15px;margin:0}h2 span{margin-left:8px;font-weight:400;color:var(--zephyr-muted);font-variant-numeric:tabular-nums}h3{font-size:14px;margin:18px 0 4px}p{margin:0;color:var(--zephyr-muted)}.page-alert{margin-bottom:16px}.scan-strip{display:flex;align-items:center;gap:12px;padding:16px;background:var(--zephyr-surface);border:1px solid var(--zephyr-border);border-radius:8px;margin-bottom:16px}.scan-strip label{font-weight:600;white-space:nowrap}.scan-strip .el-input{max-width:650px}.workspace-grid{display:grid;grid-template-columns:minmax(0,1fr) 310px;gap:16px;align-items:start}.pool-panel,.current-panel{background:var(--zephyr-surface);border:1px solid var(--zephyr-border);border-radius:8px;overflow:hidden}.section-heading{padding:16px}.section-heading p{font-size:12px;margin-top:5px}.filter-bar{display:flex;gap:8px;padding:0 16px 16px;flex-wrap:wrap}.filter-bar .el-select{width:125px}.filter-bar .el-input{max-width:225px}.code-link{font:12px var(--zephyr-font-mono);border:0;padding:0;background:none;color:var(--zephyr-primary);cursor:pointer;text-align:left}.row-subtitle{display:block;font-size:11px;color:var(--zephyr-muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;margin-top:3px}.status{display:inline-flex;align-items:center;gap:5px;font-size:12px}.status::before{content:'';width:6px;height:6px;border-radius:50%;background:#929caf}.status.bound::before{background:#37856d}.status.void::before{background:var(--zephyr-danger)}.table-footer{padding:12px 16px;border-top:1px solid var(--zephyr-border-soft)}.quiet-note{font-size:12px;line-height:1.65;margin-top:10px}.pool-panel>.quiet-note{padding:0 16px 14px;margin:0}.current-panel{padding:0 16px 18px}.current-panel>.section-heading{padding:16px 0;border-bottom:1px solid var(--zephyr-border-soft);margin-bottom:16px}.empty-current{padding:28px 8px;display:flex;flex-direction:column;align-items:center;text-align:center;gap:16px;line-height:1.7}.empty-current .el-icon{font-size:30px;color:var(--zephyr-subtle)}.current-code{font:13px var(--zephyr-font-mono);font-weight:600;overflow-wrap:anywhere;margin-bottom:8px;color:var(--zephyr-ink)}.quantity{margin:20px 0;display:flex;flex-direction:column;gap:4px;background:var(--zephyr-surface-muted);padding:12px;border-radius:6px}.quantity span{font-size:12px;color:var(--zephyr-muted)}.quantity strong{font-size:30px;font-variant-numeric:tabular-nums;font-weight:600}.quantity small{font-size:13px;font-weight:400}.box-detail dl{display:grid;grid-template-columns:75px minmax(0,1fr);gap:12px 8px;font-size:12px}.box-detail dt{color:var(--zephyr-muted)}.box-detail dd{margin:0;overflow-wrap:anywhere}.wide-button{width:100%;margin-top:16px}.binding-form{display:flex;flex-direction:column}.binding-form label{font-size:12px;margin:16px 0 6px}.inline-error{color:var(--zephyr-danger);font-size:12px;line-height:1.65;margin-top:12px;overflow-wrap:anywhere}.route-summary{background:var(--zephyr-surface-muted);padding:10px;margin-top:12px;font-size:12px;line-height:1.7}:deep(.el-dialog){max-width:calc(100vw - 24px)}@media(max-width:1100px){.workspace-grid{grid-template-columns:minmax(0,1fr)}.current-panel{max-width:none}.box-detail dl{grid-template-columns:100px 1fr}}@media(max-width:600px){.qr-workspace{padding:12px}.scan-strip{flex-wrap:wrap}.scan-strip label{width:100%}.scan-strip .el-input{flex:1}.page-heading{align-items:start}.table-footer{flex-wrap:wrap}}
.current-panel{margin-bottom:20px}.part-number{font-size:13px;color:var(--zephyr-ink);overflow-wrap:anywhere}.business-summary{display:grid;grid-template-columns:180px minmax(0,1fr);gap:32px;align-items:center;max-width:850px}.business-summary .quantity{margin:0}.business-summary .quantity strong{font-size:36px}.box-detail .process-facts{grid-template-columns:75px minmax(0,1fr) 75px minmax(0,1fr) 75px minmax(0,1fr);padding:20px 0;margin:16px 0 0;border-top:1px solid var(--zephyr-border-soft)}.business-actions,.label-actions{display:flex;flex-wrap:wrap;gap:8px}.label-actions .el-button+.el-button,.business-actions .el-button+.el-button{margin-left:0}.binding-form{max-width:560px}.identity-details{margin-top:20px;padding-top:14px;border-top:1px solid var(--zephyr-border-soft);font-size:12px;color:var(--zephyr-muted)}.identity-details summary{cursor:pointer;width:fit-content;padding:4px 0}.identity-details summary:focus-visible,.code-link:focus-visible{outline:2px solid var(--zephyr-primary);outline-offset:3px}.identity-details dl{display:grid;grid-template-columns:85px minmax(0,1fr);gap:10px;margin:14px 0 0}.identity-details dd{margin:0;overflow-wrap:anywhere}.trace-code{font-family:var(--zephyr-font-mono);font-size:11px}.pool-panel .section-heading{align-items:flex-start}.pool-panel .section-heading p{line-height:1.6}
.scan-strip{display:block;padding:12px 16px}.scan-strip summary{width:fit-content;cursor:pointer;font-size:12px;color:var(--zephyr-muted)}.scan-strip summary:focus-visible{outline:2px solid var(--zephyr-primary);outline-offset:3px}.scan-controls{display:flex;align-items:center;gap:12px;padding-top:12px}
@media(max-width:900px){.business-summary{grid-template-columns:150px minmax(0,1fr);gap:20px}.box-detail .process-facts{grid-template-columns:85px minmax(0,1fr)}.pool-panel .section-heading{flex-wrap:wrap}}
@media(max-width:600px){.business-summary{grid-template-columns:minmax(0,1fr);gap:12px}.business-summary .quantity{max-width:180px}.identity-details dl{grid-template-columns:75px minmax(0,1fr)}}
@media(max-width:600px){.scan-controls{flex-wrap:wrap}.scan-controls label{width:100%}.scan-controls .el-input{flex:1}}
</style>
