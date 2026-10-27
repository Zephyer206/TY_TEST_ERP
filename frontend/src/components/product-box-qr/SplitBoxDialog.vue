<template>
  <el-dialog class="qr-split-dialog" :model-value="true" title="拆分产品框" width="min(640px, calc(100vw - 32px))" top="4vh" :style="{maxHeight:'92vh',display:'flex',flexDirection:'column'}" :close-on-click-modal="false" :show-close="!saving" :close-on-press-escape="!saving" @close="!saving && $emit('cancel')">
    <p v-if="loading" role="status">正在核对父框余量和可用目标订单…</p>
    <template v-if="parent && info">
      <header class="source"><h3>{{planNo}} · {{parent.product_name_snapshot}}</h3><p>{{parent.customer_part_no || '未维护客户件号'}} · {{parent.current_process_code}} · 当前 {{parent.current_qty}} 件</p><p>来源用途：订单 {{info.order_qty}} 件，备货 {{info.stock_qty}} 件</p></header>
      <p v-if="info.reason" class="error" role="alert">{{info.reason}}</p>
      <el-form v-else label-position="top" @submit.prevent="submit">
        <el-form-item label="拆分去向"><el-select v-model="mode" aria-label="拆分去向" :disabled="busy"><el-option v-if="info.allowed_actions.includes('split')" label="同一订单" value="same"/><el-option v-if="info.allowed_actions.includes('cross_order_split')" label="转到其他订单" value="cross"/></el-select></el-form-item>
        <el-form-item v-if="mode==='cross'" label="目标订单与接收工艺"><el-select v-model="targetStateId" aria-label="目标订单与接收工艺" :disabled="busy" placeholder="明确选择兼容目标订单和机台工艺"><el-option v-for="target in targets" :key="target.state_id" :value="target.state_id" :label="`${target.plan_no} · ${target.product_name || target.customer_part_no} · ${target.process_code} · ${target.machine_no} · 剩余 ${target.remaining_qty} 件`"/></el-select><el-button v-if="targets.length<info.targets_total" link :disabled="busy" @click="moreTargets">读取更多目标订单</el-button><p v-if="!targets.length" class="note">暂无当前账号可见且工艺兼容的目标订单。</p></el-form-item>
        <el-form-item label="子框扫码"><div class="scan-row"><el-input v-model="childText" aria-label="子框扫码" :disabled="busy" placeholder="扫描一张未绑定标签" @keyup.enter="scanChild"/><el-button :disabled="busy || !childText.trim()" @click="scanChild">核对子标签</el-button></div><p v-if="verifiedChild" class="note">子标签可用，确认拆分时才绑定。</p></el-form-item>
        <div class="quantity-fields"><el-form-item label="拆出数量"><input v-model.number="amount" class="quantity-input" type="number" inputmode="numeric" :disabled="busy" min="1" :max="parent.current_qty" step="1" aria-label="拆出数量"/></el-form-item><el-form-item label="从来源订单用途中拆出"><input v-model.number="fromOrder" class="quantity-input" type="number" inputmode="numeric" :disabled="busy" :min="Math.max(0,(amount||0)-info.stock_qty)" :max="Math.min(amount||0,info.order_qty)" step="1" aria-label="拆出来源订单用途"/></el-form-item></div>
        <p class="note">从来源备货用途中拆出 {{fromStock}} 件。{{mode==='cross'?'子框全部计入目标订单用途。':'子框保留拆出的订单和备货用途。'}}</p>
        <p v-if="selectedTarget" class="note">目标 {{selectedTarget.plan_no}} 当前剩余需求 {{selectedTarget.remaining_qty}} 件。<span v-if="(amount||0)>selectedTarget.remaining_qty" class="error">目标剩余需求不足。</span></p>
        <dl class="balance"><div><dt>父框预计余量</dt><dd>{{Math.max(0,parent.current_qty-(amount||0))}} <small>件</small></dd></div><div><dt>子框数量</dt><dd>{{amount||0}} <small>件</small></dd></div></dl>
        <p class="note">取消不会绑定标签或扣减余量。拆分后各框保留来源，可独立继续流转。</p>
        <details v-if="verifiedChild" class="identity"><summary>核对子标签编号（辅助）</summary><code>{{verifiedChild.public_code}}</code></details>
      </el-form>
    </template>
    <p v-if="error" class="error" role="alert">{{error}}</p>
    <template #footer><el-button :disabled="busy" @click="loadSource">重新读取父框</el-button><el-button :disabled="saving" @click="$emit('cancel')">取消</el-button><el-button type="primary" :loading="saving" :disabled="busy || !valid" @click="submit">确认拆分</el-button></template>
  </el-dialog>
