<template>
  <el-dialog class="qr-exception-dialog" :model-value="true" :title="resuming?'复核并解除本条暂停':'处理卷料规格异常'" width="min(620px, calc(100vw - 32px))" top="4vh" :style="{maxHeight:'92vh',display:'flex',flexDirection:'column'}" :close-on-click-modal="false" :show-close="!saving" :close-on-press-escape="!saving" @close="!saving && $emit('cancel')">
    <h3>{{item.plan_no}} · {{item.product_name}}</h3><p>{{item.process_code}} · 批次 {{item.batch_no || '未维护批次'}}</p>
    <CoilSpecComparison :expected="item.expected_spec" :actual="item.actual_spec"/><p v-if="item.spec_incomplete" class="error">历史规格快照不完整，不能据此认定匹配或解除暂停。</p>
    <el-form label-position="top" @submit.prevent="submit">
      <template v-if="resuming"><p class="note">本次复核须符合原异常的订单规格；解除本条暂停保留原处理结果，其他未解除异常仍会阻断工艺。</p><el-form-item label="复核卷料扫码"><div class="scan-row"><el-input v-model="coilText" :disabled="busy" aria-label="复核卷料扫码" placeholder="扫描复核后的原材料或子卷标签" @keyup.enter="verify"/><el-button :disabled="busy || !coilText.trim()" @click="verify">核对复核卷料</el-button></div><p v-if="verified" class="note">已核对 {{verified.batch_no}}，规格由服务器再次比较。</p></el-form-item><el-form-item label="复核依据"><el-input v-model="reason" type="textarea" :disabled="busy" aria-label="复核依据" maxlength="500"/></el-form-item></template>
      <template v-else><el-form-item label="处理结果"><el-select v-model="resolution" :disabled="busy" aria-label="异常处理结果" placeholder="请选择本次处理结果"><el-option label="接受继续生产" value="accept_continue"/><el-option label="暂停生产" value="pause"/><el-option label="重新确认卷料" value="reconfirm_coil"/></el-select></el-form-item><p class="note">任一授权负责人确认即可。暂停或重新确认卷料仅阻断本机台订单工艺，不直接控制物理设备。</p><el-form-item label="处理备注（可留空）"><el-input v-model="remark" type="textarea" :disabled="busy" aria-label="处理备注" maxlength="500"/></el-form-item></template>
    </el-form>
    <p v-if="error" class="error" role="alert">{{error}}</p>
    <template #footer><el-button :disabled="busy" @click="$emit('reload')">重新读取异常</el-button><el-button :disabled="busy" @click="$emit('cancel')">取消</el-button><el-button type="primary" :loading="saving" :disabled="busy || (resuming? !verified || !reason.trim():!resolution)" @click="submit">{{resuming?'确认解除本条暂停':'确认处理结果'}}</el-button></template>
  </el-dialog>
</template>
<script setup lang="ts">
import {computed,ref,watch} from 'vue'
import {ElMessage} from 'element-plus'
import {coilExceptionsApi as api} from '@/api/coilExceptions'
import {materialQrApi} from '@/api/materialQr'
import type {CoilException,CoilResolution} from '@/types/coilException'
import type {MaterialBatchScanResponse} from '@/types/legacyQr'
import {qrError} from '@/views/product-box-qr/messages'
import CoilSpecComparison from './CoilSpecComparison.vue'
const props=defineProps<{item:CoilException}>(),emit=defineEmits<{cancel:[];reload:[];completed:[]}>()
const resuming=computed(()=>props.item.allowed_actions.includes('resume'))
const resolution=ref<CoilResolution>(),remark=ref(''),reason=ref(''),coilText=ref(''),verified=ref<MaterialBatchScanResponse|null>(null)
const saving=ref(false),checking=ref(false),error=ref(''),busy=computed(()=>saving.value||checking.value),requestKey=ref(crypto.randomUUID())
watch(coilText,()=>{verified.value=null},{flush:'sync'})
watch([resolution,remark,reason,verified],()=>requestKey.value=crypto.randomUUID(),{flush:'sync'})
async function verify(){if(busy.value)return;checking.value=true;error.value='';verified.value=null;try{const raw=coilText.value.trim(),id=Number(/^MAT:([1-9]\d*):\d{8}(?:\d{6})?(?::.*)?$/.exec(raw)?.[1]);if(!Number.isSafeInteger(id)||id<1||id>2147483647)throw new Error('请扫描有效的原材料或子卷标签。');const result=await materialQrApi.scanQr(id);if(result.qr_code!==raw)throw new Error('扫码内容与已保存材料身份不一致。');verified.value=result}catch(e){error.value=qrError(e)}finally{checking.value=false}}
async function submit(){if(busy.value)return;if(resuming.value? !verified.value||!reason.value.trim():!resolution.value)return;saving.value=true;error.value='';try{if(resuming.value)await api.resume(props.item.id,{rechecked_material_batch_id:verified.value!.id,reason:reason.value,expected_version:props.item.version,idempotency_key:requestKey.value});else await api.confirm(props.item.id,{resolution:resolution.value!,remark:remark.value||null,expected_version:props.item.version,idempotency_key:requestKey.value});ElMessage.success(resuming.value?'本条暂停已解除，请重新核对当前工艺':'处理结果已保存');emit('completed')}catch(e){error.value=qrError(e)}finally{saving.value=false}}
</script>
<style scoped>
:global(.qr-exception-dialog .el-dialog__body){overflow:auto;min-height:0;flex:1}:global(.qr-exception-dialog .el-dialog__header),:global(.qr-exception-dialog .el-dialog__footer){flex-shrink:0}h3{font-size:16px;margin:0 0 8px;color:var(--zephyr-ink)}p{font-size:12px;line-height:1.7;margin:6px 0;color:var(--zephyr-muted)}.scan-row{display:flex;gap:8px;width:100%}.error{color:var(--zephyr-danger)}:deep(.el-select){width:100%}@media(max-width:600px){.scan-row{flex-wrap:wrap}.scan-row .el-input{flex-basis:100%}}
</style>
