<template>
  <div class="excel-filter-panel" role="dialog" :aria-label="`${title || '列'}筛选`">
    <div class="excel-filter-sort">
      <button type="button" @click="emit('sort', 'asc')">升序</button>
      <button type="button" @click="emit('sort', 'desc')">降序</button>
    </div>
    <div class="excel-filter-tabs" role="tablist" aria-label="筛选方式">
      <span class="active" role="tab" aria-selected="true">按内容</span>
    </div>
    <el-input v-model="searchText" size="small" clearable placeholder="搜索分类" aria-label="搜索分类">
      <template #prefix><el-icon><Search /></el-icon></template>
    </el-input>
    <div class="excel-filter-toolbar">
      <el-checkbox :model-value="allSelected" :indeterminate="indeterminate" @change="toggleAll(Boolean($event))">
        全选 <small>({{ options.length }})</small>
      </el-checkbox>
      <button type="button" @click="invert">反选</button>
      <button type="button" @click="reset">清除筛选</button>
    </div>
    <div class="excel-filter-options" role="group" aria-label="筛选分类">
      <div v-for="option in filteredOptions" :key="option.value" class="excel-filter-option">
        <el-checkbox :model-value="isChecked(option)" @change="toggle(option, Boolean($event))">
          <span>{{ option.label }}</span>
          <small>{{ option.count ?? 0 }}</small>
        </el-checkbox>
      </div>
      <span v-if="!filteredOptions.length" class="excel-filter-empty">没有匹配项</span>
    </div>
    <div class="excel-filter-footer">
      <button type="button" class="link-button" @click="reset">清除筛选</button>
      <button type="button" class="primary-button" @click="confirm">确定</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Search } from '@element-plus/icons-vue'
import type { ExcelFilterOption } from './types'

const props = defineProps<{ options: ExcelFilterOption[]; selectedValues?: string[]; title?: string }>()
const emit = defineEmits<{ sort: [order: 'asc' | 'desc']; apply: [values: string[]]; clear: [] }>()
const searchText = ref('')
const selected = ref(new Set<string>())
watch(() => props.selectedValues, values => { selected.value = new Set(values || []) }, { immediate: true, deep: true })
const options = computed(() => props.options || [])
const filteredOptions = computed(() => {
  const term = searchText.value.trim().toLowerCase()
  return term ? options.value.filter(option => option.label.toLowerCase().includes(term)) : options.value
})
const isChecked = (option: ExcelFilterOption) => selected.value.has(String(option.value))
const checkedCount = computed(() => options.value.filter(isChecked).length)
const allSelected = computed(() => options.value.length > 0 && checkedCount.value === options.value.length)
const indeterminate = computed(() => checkedCount.value > 0 && !allSelected.value)
function toggle(option: ExcelFilterOption, checked: boolean) {
  const next = new Set(selected.value)
  if (checked) next.add(String(option.value))
  else next.delete(String(option.value))
  selected.value = next
}
function toggleAll(checked: boolean) { selected.value = checked ? new Set(options.value.map(option => String(option.value))) : new Set() }
function invert() { selected.value = new Set(options.value.filter(option => !isChecked(option)).map(option => String(option.value))) }
function reset() { selected.value = new Set(); emit('clear') }
function confirm() { emit('apply', Array.from(selected.value)) }
</script>

<style scoped>
.excel-filter-panel { display: flex; width: 286px; height: 100%; max-height: inherit; min-height: 0; flex-direction: column; box-sizing: border-box; overflow: hidden; padding: 4px; color: #31413b; font-size: 11px; }
.excel-filter-sort, .excel-filter-tabs, .excel-filter-toolbar, .excel-filter-footer { display: flex; align-items: center; }
.excel-filter-sort { gap: 4px; padding-bottom: 4px; border-bottom: 1px solid #e5ebe8; }
.excel-filter-sort button, .excel-filter-toolbar button { border: 0; background: transparent; color: #50645d; font: inherit; cursor: pointer; }
.excel-filter-sort button { padding: 4px 8px; }
.excel-filter-sort button:hover, .excel-filter-toolbar button:hover { color: #176b5a; }
.excel-filter-tabs { gap: 20px; padding: 7px 4px 5px; color: #71807a; }
.excel-filter-tabs span { padding-bottom: 4px; }
.excel-filter-tabs .active { border-bottom: 2px solid #176b5a; color: #176b5a; font-weight: 650; }
.excel-filter-toolbar { gap: 8px; padding: 5px 0 3px; }
.excel-filter-toolbar :deep(.el-checkbox) { margin-right: auto; }
.excel-filter-toolbar small, .excel-filter-option small { color: #8a9691; font-variant-numeric: tabular-nums; }
.excel-filter-options { min-height: 0; flex: 1 1 auto; overflow: auto; padding: 2px 0; scrollbar-gutter: stable; }
.excel-filter-option { display: block; padding: 2px 2px; cursor: pointer; line-height: 18px; }
.excel-filter-option:hover { background: #f2f7f5; }
.excel-filter-panel :deep(.el-checkbox) { height: 18px; margin-right: 0; font-size: 11px; line-height: 18px; }
.excel-filter-panel :deep(.el-checkbox__input) { height: 14px; }
.excel-filter-panel :deep(.el-checkbox__inner) { width: 14px; height: 14px; }
.excel-filter-panel :deep(.el-checkbox__label) { font-size: 11px; line-height: 18px; }
.excel-filter-option :deep(.el-checkbox) { display: flex; width: 100%; }
.excel-filter-option :deep(.el-checkbox__label) { display: flex; justify-content: space-between; min-width: 0; flex: 1; gap: 8px; overflow: hidden; padding-left: 6px; }
.excel-filter-option :deep(.el-checkbox__label span) { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.excel-filter-empty { display: block; padding: 24px 8px; color: #8a9691; text-align: center; }
.excel-filter-footer { justify-content: space-between; gap: 8px; padding-top: 6px; border-top: 1px solid #e5ebe8; }
.link-button, .primary-button { min-height: 28px; padding: 0 10px; border-radius: 4px; font: inherit; cursor: pointer; }
.link-button { border: 0; background: transparent; color: #176b5a; }
.primary-button { border: 1px solid #176b5a; background: #176b5a; color: #fff; }

/* VXE computes a conservative inline max-height for transferred filter popups.
   Keep the panel usable on short screens while giving long value lists room. */
:global(.excel-filter-popup) {
  height: min(420px, calc(100vh - 88px)) !important;
  max-height: min(420px, calc(100vh - 88px)) !important;
}
:global(.excel-filter-popup .vxe-table--filter-template) {
  height: min(420px, calc(100vh - 88px)) !important;
  max-height: min(420px, calc(100vh - 88px)) !important;
}
</style>
