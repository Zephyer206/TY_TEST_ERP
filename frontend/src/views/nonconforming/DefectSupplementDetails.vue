<template>
  <section class="quality-detail-section"><h3>状态、数量来源与隔离位置</h3>
    <dl class="quality-details-grid"><div v-for="item in traceFields" :key="item[0]"><dt>{{ item[0] }}</dt><dd>{{ item[1] || '未填写' }}</dd></div></dl>
    <p v-if="record.trace.expectedReturnQty" class="quality-forecast">预计后续退货 <b>{{ record.trace.expectedReturnQty.toLocaleString() }}</b> 件，仅供准备，未计入本条不良数量。</p>
    <p v-if="record.trace.quantityBasis" class="quality-detail-description">数量核对：{{ record.trace.quantityBasis }}</p>
    <div v-if="record.quantityLots.length" class="quality-lot-list"><div v-for="lot in record.quantityLots" :key="lot.id"><strong>{{ lot.batch }} · {{ lot.quantity.toLocaleString() }} 件</strong><span>{{ lot.container ? `箱号 ${lot.container}` : '未填写分项箱号' }}</span><p v-if="lot.note">{{ lot.note }}</p></div></div>
  </section>
  <section class="quality-detail-section"><h3>处理步骤 <small>{{ record.historicalCompletion ? '执行明细未登记' : record.status === 'pending_confirmation' ? '待确认方案' : record.quantityVerified ? `本轮针对剩余 ${remainingQty(record).toLocaleString()} 件` : '实际数量待核对' }}</small></h3>
    <p v-if="!record.planSteps.length" class="quality-muted">尚未明确处理步骤。</p>
    <ol v-else class="quality-treatment-steps"><li v-for="(step, index) in record.planSteps" :key="step.id" :class="{ 'is-done': step.completedAt, 'is-current': !historical && record.status === 'processing' && activeStep(record)?.id === step.id }">
      <span class="quality-step-number">{{ index + 1 }}</span><div class="quality-treatment-content"><div class="quality-editor-heading"><strong>{{ stepLabels[step.kind] }}</strong><span class="quality-secondary">{{ step.completedAt ? '已完成' : record.historicalCompletion ? '未登记' : record.status === 'pending_confirmation' ? '待确认' : !historical && record.status === 'processing' && activeStep(record)?.id === step.id ? '当前步骤' : '待执行' }}</span></div><p>{{ step.requirement }}</p><div v-if="step.completedAt" class="quality-secondary">{{ step.completedBy }} · {{ formatTime(step.completedAt) }}<p>{{ step.result }}</p></div><el-button v-if="!historical && canComplete && record.status === 'processing' && activeStep(record)?.id === step.id" size="small" type="primary" plain :disabled="step.kind === 'rework' && !record.moldReady" @click="$emit('complete', step.id)">记录本步完成</el-button><p v-if="!step.completedAt && step.kind === 'rework' && !record.moldReady && record.status !== 'closed'" class="quality-warning">返工模具尚未就绪</p></div>
    </li></ol>
    <p v-if="!historical && record.status === 'processing' && !activeStep(record) && !(record.importedProgress && !record.importInfo?.reviewed)" class="quality-success quality-field-help">本轮步骤已完成，可以提交实际完成数量，等待品质验收。</p>
  </section>
  <section class="quality-detail-section"><h3>品质验收标准</h3><div v-for="item in record.inspectionItems" :key="item.id" class="quality-criterion"><strong>{{ item.name }}</strong><p>{{ item.standard }}</p></div><p v-if="!record.inspectionItems.length" class="quality-muted">尚未明确验收项目及标准。</p></section>
  <section class="quality-detail-section"><h3>放行与发货要求</h3><dl class="quality-details-grid"><div><dt>放行方式</dt><dd>{{ record.release.mode === 'concession' ? '让步放行' : '按标准验收' }}</dd></div><div v-for="item in releaseFields" :key="item[0]"><dt>{{ item[0] }}</dt><dd>{{ item[1] || '未填写' }}</dd></div></dl></section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { activeStep, remainingQty, stepLabels, type DefectRecord } from '@/domain/nonconforming'
const props = defineProps<{ record: DefectRecord; canComplete?: boolean; historical?: boolean }>()
defineEmits<{ complete: [stepId: string] }>()
const traceFields = computed(() => { const t = props.record.trace; return [['产品状态 / 版本', t.productState], ['字码 / 标识现状', t.marking], ['产品形态', t.stockForm === 'single' ? '单件' : t.stockForm === 'finished' ? '成品' : ''], ['退货批次 / 单号', t.returnBatch], ['隔离存放位置', t.isolationLocation], ['箱号 / 容器号', t.containerNo], ['关联不良记录号', t.relatedRecordNo]] })
const releaseFields = computed(() => { const r = props.record.release; return [['批准人 / 单位', r.approvedBy], ['放行依据', r.basis], ['处理后对应零件号', r.outputPartNo], ['发货去向', r.destination], ['标识要求', r.labeling], ['包装 / 放置要求', r.packing], ['批次 / 余料要求', r.batchRequirement]] })
const formatTime = (value: string) => value === 'legacy' ? '旧版未记录完成时间' : new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Shanghai', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }).format(new Date(value))
</script>
