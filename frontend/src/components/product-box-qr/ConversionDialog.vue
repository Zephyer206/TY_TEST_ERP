<template>
  <el-dialog class="qr-conversion-dialog" :model-value="true" :title="item?'核对本次产品转换':'发起产品转换'" width="min(620px, calc(100vw - 32px))" top="4vh" :style="{maxHeight:'92vh',display:'flex',flexDirection:'column'}" :close-on-click-modal="false" :show-close="!busy" :close-on-press-escape="!busy" @close="!busy && $emit('close')">
    <h3>PP-{{String(box.order_id).padStart(6,'0')}} · {{box.product_name_snapshot}}</h3>
    <p>{{box.product_code}} · {{box.current_process_code}} · 当前实物 {{box.current_qty}} 件</p>
    <template v-if="item">
      <dl><div><dt>转换方向</dt><dd>{{item.source_product_code}} → {{item.target_product_code}}</dd></div><div><dt>目标工艺</dt><dd>{{item.target_process_code}}</dd></div><div><dt>状态</dt><dd>待操作工确认</dd></div></dl>
      <p class="note">{{item.trigger_type==='pre_authorized'?'订单已预授权，此次扫码仅建立待确认记录。':'负责人已发起转换。'}}关闭此窗口会保留待确认记录，产品和数量不变。</p>
      <template v-if="canConfirm">
        <label class="field">本次实际完成数量<input v-model.number="amount" type="number" inputmode="numeric" min="1" :max="box.current_qty" step="1" :disabled="busy" aria-label="转换实际完成数量"/></label>
        <p v-if="validAmount" class="quantity-preview">{{partial?`父框保留 ${box.product_code} ${box.current_qty-Number(amount)} 件；新子框 ${item.target_product_code} ${amount} 件。`:`全量 ${amount} 件转为 ${item.target_product_code}，保留原框标签。`}}</p>
        <div v-if="partial" class="field"><label for="conversion-child-scan">子框标签核对</label><div class="scan-row"><el-input id="conversion-child-scan" v-model="childText" :disabled="busy" placeholder="扫描池内未绑定子标签" @keyup.enter="verifyChild"/><el-button :disabled="busy || !childText.trim()" @click="verifyChild">核对子标签</el-button></div><p v-if="verifiedChild" class="note">子标签可用：{{verifiedChild}}</p></div>
        <el-checkbox v-model="confirmed" :disabled="busy">已核对实物及本次实际数量，确认执行转换</el-checkbox>
      </template>
      <p v-else class="note">请由操作工扫描机台，选择本订单的目标 {{item.target_product_code}} 产品 · {{item.target_process_code}} 工艺，再扫描原框确认实际数量。</p>
      <label v-if="canCancel" class="field">取消原因（可留空）<el-input v-model="cancelReason" type="textarea" maxlength="500" :disabled="busy" aria-label="转换取消原因"/></label>
    </template>
    <template v-else>
      <el-form label-position="top" @submit.prevent="create"><el-form-item label="转换目标"><el-select v-model="targetId" aria-label="转换目标产品" placeholder="明确选择目标产品及工艺" :disabled="busy"><el-option v-for="target in options.targets" :key="target.order_product_id" :value="target.order_product_id" :label="`${target.product_code} · ${target.product_name || target.customer_part_no || '未维护名称'} · ${target.target_process_code}`"/></el-select></el-form-item></el-form>
      <label class="field">建议完成数量<input v-model.number="amount" type="number" inputmode="numeric" min="1" :max="box.current_qty" step="1" :disabled="busy" aria-label="转换建议数量"/></label>
      <p class="note">发起仅保存待操作工确认记录；实际完成数量由操作工核对后提交。</p>
    </template>
    <p v-if="error" class="error" role="alert">{{error}}</p>
    <template #footer><el-button :disabled="busy" @click="$emit('close')">关闭</el-button><el-button v-if="item && canCancel" :disabled="busy" @click="cancel">取消本次转换</el-button><el-button v-if="!item" type="primary" :loading="busy" :disabled="busy || !targetId || !validAmount" @click="create">保存待确认转换</el-button><el-button v-else-if="canConfirm" type="primary" :loading="busy" :disabled="busy || !validAmount || !confirmed || (partial && !verifiedChild)" @click="submit">确认实际数量并转换</el-button></template>
  </el-dialog>