</template>

<script setup lang="ts">
import {computed, onMounted, ref, watch} from 'vue'
import {productTraceApi} from '@/api/productTrace'
import {productBoxesApi} from '@/api/productBoxes'
import {productSplitApi} from '@/api/productSplit'
import type {ProductBox,ProductQrPoolItem,QrId} from '@/types/productBox'
import type {SplitInfo,SplitTarget} from '@/types/productTrace'
import type {SplitRequest,SplitResult} from '@/types/productSplit'
import {qrError} from '@/views/product-box-qr/messages'
const props=defineProps<{parentId:QrId}>()
const emit=defineEmits<{cancel:[];completed:[result:SplitResult]}>()
const parent=ref<ProductBox|null>(null),info=ref<SplitInfo|null>(null),planNo=ref(''),targets=ref<SplitTarget[]>([]),targetStateId=ref<QrId>()
const loading=ref(false),saving=ref(false),scanning=ref(false),targetsLoading=ref(false),error=ref(''),mode=ref<'same'|'cross'>('same')
const amount=ref<number|undefined>(30),fromOrder=ref<number|undefined>(30),childText=ref(''),verifiedChild=ref<ProductQrPoolItem|null>(null)
const busy=computed(()=>loading.value||saving.value||scanning.value||targetsLoading.value)
const fromStock=computed(()=>(amount.value||0)-(fromOrder.value||0))
const selectedTarget=computed(()=>targets.value.find(row=>row.state_id===targetStateId.value))
const integer=(value:unknown):value is number=>typeof value==='number'&&Number.isInteger(value)&&value>=0&&value<=2147483647
const valid=computed(()=>!!parent.value&&!!info.value&&!info.value.reason&&!!info.value.allocation_version
  &&!!verifiedChild.value&&verifiedChild.value.qr_payload===childText.value.trim()&&integer(amount.value)&&amount.value>0&&amount.value<=parent.value.current_qty
  &&integer(fromOrder.value)&&fromOrder.value<=info.value.order_qty&&fromStock.value>=0&&fromStock.value<=info.value.stock_qty
  &&(mode.value==='same'?info.value.allowed_actions.includes('split'):info.value.allowed_actions.includes('cross_order_split')&&!!selectedTarget.value&&amount.value<=selectedTarget.value.remaining_qty))
const requestBody=computed<Omit<SplitRequest,'idempotency_key'>>(()=>({child_qr_payload:verifiedChild.value?.qr_payload||childText.value.trim(),quantity:amount.value||0,
  order_qty:fromOrder.value||0,stock_qty:fromStock.value,expected_version:parent.value?.version||0,allocation_version:info.value?.allocation_version||0,
  ...(mode.value==='cross'&&selectedTarget.value?{target_order_product_id:selectedTarget.value.order_product_id,target_state_id:selectedTarget.value.state_id,target_state_version:selectedTarget.value.state_version}:{})}))
