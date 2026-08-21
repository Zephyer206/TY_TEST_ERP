<template>
  <div class="price-management-container">
    <div class="page-header">
      <h2>价格管理</h2>
    </div>

    <el-card>
      <el-tabs v-model="activeTab">
        <el-tab-pane label="价格查询" name="query">
          <CustomerPricesQuery />
        </el-tab-pane>
        <el-tab-pane label="调价管理" name="adjustments">
          <PriceAdjustments />
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import CustomerPricesQuery from './CustomerPricesQuery.vue'
import PriceAdjustments from './PriceAdjustments.vue'

const activeTab = ref('query')
</script>

<style scoped>
.price-management-container {
  padding: 20px;
}

.page-header {
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0;
}
</style>
