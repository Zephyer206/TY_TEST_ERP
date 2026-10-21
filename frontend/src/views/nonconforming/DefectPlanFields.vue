<template>
  <div class="quality-editor-heading"><strong>处理步骤 <small>按确认顺序执行</small></strong><el-button size="small" :disabled="draft.planSteps.length >= 12" @click="draft.planSteps.push(makeStep(draft.disposition || 'rework'))">添加处理步骤</el-button></div>
  <p class="quality-field-help">可组合挑选 → 返工 → 后处理。只有返工步骤检查模具就绪；步骤完成不计入已验收数量。</p>
  <div v-for="(step, index) in draft.planSteps" :key="step.id" class="quality-edit-card quality-step-editor">
    <div class="quality-editor-heading"><strong>步骤 {{ index + 1 }}</strong><div class="quality-inline-actions"><el-button link :disabled="index === 0" :aria-label="`上移步骤 ${index + 1}`" @click="move(index, -1)">上移</el-button><el-button link :disabled="index === draft.planSteps.length - 1" :aria-label="`下移步骤 ${index + 1}`" @click="move(index, 1)">下移</el-button><el-button link type="danger" :aria-label="`删除步骤 ${index + 1}`" @click="draft.planSteps.splice(index, 1)">删除</el-button></div></div>
    <el-form-item label="步骤类型" required><el-select v-model="step.kind"><el-option v-for="kind in stepKinds" :key="kind" :label="stepLabels[kind]" :value="kind" /></el-select></el-form-item>
    <el-form-item label="本步处理要求" required><el-input v-model="step.requirement" type="textarea" :rows="2" maxlength="1000" placeholder="如：先挑变形，再返工尺寸，最后补标识" /></el-form-item>
  </div>
  <p v-if="!draft.planSteps.length" class="quality-field-help">确认前须添加步骤。报废作为单独方案；部分产品需报废时，先退回讨论剩余数量。</p>
  <div class="quality-form-divider"><strong>品质验收项目</strong><span>确认前明确标准，验收时逐项记录实测或核实结果。</span></div>
  <div v-for="(item, index) in draft.inspectionItems" :key="item.id" class="quality-edit-card quality-inspection-editor">
    <div class="quality-editor-heading"><strong>项目 {{ index + 1 }}</strong><el-button link type="danger" :aria-label="`删除验收项目 ${index + 1}`" @click="draft.inspectionItems.splice(index, 1)">删除</el-button></div>
    <div class="quality-form-grid"><el-form-item label="验收项目" required><el-input v-model="item.name" placeholder="如：力值、开口、字码、报废凭据" maxlength="120" /></el-form-item><el-form-item label="验收标准" required><el-input v-model="item.standard" placeholder="如：12–16.5N；按客户确认文件" maxlength="500" /></el-form-item></div>
  </div>
  <el-button size="small" :disabled="draft.inspectionItems.length >= 30" @click="draft.inspectionItems.push(makeInspectionItem())">添加验收项目</el-button>
  <div class="quality-form-divider"><strong>放行与发货要求</strong><span>品质、业务及仓储共同查看，确认后随方案锁定。</span></div>
  <div class="quality-form-grid">
    <el-form-item label="放行方式"><el-select v-model="draft.release.mode"><el-option label="按标准验收" value="standard" /><el-option label="让步放行" value="concession" /></el-select></el-form-item>
    <el-form-item label="批准人 / 批准单位" :required="draft.release.mode === 'concession'"><el-input v-model="draft.release.approvedBy" placeholder="让步放行时必填" maxlength="120" /></el-form-item>
  </div>
  <el-form-item label="放行依据" :required="draft.release.mode === 'concession'"><el-input v-model="draft.release.basis" type="textarea" :rows="2" maxlength="1000" placeholder="客户确认单、批准日期、文件编号或批准范围" /></el-form-item>
  <div class="quality-form-grid"><el-form-item label="处理后对应零件号"><el-input v-model="draft.release.outputPartNo" placeholder="仅记录本次对应关系" maxlength="120" /></el-form-item><el-form-item label="发货去向"><el-input v-model="draft.release.destination" placeholder="客户收货地 / 工厂，如安吉、重庆" maxlength="200" /></el-form-item></div>
  <el-form-item label="标识要求"><el-input v-model="draft.release.labeling" type="textarea" :rows="2" maxlength="1000" placeholder="返工标识、客户标签、字码等" /></el-form-item>
  <div class="quality-form-grid"><el-form-item label="包装 / 放置要求"><el-input v-model="draft.release.packing" type="textarea" :rows="2" maxlength="1000" placeholder="如：放箱子底部" /></el-form-item><el-form-item label="批次 / 余料要求"><el-input v-model="draft.release.batchRequirement" type="textarea" :rows="2" maxlength="1000" placeholder="如：单独批次、余料清理、不得混箱" /></el-form-item></div>
</template>

<script setup lang="ts">
import { makeInspectionItem, makeStep, stepKinds, stepLabels, type DefectDraft } from '@/domain/nonconforming'
const props = defineProps<{ draft: DefectDraft }>()
function move(index: number, direction: number) {
  const steps = props.draft.planSteps; const target = index + direction
  if (target < 0 || target >= steps.length) return
  const current = steps[index]; steps[index] = steps[target]; steps[target] = current
}
</script>
