<template>
  <div class="machines-workspace">
    <div class="page-header"><div><span class="eyebrow">工艺与生产</span><h2>机台</h2><p>查看冲压设备状态、能力与维护任务。</p></div><el-button disabled>新增机台</el-button></div>
    <div class="machine-actions"><button v-for="item in actions" :key="item.title" type="button" @click="showNotice(item.title)"><el-icon><component :is="item.icon" /></el-icon><strong>{{ item.title }}</strong><span>{{ item.description }}</span></button></div>
    <section class="machine-panel"><div class="panel-heading"><div><h3>设备状态</h3><p>设备数据接口接入后，按吨位、状态、模具和维修计划展示实时工作负荷。</p></div><el-button text disabled>筛选</el-button></div><el-empty description="暂无可展示的机台数据" :image-size="76" /></section>
  </div>
</template>
<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { Cpu, DataAnalysis, Finished, Tools } from '@element-plus/icons-vue'
const actions=[{title:'设备台账',description:'机台基础信息、吨位与能力',icon:Cpu},{title:'状态看板',description:'运行、空闲、故障和停机状态',icon:DataAnalysis},{title:'维护任务',description:'预防维护与故障维修记录',icon:Tools},{title:'生产负荷',description:'按计划查看设备排产负荷',icon:Finished}]
const showNotice=(title:string)=>ElMessage.info(`${title}功能将在设备接口接入后启用`)
</script>
<style scoped>
.machines-workspace{min-width:0}.page-header p,.panel-heading p{margin:6px 0 0;color:#737b85;font-size:13px}.eyebrow{color:#2f9e89;font-size:12px;font-weight:700}.machine-actions{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin-bottom:18px}.machine-actions button{min-height:116px;display:flex;flex-direction:column;align-items:flex-start;gap:8px;padding:17px;border:1px solid #e0e4e8;border-radius:6px;background:#fff;color:#30353b;text-align:left;cursor:pointer}.machine-actions button:hover{border-color:#9acfc2}.machine-actions .el-icon{color:#3a6ea5;font-size:21px}.machine-actions strong{font-size:14px}.machine-actions span{color:#747d87;font-size:12px;line-height:1.5}.machine-panel{min-height:260px;border:1px solid #e0e4e8;border-radius:6px;background:#fff}.panel-heading{display:flex;justify-content:space-between;gap:16px;padding:18px;border-bottom:1px solid #e8ebed}.panel-heading h3{margin:0;font-size:15px}@media(max-width:900px){.machine-actions{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:520px){.machine-actions{grid-template-columns:1fr}}
</style>
