<template>
  <dl class="quality-snapshot"><div><dt>不良数量</dt><dd>{{ record.quantity.toLocaleString() }}</dd></div><div><dt>处理方案</dt><dd>{{ planLabel(record) }}</dd></div><div><dt>处理要求</dt><dd>{{ record.treatment || '未填写' }}</dd></div><div><dt>计划完成</dt><dd>{{ record.plannedDate || '未安排' }}</dd></div><div><dt>负责人</dt><dd>{{ record.assignee || '未填写' }}</dd></div><div><dt>处理顺序</dt><dd>{{ record.priority }}</dd></div></dl>
  <div v-if="inspection" class="quality-inspection-evidence"><h4>本次验收明细</h4><div v-for="check in inspection.checks || []" :key="check.id" class="quality-criterion"><strong>{{ record.inspectionItems.find(item => item.id === check.id)?.name || '验收项目' }} · {{ check.passed === true ? '通过' : check.passed === false ? '不通过' : '未判定' }}</strong><p>{{ check.actual || '未填写实测 / 核实结果' }}</p></div><p>实物数量：{{ inspection.quantityChecked ? '已核对' : '未确认' }} · 放行及发货要求：{{ inspection.releaseChecked ? '已核对' : '未确认 / 不适用' }}</p></div>
  <DefectSupplementDetails :record="record" historical />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { normalizeDefect, planLabel, type DefectRecord, type InspectionEvidence } from '@/domain/nonconforming'
import DefectSupplementDetails from './DefectSupplementDetails.vue'
const props = defineProps<{ value: string }>()
const parsed = computed(() => JSON.parse(props.value) as DefectRecord & { inspection?: InspectionEvidence })
const record = computed(() => normalizeDefect(parsed.value))
const inspection = computed(() => parsed.value.inspection)
</script>
