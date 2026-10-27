<template>
  <main class="trace-workspace"><header><h1>工艺流转与追溯</h1><p>扫描产品框，核对当前订单、工艺数量和原材料来源。进入后续工艺请在机台生产中明确选单。</p></header><section class="lookup" aria-label="产品框定位"><label for="trace-box-scan">产品框扫码</label><el-input id="trace-box-scan" v-model="scanText" :disabled="loading" placeholder="扫描产品框标签" @keyup.enter="lookup"/><el-button type="primary" :loading="loading" @click="lookup">查询追溯</el-button></section><p v-if="error" class="error" role="alert">{{error}}</p><section v-if="boxId" class="content"><TraceDetail :box-id="boxId" :key="refreshKey" @navigate="navigateBox"/></section><p v-else-if="!loading && !error" class="empty">先扫描产品框，查看它的订单和完整工艺记录。</p></main>
</template>
<script setup lang="ts">
import {ref} from 'vue'
import TraceDetail from '@/components/product-box-qr/TraceDetail.vue'
import {productBoxesApi} from '@/api/productBoxes'
import {qrError} from './messages'
import type {QrId} from '@/types/productBox'
const scanText=ref(''),boxId=ref<QrId>(),loading=ref(false),error=ref(''),refreshKey=ref(0)
function navigateBox(id:QrId){scanText.value='';error.value='';boxId.value=id}
async function lookup(){if(loading.value)return;boxId.value=undefined;error.value='';if(!scanText.value.trim()){error.value='请先扫描产品框标签。';return}loading.value=true;try{const result=await productBoxesApi.scan(scanText.value.trim());if(!result.box){error.value='该标签尚未绑定订单，没有生产追溯记录。';return}boxId.value=result.box.id;refreshKey.value++}catch(reason){error.value=qrError(reason)}finally{loading.value=false}}
</script>
<style scoped>
.trace-workspace{padding:24px;color:var(--zephyr-ink)}h1{font-size:22px;margin:0 0 8px}header p,p{font-size:12px;line-height:1.7;color:var(--zephyr-muted);margin:0}header{margin-bottom:20px}.lookup{display:flex;gap:12px;align-items:center;padding:16px;background:var(--zephyr-surface);border:1px solid var(--zephyr-border);border-radius:8px}.lookup label{white-space:nowrap;font-size:12px}.lookup .el-input{max-width:650px}.content{margin-top:16px;padding:20px;background:var(--zephyr-surface);border:1px solid var(--zephyr-border);border-radius:8px}.error{color:var(--zephyr-danger);margin:12px 0}.empty{padding:32px;text-align:center}@media(max-width:700px){.trace-workspace{padding:12px}.lookup{flex-wrap:wrap}.lookup .el-input{flex-basis:100%;max-width:none}.content{padding:12px}}
</style>
