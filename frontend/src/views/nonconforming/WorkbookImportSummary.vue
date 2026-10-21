<template>
  <section class="quality-import-summary" aria-label="Excel 导入概况">
    <div class="quality-import-summary-top"><div><strong>Excel 数据已入库</strong><span class="quality-origin-file" :title="bundle.fileName">{{ bundle.fileName }}</span></div><span>{{ bundle.sourceRows }} 行原记录 → {{ records.length }} 条明细</span></div>
    <p>合并 {{ bundle.mergedDuplicateRows }} 行跨表重复，{{ bundle.splitRows }} 行按单件 / 成品拆分。保留原表进度及日期；其中 {{ records.filter(row => row.historicalCompletion).length }} 条已按实际完成日期结案，其余继续按系统流程处理。历史结案不补造验收分项。</p>
    <div class="quality-import-summary-bottom"><span>数量可直接读取：{{ knownQuantity.toLocaleString() }} 件（{{ knownRecords.length }} 条）</span><el-button link type="warning" @click="$emit('review')">查看 {{ reviewCount }} 条数量待核对记录</el-button><span>暂归天越，公司权属待核对。</span></div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { DefectRecord } from '@/domain/nonconforming'
import type { WorkbookBundle } from '@/domain/nonconformingImport'
const props = defineProps<{ bundle: WorkbookBundle; records: DefectRecord[] }>()
defineEmits<{ review: [] }>()
const knownRecords = computed(() => props.records.filter(row => row.quantityVerified))
const knownQuantity = computed(() => knownRecords.value.reduce((sum, row) => sum + row.quantity, 0))
const reviewCount = computed(() => props.records.filter(row => !row.quantityVerified).length)
</script>
