<template>
  <MobileShell title="生产">
    <section class="production-page">
      <div class="page-intro"><div><span class="eyebrow">Manufacturing status</span><h1>生产情况</h1></div><button class="refresh-button" type="button" :disabled="loading" @click="loadPlans"><van-icon name="replay" />刷新</button></div>
      <van-tabs v-model:active="statusFilter" shrink><van-tab title="全部" name="all" /><van-tab title="待备料" name="pending" /><van-tab title="可排产" name="ready" /></van-tabs>
      <van-loading v-if="loading" class="center-state" />
      <van-empty v-else-if="!filteredPlans.length" description="暂无生产计划" />
      <div v-else class="plan-list">
        <article v-for="plan in filteredPlans" :key="plan.id" class="plan-card">
          <div class="plan-heading"><div><strong>{{ plan.customer_part_no || '未维护客户件号' }}</strong><span v-if="plan.is_urgent" class="urgent">加急</span></div><van-tag :type="plan.material_status === 'ready' ? 'success' : 'warning'">{{ plan.material_status === 'ready' ? '可排产' : '待备料' }}</van-tag></div>
          <p class="plan-name">{{ plan.part_name || '未命名零件' }}</p>
          <dl><div><dt>订单量</dt><dd>{{ formatNumber(plan.total_qty) }}</dd></div><div><dt>剩余量</dt><dd>{{ formatNumber(plan.remaining_qty) }}</dd></div><div><dt>材料</dt><dd>{{ plan.material_name || '-' }}</dd></div><div><dt>TWP</dt><dd>{{ plan.twp_value || '待补充' }}<em v-if="plan.twp_manual_override">手动</em></dd></div></dl>
          <div class="plan-foot"><span>{{ plan.material_status === 'ready' ? '资材已确认' : '等待资材确认' }}</span><span>{{ formatDate(plan.updated_at || plan.created_at) }}</span></div>
        </article>
      </div>
    </section>
  </MobileShell>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { showToast } from 'vant'
import MobileShell from '@/components/MobileShell.vue'
import { listWorkbenchPlans } from '@/api/production'

const plans = ref([])
const loading = ref(false)
const statusFilter = ref('all')
const filteredPlans = computed(() => statusFilter.value === 'all' ? plans.value : plans.value.filter((plan) => plan.material_status === statusFilter.value))
const formatNumber = (value) => Number(value || 0).toLocaleString('zh-CN')
const formatDate = (value) => value ? new Date(value).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) : '-'
const loadPlans = async () => {
  loading.value = true
  try { const data = await listWorkbenchPlans({ limit: 100 }); plans.value = data.items || [] }
  catch (error) { showToast({ message: error.message || '获取生产情况失败', position: 'top' }) } finally { loading.value = false }
}
onMounted(loadPlans)
</script>

<style scoped>
.production-page { padding: 14px 0 20px; }
.page-intro { display: flex; align-items: flex-end; justify-content: space-between; padding: 0 16px 10px; }
.eyebrow { color: #87948f; font-size: 10px; letter-spacing: .08em; text-transform: uppercase; }
h1 { margin: 5px 0 0; color: #26353a; font-size: 22px; letter-spacing: -.02em; }
.refresh-button { display: inline-flex; align-items: center; gap: 5px; min-height: 36px; padding: 0 10px; border: 1px solid #d8e1df; border-radius: 4px; color: #176b5a; background: #fff; }
.plan-list { display: grid; gap: 10px; padding: 12px 12px 0; }
.plan-card { padding: 13px; border: 1px solid #d8e1df; border-radius: 6px; background: #fff; box-shadow: 0 2px 7px rgba(38, 53, 58, .04); }
.plan-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; }
.plan-heading strong { color: #176b5a; font-size: 15px; }
.urgent { display: inline-flex; margin-left: 6px; padding: 2px 5px; border-radius: 3px; color: #a56b12; background: #fff2d5; font-size: 10px; font-weight: 700; }
.plan-name { margin: 5px 0 12px; color: #596a70; font-size: 13px; }
dl { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 9px 14px; margin: 0; }
dt { color: #8a989d; font-size: 11px; } dd { margin: 3px 0 0; overflow: hidden; color: #3e5157; font-size: 13px; text-overflow: ellipsis; white-space: nowrap; } dd em { margin-left: 4px; color: #a56b12; font-size: 10px; font-style: normal; }
.plan-foot { display: flex; justify-content: space-between; gap: 8px; padding-top: 10px; margin-top: 12px; border-top: 1px solid #eef2f1; color: #819096; font-size: 11px; }
.center-state { padding: 36px 0; text-align: center; }
:deep(.van-tabs__line) { background: #176b5a; }
</style>
