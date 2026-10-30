<template>
  <table class="coil-spec-table"><caption class="sr-only">订单与实际卷料规格比较</caption><thead><tr><th scope="col">规格</th><th scope="col">订单要求</th><th scope="col">实际卷料</th></tr></thead><tbody><tr v-for="field in fields" :key="field.key" :class="{different:(expected[field.key]||'').toLowerCase()!==(actual[field.key]||'').toLowerCase()}"><th scope="row">{{field.label}}</th><td>{{display(expected[field.key])}}</td><td>{{display(actual[field.key])}}</td></tr></tbody></table>
</template>
<script setup lang="ts">
import type {CoilSpec} from '@/types/coilException'
defineProps<{expected:CoilSpec;actual:CoilSpec}>()
const fields:Array<{key:keyof CoilSpec;label:string}>=[{key:'material_name',label:'用料名称'},{key:'thickness',label:'厚度（mm）'},{key:'width',label:'宽度（mm）'}]
const display=(value:string|null)=>value===null?'未记录':value
</script>
<style scoped>
.coil-spec-table{width:100%;border-collapse:collapse;font-size:12px;font-variant-numeric:tabular-nums;margin:12px 0}.coil-spec-table th,.coil-spec-table td{text-align:left;padding:9px 12px;border-bottom:1px solid var(--zephyr-border-soft)}.coil-spec-table thead th{color:var(--zephyr-muted);font-weight:500;background:var(--zephyr-surface-muted,#f6f7fa)}.coil-spec-table tbody th{font-weight:500}.different td:last-child{color:var(--zephyr-danger);font-weight:600}.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}
</style>