</template>
<script setup lang="ts">
import {computed,ref,watch} from 'vue'
import {ElMessage} from 'element-plus'
import {productConversionsApi as api} from '@/api/productConversions'
import {productBoxesApi} from '@/api/productBoxes'
import type {ProductBox,QrId} from '@/types/productBox'
import type {ConversionOptions,ConversionRecord,ConversionResult} from '@/types/productConversion'
import {qrError} from '@/views/product-box-qr/messages'
const props=defineProps<{box:ProductBox;options:ConversionOptions;item?:ConversionRecord;contextId?:QrId;targetProductId?:QrId;processCode?:string}>()
const emit=defineEmits<{close:[];updated:[result?:ConversionResult]}>()
const busy=ref(false),error=ref(''),targetId=ref<QrId>(),amount=ref<number|string>(props.item?.proposed_qty ?? props.box.current_qty)
const confirmed=ref(false),childText=ref(''),verifiedChild=ref(''),cancelReason=ref(''),requestKey=ref(crypto.randomUUID())
const canConfirm=computed(()=>!!props.contextId && props.item?.target_order_product_id===props.targetProductId && props.item?.target_process_code===props.processCode)
const canCancel=computed(()=>props.item?.can_cancel || canConfirm.value)
const validAmount=computed(()=>typeof amount.value==='number' && Number.isInteger(amount.value) && amount.value>0 && amount.value<=props.box.current_qty)
const partial=computed(()=>validAmount.value && Number(amount.value)<props.box.current_qty)
watch(childText,()=>{verifiedChild.value='';confirmed.value=false},{flush:'sync'})
watch([amount,targetId],()=>{confirmed.value=false;requestKey.value=crypto.randomUUID()},{flush:'sync'})
watch([childText,cancelReason,confirmed],()=>requestKey.value=crypto.randomUUID(),{flush:'sync'})
async function run(fn:()=>Promise<void>){if(busy.value)return;busy.value=true;error.value='';try{await fn()}catch(e){error.value=qrError(e)}finally{busy.value=false}}
async function verifyChild(){await run(async()=>{verifiedChild.value='';const result=await productBoxesApi.scan(childText.value.trim());if(result.box || result.pool_item.pool_status!=='unused')throw new Error('子标签已被使用，请更换未绑定标签。');verifiedChild.value=result.pool_item.public_code})}
async function create(){if(!targetId.value || !validAmount.value)return;await run(async()=>{await api.create({box_id:props.box.id,target_order_product_id:targetId.value!,proposed_qty:Number(amount.value),expected_version:props.box.version,idempotency_key:requestKey.value});ElMessage.success('待确认转换已保存，产品和数量保持原样');emit('updated')})}
async function cancel(){if(!props.item || !canCancel.value)return;await run(async()=>{await api.cancel(props.item!.id,{conversion_version:props.item!.version,...(props.contextId?{context_id:props.contextId}:{}),reason:cancelReason.value,idempotency_key:requestKey.value});ElMessage.success('转换已取消，产品和数量保持原样');emit('updated')})}
async function submit(){if(!props.item || !props.contextId || !canConfirm.value || !validAmount.value || !confirmed.value || (partial.value&&!verifiedChild.value))return;await run(async()=>{const result=await api.confirm(props.item!.id,{context_id:props.contextId!,actual_qty:Number(amount.value),confirm:true,...(partial.value?{child_qr_payload:childText.value.trim()}:{}),expected_version:props.box.version,conversion_version:props.item!.version,idempotency_key:requestKey.value});ElMessage.success('产品转换已保存，原订单与工艺记录保留');emit('updated',result)})}
</script>
<style scoped>
:global(.qr-conversion-dialog .el-dialog__body){overflow:auto;min-height:0;flex:1}:global(.qr-conversion-dialog .el-dialog__header),:global(.qr-conversion-dialog .el-dialog__footer){flex-shrink:0}h3{font-size:16px;margin:0 0 8px;color:var(--zephyr-ink)}p{font-size:12px;line-height:1.7;color:var(--zephyr-muted)}dl{display:flex;gap:28px;padding:14px 0;border-block:1px solid var(--zephyr-border-soft)}dt{font-size:12px;color:var(--zephyr-muted)}dd{margin:8px 0 0;font-size:15px;color:var(--zephyr-ink)}.field{display:flex;flex-direction:column;gap:8px;margin:16px 0;font-size:13px}.field input{width:160px;height:34px;padding:0 10px;border:1px solid var(--zephyr-border);border-radius:6px;color:var(--zephyr-ink);background:var(--zephyr-surface);font:inherit;font-variant-numeric:tabular-nums}.field input:focus-visible{outline:2px solid var(--zephyr-primary);outline-offset:2px}.scan-row{display:flex;gap:8px}.quantity-preview{color:var(--zephyr-ink);font-variant-numeric:tabular-nums}.error{color:var(--zephyr-danger)}:deep(.el-select){width:100%}:deep(.el-checkbox){height:auto;white-space:normal}:deep(.el-checkbox__label){white-space:normal;line-height:1.7}@media(max-width:600px){.scan-row{flex-wrap:wrap}.scan-row .el-input{flex-basis:100%}dl{flex-wrap:wrap}}
</style>
