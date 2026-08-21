<template>
  <VxeTable
    ref="tableRef"
    class="excel-grid"
    :data="data"
    :height="height"
    border="inner"
    show-overflow="ellipsis"
    show-header-overflow="ellipsis"
    :column-config="{ resizable: true, useKey: true }"
    :sort-config="{ remote: true, multiple: false }"
    :filter-config="{ remote: true, transfer: true, showFooter: false, className: 'excel-filter-popup' }"
    :row-config="{ isHover: true, keyField: rowKey }"
    @cell-click="handleCellClick"
    @sort-change="handleSortChange"
    @column-resizable-change="handleColumnResize"
    @column-dragend="handleColumnDragEnd"
  >
    <VxeColumn
      v-for="column in columns"
      :key="column.key"
      :field="column.key"
      :title="column.label"
      :width="column.width"
      :min-width="column.minWidth"
      :align="column.align"
      :sortable="column.sortable"
      :fixed="column.fixed"
      :filters="column.filters"
      :filter-multiple="column.filterMultiple !== false"
    >
      <template #header="{ column: tableColumn }">
        <span class="excel-grid-header" :data-excel-column="column.key" draggable="true" @dragstart="startColumnDrag(column.key)" @dragover.prevent @drop="dropColumn(column.key)" @pointerdown="beginPointerColumnDrag($event, column.key)" @pointerup="finishPointerColumnDrag($event, column.key)" @mousedown="beginPointerColumnDrag($event, column.key)" @mouseup="finishPointerColumnDrag($event, column.key)"><span>{{ tableColumn.title }}</span><span v-if="column.filters?.length" class="excel-filter-mark" aria-hidden="true">⌄</span></span>
      </template>
      <template #filter>
        <ExcelFilterPanel :options="column.filters || []" :selected-values="selectedFilters[column.key] || []" :title="column.label" @sort="(order) => emit('sort-change', { field: column.key, order })" @apply="(values) => applyFilter(column.key, values)" @clear="() => applyFilter(column.key, [])" />
      </template>
      <template #default="{ row }"><slot name="cell" :row="row" :column="column"><slot :name="`cell-${column.key}`" :row="row" :column="column"><span>{{ column.formatter ? column.formatter(row) : (row[column.key] ?? '—') }}</span></slot></slot></template>
    </VxeColumn>
  </VxeTable>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import ExcelFilterPanel from './ExcelFilterPanel.vue'
import type { ExcelGridColumn, ExcelGridFilterValues } from './types'

defineProps<{ data: any[]; columns: ExcelGridColumn[]; height?: string | number; loading?: boolean; rowKey?: string }>()
const emit = defineEmits<{
  'row-click': [row: any]
  'sort-change': [payload: { field: string; order: 'asc' | 'desc' | null }]
  'filter-change': [filters: ExcelGridFilterValues]
  'column-resize': [payload: { field: string; width: number }]
  'column-order-change': [payload: { oldField?: string; newField?: string }]
}>()
const tableRef = ref()
const selectedFilters = reactive<ExcelGridFilterValues>({})
const draggingField = ref<string | null>(null)
function handleCellClick(params: any) { emit('row-click', params.row) }
function handleSortChange(params: any) { emit('sort-change', { field: params.field, order: params.order || null }) }
function applyFilter(field: string, values: string[]) {
  if (values.length) selectedFilters[field] = values
  else delete selectedFilters[field]
  tableRef.value?.closeFilter?.()
  emit('filter-change', { ...selectedFilters })
}
function handleColumnResize(params: any) { if (params.column?.field) emit('column-resize', { field: params.column.field, width: Number(params.resizeWidth || params.column.renderWidth || 0) }) }
function handleColumnDragEnd(params: any) { emit('column-order-change', { oldField: params.oldColumn?.field, newField: params.newColumn?.field }) }
function startColumnDrag(field: string) { draggingField.value = field }
function dropColumn(targetField: string) {
  const oldField = draggingField.value
  draggingField.value = null
  if (oldField && oldField !== targetField) emit('column-order-change', { oldField, newField: targetField })
}
function beginPointerColumnDrag(event: MouseEvent, field: string) { if (event.button === 0) draggingField.value = field }
function finishPointerColumnDrag(event: MouseEvent, fallbackField: string) {
  if (event.button !== 0) return
  const target = document.elementFromPoint(event.clientX, event.clientY)?.closest<HTMLElement>('[data-excel-column]')
  dropColumn(target?.dataset.excelColumn || fallbackField)
}
function clearFilters() { Object.keys(selectedFilters).forEach(field => delete selectedFilters[field]); tableRef.value?.clearFilter?.() }
defineExpose({ tableRef, clearFilters })
</script>

<style scoped>
.excel-grid { width: 100%; height: 100%; --vxe-ui-font-size: 12px; --vxe-ui-font-color: #30413a; --vxe-ui-table-header-background-color: #f5f8f7; --vxe-ui-table-border-color: #dce5e1; --vxe-ui-table-row-hover-background-color: #f2f7f5; font-variant-numeric: tabular-nums; }
.excel-grid-header { display: inline-flex; align-items: center; gap: 3px; font-weight: 650; cursor: grab; user-select: none; }
.excel-grid-header:active { cursor: grabbing; }
.excel-filter-mark { color: #7d8b85; font-size: 11px; line-height: 1; }
.excel-grid :deep(.vxe-cell--sort), .excel-grid :deep(.vxe-cell--filter) { font-size: 10px; }
.excel-grid :deep(.vxe-cell--filter) { padding-inline: 2px; }
</style>
