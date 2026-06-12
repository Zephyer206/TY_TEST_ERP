<template>
  <div class="dashboard">
    <h2>工作台</h2>
    <el-row :gutter="16">
      <el-col :span="6">
        <el-card>
          <template #header>待处理报价</template>
          <div class="stat-number">{{ stats.pendingQuotes }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card>
          <template #header>进行中生产</template>
          <div class="stat-number">{{ stats.activeProduction }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card>
          <template #header>待质检</template>
          <div class="stat-number">{{ stats.pendingQC }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card>
          <template #header>今日产出</template>
          <div class="stat-number">{{ stats.todayOutput }}</div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { reactive } from 'vue'

const stats = reactive({
  pendingQuotes: 5,
  activeProduction: 12,
  pendingQC: 8,
  todayOutput: 1234,
})
</script>

<style scoped>
.dashboard h2 {
  margin-bottom: 16px;
}

.stat-number {
  font-size: 32px;
  font-weight: bold;
  text-align: center;
  color: #409eff;
}
</style>
