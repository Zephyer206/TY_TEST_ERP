<template>
  <section v-loading="loading" class="surface-editor" aria-label="零件表面处理资料">
    <div class="surface-header"><div><strong>零件表面处理</strong><p>统一保存在零件档案，核算引用同一份处理要求。</p></div><span>资料版本 {{ form.revision }}</span></div>
    <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon class="surface-alert" />
    <el-form label-position="top">
      <el-form-item label="处理要求状态"><el-select v-model="form.status" aria-label="处理要求状态" @change="statusChanged"><el-option label="待确认" value="pending" /><el-option label="明确无需处理" value="none" /><el-option label="需要处理" value="required" /></el-select></el-form-item>
      <p v-if="form.status === 'none'" class="muted">本次明确该零件无需表面处理。</p>
      <div v-for="(item,index) in form.items" :key="item.item_key" class="surface-row">
        <el-form-item :label="`处理方式 ${index+1}`"><el-input v-model="item.name" placeholder="例如电镀、喷涂" /></el-form-item>
        <el-form-item label="技术要求"><el-input v-model="item.requirements" placeholder="颜色、膜厚、标准等" /></el-form-item>
        <el-form-item label="要求来源"><el-input v-model="item.source" placeholder="图纸或核对依据" /></el-form-item>
        <el-button link type="danger" :aria-label="`删除处理项目 ${index+1}`" @click="form.items.splice(index,1); saved=false">删除</el-button>
      </div>
      <el-button v-if="form.status !== 'none'" plain @click="add">新增处理项目</el-button>
    </el-form>
    <div class="surface-footer"><el-button type="primary" :loading="saving" :disabled="loading || loadFailed" @click="save">保存到零件档案</el-button><el-button @click="load">重新加载</el-button><span v-if="saved" role="status">表面处理已保存到零件；成本核算需另行保存。</span></div>
  </section>
</template>
<script setup lang="ts">
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { partTreatmentsApi, costingError } from '@/api/costing'
import type { SurfaceTreatment } from '@/types/costing'
const props = defineProps<{partId: number | string; source?: string}>()
const emit = defineEmits<{saved: [value: SurfaceTreatment]}>()
const form = ref<SurfaceTreatment>({status:'pending',revision:0,items:[]})
const loading=ref(false), saving=ref(false), error=ref(''), saved=ref(false)
const loadFailed=ref(true)
async function load() { loading.value=true; error.value=''; saved.value=false
  try { form.value=(await partTreatmentsApi.detail(props.partId)).surface_treatment; loadFailed.value=false } catch(e) { error.value=costingError(e); loadFailed.value=true } finally { loading.value=false } }
function statusChanged() { saved.value=false; if(form.value.status==='none') form.value.items=[] }
function add() { form.value.items.push({item_key:crypto.randomUUID(),name:'',requirements:'',source:''}); form.value.status='required'; saved.value=false }
async function save() { saving.value=true; error.value=''
  try { const r=await partTreatmentsApi.save(props.partId,{expected_revision:form.value.revision,surface_treatment:form.value,source:props.source||'零件维护'})
    form.value=r.surface_treatment; saved.value=true; emit('saved',r.surface_treatment); ElMessage.success('表面处理已保存到零件档案')
  } catch(e) { error.value=costingError(e); saved.value=false } finally { saving.value=false } }
watch(()=>props.partId,load,{immediate:true})
</script>
<style scoped>
.surface-editor{padding:16px 0}.surface-header,.surface-footer{display:flex;gap:16px;align-items:center;justify-content:space-between}.surface-header p{color:var(--zephyr-muted,#647477);font-size:13px;margin:6px 0 18px}.surface-header span{font-variant-numeric:tabular-nums;color:#647477;font-size:12px}.surface-row{display:grid;grid-template-columns:1fr 1.7fr 1.4fr auto;gap:12px;align-items:center}.surface-footer{justify-content:flex-start;flex-wrap:wrap;margin-top:18px}.surface-footer span{font-size:12px;color:#46745c}.surface-alert{margin-bottom:14px}.muted{color:#647477;font-size:13px}@media(max-width:760px){.surface-row{grid-template-columns:1fr}.surface-header{align-items:flex-start}}
</style>