const requestKey=ref(crypto.randomUUID())
watch(requestBody,()=>requestKey.value=crypto.randomUUID(),{flush:'sync'})
watch(childText,()=>verifiedChild.value=null,{flush:'sync'})
watch(amount,()=>{fromOrder.value=Math.min(amount.value||0,info.value?.order_qty||0)})
async function loadSource(){if(saving.value)return;loading.value=true;error.value='';verifiedChild.value=null;childText.value='';parent.value=null;info.value=null;targets.value=[];targetStateId.value=undefined;try{const result=await productTraceApi.trace(props.parentId);parent.value=result.box;planNo.value=result.order.plan_no;info.value=result.split;targets.value=result.split?.targets||[];mode.value=result.split?.allowed_actions.includes('split')?'same':'cross';amount.value=Math.min(30,result.box.current_qty);fromOrder.value=Math.min(amount.value,result.split?.order_qty||0)}catch(reason){error.value=qrError(reason)}finally{loading.value=false}}
async function moreTargets(){if(busy.value||!info.value)return;targetsLoading.value=true;error.value='';try{const result=await productTraceApi.trace(props.parentId,{page:info.value.page+1});targets.value.push(...(result.split?.targets||[]));if(result.split)info.value={...info.value,page:result.split.page,targets_total:result.split.targets_total}}catch(reason){error.value=qrError(reason)}finally{targetsLoading.value=false}}
async function scanChild(){if(busy.value||!childText.value.trim())return;scanning.value=true;error.value='';verifiedChild.value=null;try{const result=await productBoxesApi.scan(childText.value.trim(),props.parentId);if(result.box||result.pool_item.pool_status!=='unused')throw new Error('子框必须使用池内未绑定标签。');verifiedChild.value=result.pool_item}catch(reason){error.value=qrError(reason)}finally{scanning.value=false}}
async function submit(){if(busy.value||!valid.value)return;saving.value=true;error.value='';try{const result=await productSplitApi.split(props.parentId,{...requestBody.value,idempotency_key:requestKey.value});emit('completed',result)}catch(reason){error.value=qrError(reason)}finally{saving.value=false}}
onMounted(loadSource)
</script>

<style scoped>
.quantity-input{width:150px;box-sizing:border-box;height:32px;border:1px solid var(--zephyr-border);border-radius:4px;padding:0 10px;font:inherit;color:var(--zephyr-ink);background:var(--zephyr-surface,#fff);font-variant-numeric:tabular-nums}.quantity-input:focus-visible{outline:2px solid var(--zephyr-primary);outline-offset:2px}.quantity-input:disabled{opacity:.6}
:global(.qr-split-dialog .el-dialog__body){overflow:auto;min-height:0;flex:1}:global(.qr-split-dialog .el-dialog__header),:global(.qr-split-dialog .el-dialog__footer){flex-shrink:0}
.source{padding-bottom:16px;border-bottom:1px solid var(--zephyr-border-soft);margin-bottom:16px}h3{font-size:16px;margin:0 0 8px;color:var(--zephyr-ink)}p{font-size:12px;line-height:1.7;margin:4px 0;color:var(--zephyr-muted)}.scan-row{display:flex;gap:8px;width:100%}.quantity-fields{display:flex;gap:24px;flex-wrap:wrap}.balance{display:flex;gap:48px;padding:16px 0;margin:12px 0;border-top:1px solid var(--zephyr-border-soft);border-bottom:1px solid var(--zephyr-border-soft);font-variant-numeric:tabular-nums}.balance dt{font-size:12px;color:var(--zephyr-muted)}.balance dd{margin:8px 0 0;font-size:28px;font-weight:600;color:var(--zephyr-ink)}.balance small{font-size:12px;font-weight:400}.error{color:var(--zephyr-danger);font-size:12px}.identity{font-size:11px;color:var(--zephyr-muted);margin:12px 0}.identity summary{cursor:pointer;width:fit-content}.identity code{display:block;margin-top:8px;font:11px var(--zephyr-font-mono)}summary:focus-visible{outline:2px solid var(--zephyr-primary);outline-offset:3px}:deep(.el-select){width:100%}@media(max-width:600px){.scan-row{flex-wrap:wrap}.scan-row .el-input{flex-basis:100%}.quantity-fields{gap:12px}.balance{gap:32px}}
</style>
