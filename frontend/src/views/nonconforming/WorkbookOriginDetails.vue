<template>
  <section v-if="origin" class="quality-detail-section quality-workbook-origin">
    <h3>原表记录 <small>{{ origin.reviewed ? '已进入系统处理流程' : '导入待核对' }}</small></h3>
    <p class="quality-origin-file">{{ origin.fileName }}</p>
    <div class="quality-origin-refs"><span v-for="source in origin.sources" :key="`${source.sheet}-${source.row}`">{{ source.sheet }} · 第 {{ source.row }} 行 · 序号 {{ source.serial }}</span><span v-if="origin.splitLabel">本条形态：{{ origin.splitLabel }}</span></div>
    <dl class="quality-details-grid"><div><dt>原表进度</dt><dd>{{ originalProgressLabels[origin.progress] }}</dd></div><div><dt>原表数量原文</dt><dd>{{ origin.raw['数量'] || '未填写' }}</dd></div><div><dt>原表预计完成</dt><dd>{{ origin.originalPlanned || '未填写' }}</dd></div><div><dt>原表实际完成 / 进展</dt><dd>{{ origin.originalActual || '未填写' }}</dd></div></dl>
    <p class="quality-origin-note">原表进度为历史参考，系统验收结果另行记录。公司权属尚待核对，当前暂归天越。</p>
    <ul class="quality-origin-review"><li v-for="note in origin.reviewNotes" :key="note">{{ note }}</li></ul>
    <details class="quality-original-cells"><summary>展开原表全部字段</summary><dl><div v-for="(value, name) in origin.raw" :key="name"><dt>{{ name }}</dt><dd>{{ value || '未填写' }}</dd></div></dl></details>
  </section>
</template>

<script setup lang="ts">
import { originalProgressLabels } from '@/domain/nonconformingImport'
import type { WorkbookOrigin } from '@/domain/nonconforming'
defineProps<{ origin?: WorkbookOrigin }>()
</script>
