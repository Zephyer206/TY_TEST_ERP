<template>
  <el-dialog v-model="visible" :title="`${name} · V${version?.version || 1}`" width="min(1280px, 96vw)" top="3vh" class="ppap-preview-dialog" destroy-on-close @closed="release">
    <div v-if="version" class="ppap-preview-meta"><span>{{ version.created_by }} · {{ formatDate(version.created_at) }}</span><span v-if="version.extension !== '.pdf'">Excel阅读预览 · 每个工作表对应一页</span><el-button v-if="canWrite" :loading="downloading" @click="download">下载原文件</el-button></div>
    <div v-if="version?.sheets.length" class="ppap-sheet-tabs" aria-label="工作表"><el-button v-for="(sheet, index) in version.sheets" :key="index" :type="activeSheet === index ? 'primary' : 'default'" size="small" @click="activeSheet = index">{{ sheet }}</el-button></div>
    <div v-if="loading" class="ppap-preview-status" role="status" aria-live="polite"><el-icon class="is-loading"><Loading /></el-icon><p>正在生成在线预览，请稍候…</p></div>
    <div v-else-if="error" class="ppap-preview-status" role="alert"><p>{{ error }}</p><el-button @click="load">重试预览</el-button></div>
    <PdfViewer v-else-if="pdfData" :data="pdfData" :page="activeSheet + 1" @page-change="activeSheet = $event - 1" />
    <template #footer><el-button @click="visible = false">关闭预览</el-button></template>
  </el-dialog>
</template>
<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { Loading } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { ppapApi, type PpapVersion } from '@/api/ppap'
import type { CompanyKey } from '@/stores/company'
import PdfViewer from './PdfViewer.vue'
const props = defineProps<{ modelValue: boolean; company: CompanyKey; archiveId: string; version: PpapVersion | null; name: string; canWrite: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [boolean] }>()
const visible = computed({ get: () => props.modelValue, set: v => emit('update:modelValue', v) })
const pdfData = ref<Blob | null>(null), loading = ref(false), error = ref(''), activeSheet = ref(0), downloading = ref(false)
let request = 0
function release() { request++; pdfData.value = null }
function formatDate(value: string) { return new Date(value.endsWith('Z') ? value : `${value}Z`).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false }) }
async function load() {
  release(); const current = request
  if (!props.version) return
  loading.value = true; error.value = ''; activeSheet.value = 0
  try { const data = await ppapApi.preview(props.company, props.archiveId, props.version.id); if (current === request && visible.value) pdfData.value = data } catch (e) { if (current === request) error.value = (e as Error).message } finally { if (current === request) loading.value = false }
}
watch(() => [props.modelValue, props.version?.id], () => { if (props.modelValue) void load(); else release() })
async function download() {
  if (!props.version) return
  downloading.value = true
  try {
    const data = await ppapApi.original(props.company, props.archiveId, props.version.id)
    const link = document.createElement('a'); const target = URL.createObjectURL(data); link.href = target; link.download = props.name; link.click(); setTimeout(() => URL.revokeObjectURL(target), 1000)
  } catch (e) { ElMessage.error((e as Error).message) } finally { downloading.value = false }
}
onBeforeUnmount(release)
</script>
