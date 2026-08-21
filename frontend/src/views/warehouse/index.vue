<template>
  <div class="inventory-workspace">
    <div class="page-header">
      <div>
        <span class="eyebrow">库存</span>
        <h2>库存工作台</h2>
        <p>集中查看库存余额与仓储作业，后续业务页面将在此模块内展开。</p>
      </div>
      <el-button type="primary" disabled title="库存作业接口接入后启用">新建库存作业</el-button>
    </div>

    <div class="inventory-actions">
      <button v-for="item in actions" :key="item.title" class="inventory-action" type="button" @click="showPlanned(item.title)">
        <el-icon><component :is="item.icon" /></el-icon>
        <strong>{{ item.title }}</strong>
        <span>{{ item.description }}</span>
      </button>
    </div>

    <section class="inventory-panel">
      <div class="panel-heading">
        <div>
          <h3>库存余额</h3>
          <p>库存接口接入后，此处将按仓库、材料和零件展示可用数量、在途数量与预警状态。</p>
        </div>
        <el-button text disabled>筛选</el-button>
      </div>
      <el-empty description="暂无可展示的库存数据" :image-size="76">
        <template #description>
          <p>库存作业与余额接口尚未接入，页面结构已准备完成。</p>
        </template>
      </el-empty>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { Box, Connection, Finished, Tickets } from '@element-plus/icons-vue'

const actions = [
  { title: '库存余额', description: '按仓库与物料查询现存数量', icon: Box },
  { title: '收货与入库', description: '登记采购或生产完工入库', icon: Finished },
  { title: '发货与出库', description: '登记领料、发货与其他出库', icon: Tickets },
  { title: '调拨与盘点', description: '处理库位调拨和盘点差异', icon: Connection },
]

const showPlanned = (title: string) => ElMessage.info(`${title}功能将在库存接口接入后启用`)
</script>

<style scoped>
.inventory-workspace { min-width: 0; }
.page-header > div { min-width: 0; }
.page-header p { margin: 6px 0 0; color: #737b85; font-size: 13px; }
.eyebrow { color: #2f9e89; font-size: 12px; font-weight: 700; }
.inventory-actions { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin-bottom: 18px; }
.inventory-action { min-height: 126px; display: flex; flex-direction: column; align-items: flex-start; gap: 8px; padding: 18px; border: 1px solid #e0e4e8; border-radius: 6px; background: #fff; color: #30353b; text-align: left; cursor: pointer; transition: border-color .15s, box-shadow .15s; }
.inventory-action:hover { border-color: #9acfc2; box-shadow: 0 4px 12px rgba(23, 87, 73, .08); }
.inventory-action .el-icon { color: #2f9e89; font-size: 22px; }
.inventory-action strong { font-size: 14px; }
.inventory-action span { color: #7a838d; font-size: 12px; line-height: 1.55; }
.inventory-panel { min-height: 280px; border: 1px solid #e0e4e8; border-radius: 6px; background: #fff; }
.panel-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; padding: 18px; border-bottom: 1px solid #e8ebed; }
.panel-heading h3 { margin: 0; font-size: 15px; }
.panel-heading p { margin: 6px 0 0; color: #7a838d; font-size: 12px; }
@media (max-width: 900px) { .inventory-actions { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 520px) { .inventory-actions { grid-template-columns: 1fr; } }
</style>
