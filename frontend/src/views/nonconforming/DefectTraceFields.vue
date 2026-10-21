<template>
  <div class="quality-form-divider"><strong>数量、状态与实物追溯</strong><span>同一条记录对应同一种零件及产品形态。</span></div>
  <div class="quality-form-grid">
    <el-form-item label="产品状态 / 版本"><el-input v-model="draft.trace.productState" placeholder="如：新状态、老状态、设变前" maxlength="120" /></el-form-item>
    <el-form-item label="字码 / 标识现状"><el-input v-model="draft.trace.marking" placeholder="如：无字码、原字码需保留" maxlength="120" /></el-form-item>
    <el-form-item label="产品形态"><el-select v-model="draft.trace.stockForm" clearable placeholder="按实物填写"><el-option label="单件" value="single" /><el-option label="成品" value="finished" /></el-select></el-form-item>
    <el-form-item label="退货批次 / 单号"><el-input v-model="draft.trace.returnBatch" placeholder="与生产批次分开记录" maxlength="120" /></el-form-item>
    <el-form-item label="预计后续退货（件）"><el-input-number v-model="draft.trace.expectedReturnQty" :min="0" :max="1000000000" :precision="0" controls-position="right" /><span class="quality-field-help">只作预警，不计入本条不良数量；实物到货后另行核实登记。</span></el-form-item>
    <el-form-item label="关联不良记录号"><el-input v-model="draft.trace.relatedRecordNo" placeholder="同一事件的单件 / 成品、原退货记录等" maxlength="120" /></el-form-item>
    <el-form-item label="隔离存放位置"><el-input v-model="draft.trace.isolationLocation" placeholder="仓库、隔离区或货架" maxlength="120" /></el-form-item>
    <el-form-item label="箱号 / 容器号"><el-input v-model="draft.trace.containerNo" placeholder="支持记录多个箱号" maxlength="200" /></el-form-item>
  </div>
  <el-form-item label="数量来源 / 核对说明"><el-input v-model="draft.trace.quantityBasis" type="textarea" :rows="2" maxlength="1000" placeholder="如：6300与3700分别来自哪里，是否与原记录重叠；单件与成品应分条登记" /></el-form-item>
  <div class="quality-editor-heading"><strong>数量分项 <small>可选，合计须等于实际不良数量</small></strong><el-button size="small" :disabled="draft.quantityLots.length >= 50" @click="addLot">添加数量分项</el-button></div>
  <div v-for="(lot, index) in draft.quantityLots" :key="lot.id" class="quality-edit-card quality-lot-editor">
    <div class="quality-editor-heading"><strong>分项 {{ index + 1 }}</strong><el-button link type="danger" :aria-label="`删除数量分项 ${index + 1}`" @click="draft.quantityLots.splice(index, 1)">删除</el-button></div>
    <div class="quality-form-grid"><el-form-item label="批次 / 来源" required><el-input v-model="lot.batch" maxlength="120" /></el-form-item><el-form-item label="分项数量（件）" required><el-input-number v-model="lot.quantity" :min="1" :max="1000000000" :precision="0" controls-position="right" /></el-form-item><el-form-item label="分项箱号"><el-input v-model="lot.container" maxlength="120" /></el-form-item><el-form-item label="分项核对说明"><el-input v-model="lot.note" maxlength="300" /></el-form-item></div>
  </div>
  <p v-if="draft.quantityLots.length" class="quality-field-help" :class="{ 'quality-danger': lotTotal !== draft.quantity }">分项合计 {{ lotTotal.toLocaleString() }} 件 / 实际不良 {{ draft.quantity.toLocaleString() }} 件。{{ lotTotal === draft.quantity ? '数量一致。' : '请核对差额后保存。' }}</p>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { DefectDraft } from '@/domain/nonconforming'
const props = defineProps<{ draft: DefectDraft }>()
const lotTotal = computed(() => props.draft.quantityLots.reduce((sum, lot) => sum + (lot.quantity || 0), 0))
function addLot() { props.draft.quantityLots.push({ id: crypto.randomUUID(), batch: '', container: '', quantity: 1, note: '' }) }
</script>
