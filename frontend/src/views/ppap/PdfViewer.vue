<template>
  <div class="ppap-pdf-viewer">
    <div v-if="pageCount" class="ppap-pdf-controls" aria-label="文档阅读工具">
      <el-button :disabled="pageNumber <= 1 || rendering" @click="go(pageNumber - 1)">上一页</el-button><span>第 {{ pageNumber }} / {{ pageCount }} 页</span><el-button :disabled="pageNumber >= pageCount || rendering" @click="go(pageNumber + 1)">下一页</el-button>
      <el-select v-model="zoom" aria-label="预览缩放" @change="render"><el-option label="适合宽度" value="fit" /><el-option v-for="n in [50, 75, 100, 125, 150, 200, 300]" :key="n" :label="`${n}%`" :value="String(n)" /></el-select>
    </div>
    <div v-if="error" class="ppap-preview-status" role="alert"><p>{{ error }}</p><el-button @click="load">重新加载文档</el-button></div>
    <div v-else ref="host" class="ppap-pdf-scroll" :aria-busy="rendering || loading">
      <p v-if="loading || rendering" class="ppap-pdf-loading" role="status">正在显示文档…</p>
      <canvas ref="canvas" role="img" :aria-label="`文档第${pageNumber}页`" />
    </div>
    <details v-if="pageText" class="ppap-pdf-text"><summary>查看本页文字</summary><pre>{{ pageText }}</pre></details>
  </div>
</template>
<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'
interface PdfPage {
  getViewport(options: { scale: number }): { width: number; height: number }
  render(options: Record<string, unknown>): { promise: Promise<void>; cancel(): void }
  getTextContent(): Promise<{ items: { str?: string; hasEOL?: boolean }[] }>
}
interface PdfDocument { numPages: number; getPage(n: number): Promise<PdfPage>; destroy(): Promise<void> }
const props = defineProps<{ data: Blob; page: number }>()
const emit = defineEmits<{ 'page-change': [number] }>()
const host = ref<HTMLElement | null>(null), canvas = ref<HTMLCanvasElement | null>(null)
const pageCount = ref(0), pageNumber = ref(1), zoom = ref('fit'), loading = ref(false), rendering = ref(false), error = ref(''), pageText = ref('')
let document: PdfDocument | null = null, request = 0, renderRequest = 0
let renderTask: { promise: Promise<void>; cancel(): void } | null = null
async function load() {
  const current = ++request
  renderTask?.cancel(); if (document) { void document.destroy(); document = null }
  loading.value = true; error.value = ''; pageCount.value = 0; pageText.value = ''
  try {
    const assets = `${import.meta.env.BASE_URL}vendor/pdfjs/`
    const library = await import(/* @vite-ignore */ `${assets}pdf.mjs`)
    library.GlobalWorkerOptions.workerSrc = `${assets}pdf.worker.mjs`
    const task = library.getDocument({ data: new Uint8Array(await props.data.arrayBuffer()), cMapUrl: `${assets}cmaps/`, cMapPacked: true, standardFontDataUrl: `${assets}standard_fonts/`, wasmUrl: `${assets}wasm/`, iccUrl: `${assets}iccs/`, isEvalSupported: false })
    const loaded: PdfDocument = await task.promise
    if (current !== request) { void loaded.destroy(); return }
    document = loaded; pageCount.value = loaded.numPages; pageNumber.value = Math.min(Math.max(1, props.page), loaded.numPages)
    loading.value = false; await nextTick(); await render()
  } catch (e) { if (current === request) error.value = `文档显示失败：${(e as Error).message}` } finally { if (current === request) loading.value = false }
}
async function render() {
  if (!document || !canvas.value || !host.value) return
  const current = ++renderRequest; renderTask?.cancel(); rendering.value = true
  try {
    const pdfPage = await document.getPage(pageNumber.value)
    if (current !== renderRequest) return
    const original = pdfPage.getViewport({ scale: 1 })
    const desired = zoom.value === 'fit' ? Math.max(0.2, (host.value.clientWidth - 32) / original.width) : Number(zoom.value) / 100
    const pixelRatio = Math.min(window.devicePixelRatio || 1, 2)
    const scale = Math.min(desired * pixelRatio, Math.sqrt(16000000 / (original.width * original.height)), 16384 / original.width, 16384 / original.height)
    const viewport = pdfPage.getViewport({ scale })
    canvas.value.width = Math.ceil(viewport.width); canvas.value.height = Math.ceil(viewport.height)
    canvas.value.style.width = `${original.width * desired}px`; canvas.value.style.height = `${original.height * desired}px`
    const context = canvas.value.getContext('2d')
    if (!context) throw new Error('浏览器无法创建文档画布')
    renderTask = pdfPage.render({ canvas: canvas.value, canvasContext: context, viewport })
    await renderTask.promise
    if (current === renderRequest) pageText.value = (await pdfPage.getTextContent()).items.map(i => (i.str || '') + (i.hasEOL ? '\n' : ' ')).join('')
  } catch (e) { if (current === renderRequest && (e as Error).name !== 'RenderingCancelledException') error.value = `文档显示失败：${(e as Error).message}` } finally { if (current === renderRequest) rendering.value = false }
}
function go(n: number) { pageNumber.value = Math.min(Math.max(1, n), pageCount.value); emit('page-change', pageNumber.value) }
watch(() => props.data, () => void load(), { immediate: true })
watch(() => props.page, n => { if (document) { pageNumber.value = Math.min(Math.max(1, n), pageCount.value); void render() } })
onBeforeUnmount(() => { request++; renderRequest++; renderTask?.cancel(); if (document) void document.destroy() })
</script>
