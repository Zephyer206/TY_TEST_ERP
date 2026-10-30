<template>
  <section class="exception-panel" aria-label="当前工艺卷料规格"><h3>卷料规格与异常</h3>
    <template v-if="canCheck"><p class="note">核对订单用料与实际卷料；规格不一致须明确记录异常后继续，负责人可另行决定暂停。</p><div class="scan-row"><el-input v-model="coilText" :disabled="busy || disabled" aria-label="规格核对卷料扫码" placeholder="扫描实际原材料或子卷标签" @keyup.enter="check(false)"/><el-button :disabled="busy || disabled || !coilText.trim()" @click="check(false)">核对卷料规格</el-button></div>
      <div v-if="probe" class="comparison"><p><strong>{{probe.matches?'规格匹配':probe.requires_confirmation?'规格不一致，尚未记录异常':'规格不一致，已有处理记录'}}</strong><span v-if="verified"> · {{verified.batch_no}}</span></p><CoilSpecComparison :expected="probe.expected_spec" :actual="probe.actual_spec"/><el-button v-if="probe.requires_confirmation" type="primary" :disabled="busy || disabled || !verified" @click="check(true)">记录异常并继续生产</el-button><p v-else-if="!probe.production_allowed" class="error">当前工艺仍有未解除暂停，请由负责人处理。</p><p v-else class="note">{{probe.matches?'本次卷料已核对。':'异常已记录，负责人处理前允许继续。'}}数量仍需在产品框中另行保存。</p></div>
    </template>
    <p v-if="error" class="error" role="alert">{{error}}</p>
    <p v-if="!items.length" class="note empty">当前工艺暂无规格异常。</p>
    <article v-for="item in items" :key="item.id" class="exception-row"><div class="row-heading"><strong>{{item.batch_no || '未维护批次'}} · {{item.status==='pending_confirmation'?'待确认':'已确认'}}</strong><el-button v-if="item.allowed_actions.includes('confirm')" link :disabled="busy || disabled" @click="selected=item">处理异常</el-button><el-button v-if="item.allowed_actions.includes('resume')" link :disabled="busy || disabled" @click="selected=item">复核并恢复</el-button></div><p>{{outcome(item)}}<span v-if="item.remark"> · {{item.remark}}</span></p><p class="delivery">通知投递：待投递 {{item.delivery_summary.pending}} · 已投递 {{item.delivery_summary.sent}} · 失败 {{item.delivery_summary.failed}}<span v-if="item.recipient_groups.some(g=>g.resolution_status==='pending_configuration')" class="error"> · 收件组配置待补齐</span></p><details><summary>查看规格与处理依据</summary><CoilSpecComparison :expected="item.expected_spec" :actual="item.actual_spec"/><p>创建账号 {{item.created_by}}<span v-if="item.confirmed_by"> · 确认账号 {{item.confirmed_by}}</span><span v-if="item.released_at"> · 本条暂停已解除：{{item.resume_reason}}</span></p></details></article>
    <ExceptionDecisionDialog v-if="selected" :item="selected" @cancel="selected=null" @reload="reload" @completed="reload"/>
  </section>
</template>
<script setup lang="ts">
import {ref,watch} from 'vue'
import {coilExceptionsApi as api} from '@/api/coilExceptions'
import {materialQrApi} from '@/api/materialQr'
import type {QrId} from '@/types/productBox'
import type {CoilCheckResult,CoilException} from '@/types/coilException'
import type {MaterialBatchScanResponse} from '@/types/legacyQr'
import {qrError} from '@/views/product-box-qr/messages'
import CoilSpecComparison from './CoilSpecComparison.vue'
import ExceptionDecisionDialog from './ExceptionDecisionDialog.vue'
const props=defineProps<{contextId:QrId;productBoxId?:QrId;canCheck:boolean;items:CoilException[];disabled?:boolean}>()
const emit=defineEmits<{updated:[];checked:[material:MaterialBatchScanResponse];inputChanged:[value:string];decision:[allowed:boolean]}>()
const coilText=ref(''),verified=ref<MaterialBatchScanResponse|null>(null),probe=ref<CoilCheckResult|null>(null),busy=ref(false),error=ref(''),selected=ref<CoilException|null>(null)
const requestKey=ref(crypto.randomUUID());let sequence=0
watch(coilText,()=>{sequence++;verified.value=null;probe.value=null;requestKey.value=crypto.randomUUID();emit('inputChanged',coilText.value)},{flush:'sync'})
watch(()=>[props.contextId,props.productBoxId],()=>{sequence++;coilText.value='';verified.value=null;probe.value=null;error.value='';selected.value=null})
function outcome(item:CoilException){if(item.status==='pending_confirmation')return '等待主管或本单业务人员确认；通知投递不代替业务确认。';if(item.released_at)return '本条暂停已解除，原处理结果保留。';return ({accept_continue:'接受继续生产；规格差异保留记录。',pause:'暂停本机台订单工艺。',reconfirm_coil:'等待重新确认卷料，本机台订单工艺暂停。'} as Record<string,string>)[item.resolution||'']||'等待处理'}
function reload(){selected.value=null;emit('updated')}
async function check(proceed:boolean){if(busy.value||props.disabled)return;busy.value=true;error.value='';const request=sequence;try{const raw=coilText.value.trim();if(!proceed){verified.value=null;probe.value=null;const id=Number(/^MAT:([1-9]\d*):\d{8}(?:\d{6})?(?::.*)?$/.exec(raw)?.[1]);if(!Number.isSafeInteger(id)||id<1||id>2147483647)throw new Error('请扫描有效的原材料或子卷标签。');const result=await materialQrApi.scanQr(id);if(request!==sequence)return;if(result.qr_code!==raw)throw new Error('扫码内容与已保存材料身份不一致。');verified.value=result;requestKey.value=crypto.randomUUID()}if(!verified.value||verified.value.qr_code!==raw)throw new Error('请重新核对实际卷料。');emit('checked',verified.value);const result=await api.check({context_id:props.contextId,material_batch_id:verified.value.id,...(props.productBoxId?{product_box_id:props.productBoxId}:{}),continue_production:proceed,idempotency_key:`${proceed?'record':'preview'}-${requestKey.value}`});if(request!==sequence)return;probe.value=result;emit('decision',result.production_allowed);if(proceed)emit('updated')}catch(e){if(request===sequence){error.value=qrError(e);emit('decision',false)}}finally{busy.value=false}}
</script>
<style scoped>
.exception-panel{padding:20px 0;border-top:1px solid var(--zephyr-border-soft);margin-top:20px;color:var(--zephyr-ink)}h3{font-size:14px;margin:0 0 10px}.scan-row{display:flex;gap:8px;margin:12px 0}.scan-row .el-input{max-width:650px}p{font-size:12px;line-height:1.7;margin:6px 0}.note,.delivery{color:var(--zephyr-muted)}.error{color:var(--zephyr-danger)}.comparison{max-width:760px;padding:12px 0}.exception-row{padding:14px 0;border-top:1px solid var(--zephyr-border-soft)}.row-heading{display:flex;align-items:center;gap:12px;font-size:13px}.empty{padding:8px 0}summary{font-size:12px;color:var(--zephyr-muted);cursor:pointer;width:fit-content}summary:focus-visible{outline:2px solid var(--zephyr-primary);outline-offset:3px}@media(max-width:600px){.scan-row{flex-wrap:wrap}.scan-row .el-input{flex-basis:100%}.row-heading{flex-wrap:wrap}}
</style>
