<template>
  <el-dialog :model-value="modelValue" title="产品框标签打印" width="900px" top="4vh" append-to-body class="product-qr-print-dialog" :class="{ 'qr-print-ready': modelValue }" :close-on-click-modal="false" :close-on-press-escape="!confirming" :show-close="!confirming" @update:model-value="close">
    <template v-if="job">
      <div class="print-summary"><strong>{{ job.items.length }} 张标签 · A4 纵向 · 3 列 × 7 行</strong><span>共 {{ sheets.length }} 页</span></div>
      <p class="print-help">选择 A4、实际大小（100%），关闭浏览器页眉页脚。关闭或取消打印后，次数保持不变。</p>
      <div class="print-preview">
        <QrLabels :items="job.items" />
      </div>
      <div class="confirmation-area"><el-checkbox v-model="printed" :disabled="confirming">我已核对，本作业的全部标签已实际打印成功</el-checkbox><p v-if="error" class="print-error" role="alert">{{ error }}</p></div>
    </template>
    <template #footer><el-button :disabled="confirming" @click="close(false)">关闭预览</el-button><el-button :disabled="!job || confirming" @click="openPrint">打开系统打印</el-button><el-button type="primary" :disabled="!printed || !job" :loading="confirming" @click="confirm">确认已打印</el-button></template>
  </el-dialog>
  <Teleport to="body"><section v-if="modelValue && job" id="product-qr-print-sheet" aria-hidden="true"><component :is="'style'">@page { size: A4 portrait; margin: 0; }</component><QrLabels :items="job.items" /></section></Teleport>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { productBoxesApi } from '@/api/productBoxes'
import type { QrPrintJob } from '@/types/productBox'
import { qrError } from './messages'
import QrLabels from './QrLabels.vue'
const props=defineProps<{modelValue:boolean;job:QrPrintJob|null}>()
const emit=defineEmits<{(event:'update:modelValue',value:boolean):void;(event:'confirmed'):void}>()
const confirming=ref(false),printed=ref(false),error=ref(''),requestKey=ref('')
const sheets=computed(()=> { const result=[]; const labels=props.job?.items||[]; for(let i=0;i<labels.length;i+=21)result.push(labels.slice(i,i+21));return result })
watch(()=>props.job?.print_job_id,()=>{printed.value=false;error.value='';requestKey.value=crypto.randomUUID()})
function close(value:boolean) { if(!confirming.value) emit('update:modelValue',value) }
async function openPrint() { error.value=''; await nextTick(); try { await Promise.all([...document.querySelectorAll<HTMLImageElement>('.qr-print-ready .qr-label img')].map(image=>image.decode())); window.print() } catch { error.value='二维码图像尚未加载完成，请重新打开预览后重试。' } }
async function confirm(){if(!props.job||!printed.value||confirming.value)return;confirming.value=true;error.value='';try{await productBoxesApi.confirmPrint({print_job_id:props.job.print_job_id,confirmed_item_ids:props.job.items.map(i=>i.id),idempotency_key:requestKey.value});emit('confirmed');emit('update:modelValue',false)}catch(reason){error.value=qrError(reason)}finally{confirming.value=false}}
</script>

<style>
.print-summary{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap}.print-summary span,.print-help{font-size:12px;color:var(--zephyr-muted)}.print-help{line-height:1.7;margin:10px 0 16px}.print-preview{max-height:54vh;overflow:auto;background:var(--zephyr-canvas);padding:16px;border:1px solid var(--zephyr-border);border-radius:6px}.qr-paper{width:210mm;height:297mm;box-sizing:border-box;padding:10mm;display:grid;grid-template-columns:repeat(3,60mm);grid-template-rows:repeat(7,35mm);gap:5mm;background:#fff;color:#000;margin:0 auto 16px;break-after:page}.qr-label{width:60mm;height:35mm;box-sizing:border-box;padding:2mm;display:grid;grid-template-columns:24mm minmax(0,1fr);grid-template-rows:24mm 5mm;gap:1mm;align-items:start;outline:1px dashed #ddd;overflow:hidden}.qr-label img{width:24mm;height:24mm;image-rendering:pixelated}.qr-label code{grid-column:1 / -1;font:9px Consolas,monospace;white-space:nowrap;text-align:center;color:#000}.label-business{display:flex;flex-direction:column;gap:1mm;padding-top:1mm;line-height:1.25;font-size:9px;overflow-wrap:anywhere;max-height:24mm;overflow:hidden}.label-business strong{font-size:10px}.confirmation-area{margin-top:16px}.confirmation-area .el-checkbox{white-space:normal;height:auto;align-items:start}.confirmation-area .el-checkbox__label{white-space:normal;line-height:1.6}.print-error{color:var(--zephyr-danger);font-size:12px;margin:10px 0 0}.product-qr-print-dialog{max-width:calc(100vw - 24px)}
#product-qr-print-sheet{display:none}
.qr-label{grid-template-columns:minmax(0,1fr) 24mm}.qr-label .label-business{grid-column:1;grid-row:1}.qr-label img{grid-column:2;grid-row:1}
@media print{
body:has(#product-qr-print-sheet){margin:0!important;padding:0!important;overflow:visible!important;height:auto!important;min-width:0!important;background:#fff!important}
body:has(#product-qr-print-sheet)>*:not(#product-qr-print-sheet){display:none!important}
#product-qr-print-sheet{display:block!important}
#product-qr-print-sheet .qr-paper{margin:0;break-inside:avoid}
#product-qr-print-sheet .qr-paper:last-child{break-after:auto}
#product-qr-print-sheet .qr-label{outline:0}
}
</style>
