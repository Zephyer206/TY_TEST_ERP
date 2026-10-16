<template>
  <MobileShell title="查询">
    <van-tabs v-model:active="activeTab" sticky offset-top="48px">
      <van-tab title="价格" name="price">
        <section class="query-section">
          <van-cell-group inset>
            <van-cell title="客户" :value="selectedCustomer?.name || '请选择客户'" is-link @click="customerPicker = true" />
            <van-field v-model="priceKeyword" label="件号/名称" clearable placeholder="输入客户件号或零件名称" @keyup.enter="loadPrices" />
          </van-cell-group>
          <div class="query-actions"><van-button type="primary" block :loading="priceLoading" @click="loadPrices">查询价格</van-button></div>
          <van-empty v-if="!priceLoading && priceLoaded && !filteredPrices.length" description="暂无匹配价格" />
          <van-cell-group v-else inset class="result-list">
            <van-cell v-for="row in filteredPrices" :key="row.part_id" is-link @click="openPrice(row)">
              <template #title><strong>{{ row.customer_part_no || '未维护客户件号' }}</strong></template>
              <template #label><span>{{ row.display_name || row.internal_name || '未命名零件' }}</span><span v-if="row.material_name" class="subline">{{ row.material_name }}</span></template>
              <template #value><span :class="{ 'price-missing': row.current_year_price === null }">{{ formatPrice(row.current_year_price) }}</span></template>
            </van-cell>
          </van-cell-group>
        </section>
      </van-tab>
      <van-tab title="零件" name="parts">
        <section class="query-section">
          <van-search v-model="partKeyword" placeholder="搜索客户件号、零件名称" show-action @search="loadParts" @clear="loadParts">
            <template #action><button class="search-action" type="button" @click="loadParts">搜索</button></template>
          </van-search>
          <van-loading v-if="partsLoading" class="center-state" />
          <van-empty v-else-if="partsLoaded && !parts.length" description="暂无零件" />
          <van-cell-group v-else inset class="result-list">
            <van-cell v-for="part in parts" :key="part.id" is-link @click="openPart(part)">
              <template #title><strong>{{ part.customer_part_no || '未维护客户件号' }}</strong></template>
              <template #label><span>{{ part.part_name || '未命名零件' }}</span><span class="subline">{{ [part.material_name, part.tooling_number, part.press_tonnage].filter(Boolean).join(' · ') || '规格待补充' }}</span></template>
              <template #value><van-tag :type="part.part_status === 'active' ? 'success' : 'warning'">{{ part.part_status || '未知' }}</van-tag></template>
            </van-cell>
          </van-cell-group>
        </section>
      </van-tab>
    </van-tabs>
    <van-action-sheet v-model:show="customerPicker" title="选择客户">
      <van-search v-model="customerKeyword" placeholder="搜索客户" />
      <van-cell v-for="customer in filteredCustomers" :key="customer.id" :title="customer.name" :label="customer.customer_code || ''" clickable @click="selectCustomer(customer)" />
      <van-empty v-if="!customerLoading && !filteredCustomers.length" description="暂无客户" />
    </van-action-sheet>
    <van-popup v-model:show="priceDetailVisible" position="bottom" round :style="{ height: 'auto', maxHeight: '82%' }">
      <div v-if="activePrice" class="detail-sheet">
        <div class="sheet-heading"><div><strong>{{ activePrice.customer_part_no || '未维护客户件号' }}</strong><p>{{ activePrice.display_name || activePrice.internal_name || '未命名零件' }}</p></div><van-icon name="cross" size="20" @click="priceDetailVisible = false" /></div>
        <van-cell-group inset><van-cell title="本年价格" :value="formatPrice(activePrice.current_year_price)" /><van-cell title="上年价格" :value="formatPrice(activePrice.previous_year_price)" /><van-cell title="材料" :value="activePrice.material_name || '-'" /><van-cell title="价格备注" :value="activePrice.notes || '-'" /></van-cell-group>
      </div>
    </van-popup>
    <van-popup v-model:show="partDetailVisible" position="bottom" round :style="{ height: 'auto', maxHeight: '88%' }">
      <div v-if="activePart" class="detail-sheet"><div class="sheet-heading"><div><strong>{{ activePart.customer_part_no || '未维护客户件号' }}</strong><p>{{ activePart.part_name || '未命名零件' }}</p></div><van-icon name="cross" size="20" @click="partDetailVisible = false" /></div><van-cell-group inset><van-cell title="TWP" :value="activePart.spec_twph || 'TWP 待补充'" /><van-cell title="模具号" :value="activePart.tooling_number || '-'" /><van-cell title="材料" :value="activePart.material_name || '-'" /><van-cell title="冲床吨位" :value="activePart.press_tonnage || '-'" /><van-cell title="库存" :value="String(activePart.stock_pcs ?? 0) + ' 件'" /></van-cell-group></div>
    </van-popup>
  </MobileShell>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { showToast } from 'vant'
import MobileShell from '@/components/MobileShell.vue'
import { listCustomers } from '@/api/customers'
import { listCustomerYearPrices } from '@/api/customerPrices'
import { listParts } from '@/api/parts'

const route = useRoute()
const activeTab = ref(route.query.tab === 'parts' ? 'parts' : 'price')
const customers = ref([])
const customerKeyword = ref('')
const selectedCustomer = ref(null)
const customerPicker = ref(false)
const customerLoading = ref(false)
const priceKeyword = ref('')
const prices = ref([])
const priceLoaded = ref(false)
const priceLoading = ref(false)
const activePrice = ref(null)
const priceDetailVisible = ref(false)
const partKeyword = ref('')
const parts = ref([])
const partsLoaded = ref(false)
const partsLoading = ref(false)
const activePart = ref(null)
const partDetailVisible = ref(false)

const filteredCustomers = computed(() => {
  const keyword = customerKeyword.value.trim().toLowerCase()
  return customers.value.filter((customer) => !keyword || (customer.name + ' ' + (customer.customer_code || '')).toLowerCase().includes(keyword))
})
const filteredPrices = computed(() => {
  const keyword = priceKeyword.value.trim().toLowerCase()
  return prices.value.filter((row) => !keyword || [row.customer_part_no, row.display_name, row.internal_name, row.material_name].filter(Boolean).some((value) => String(value).toLowerCase().includes(keyword)))
})
const formatPrice = (value) => value === null || value === undefined ? '暂无价格' : 'USD ' + Number(value).toFixed(4)
const loadCustomers = async () => {
  customerLoading.value = true
  try { const data = await listCustomers({ limit: 200, has_parts: true }); customers.value = data.items || data || [] }
  catch (error) { showToast({ message: error.message || '获取客户失败', position: 'top' }) } finally { customerLoading.value = false }
}
const selectCustomer = (customer) => { selectedCustomer.value = customer; customerPicker.value = false; customerKeyword.value = ''; priceLoaded.value = false; prices.value = [] }
const loadPrices = async () => {
  if (!selectedCustomer.value) { customerPicker.value = true; return }
  priceLoading.value = true
  try { const data = await listCustomerYearPrices(selectedCustomer.value.id); prices.value = data.parts || []; priceLoaded.value = true }
  catch (error) { showToast({ message: error.message || '获取价格失败', position: 'top' }) } finally { priceLoading.value = false }
}
const openPrice = (row) => { activePrice.value = row; priceDetailVisible.value = true }
const loadParts = async () => {
  partsLoading.value = true
  try { parts.value = await listParts({ search: partKeyword.value.trim() || undefined, limit: 50 }); partsLoaded.value = true }
  catch (error) { showToast({ message: error.message || '获取零件失败', position: 'top' }) } finally { partsLoading.value = false }
}
const openPart = (part) => { activePart.value = part; partDetailVisible.value = true }
onMounted(() => { loadCustomers(); loadParts() })
</script>

<style scoped>
.query-section { padding: 12px 0 18px; }
.query-actions { padding: 12px 16px; }
.result-list { margin-top: 12px; }
.result-list :deep(.van-cell__title) { min-width: 0; }
.result-list strong { color: #176b5a; font-size: 14px; }
.subline { display: block; margin-top: 4px; color: #7a888c; font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.price-missing { color: #a56b12; }
.search-action { border: 0; color: #176b5a; background: transparent; font-size: 14px; }
.center-state { padding: 28px 0; text-align: center; }
.detail-sheet { padding: 18px 0 calc(18px + env(safe-area-inset-bottom)); }
.sheet-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; padding: 0 18px 14px; }
.sheet-heading strong { color: #176b5a; font-size: 17px; }
.sheet-heading p { margin: 5px 0 0; color: #718087; font-size: 13px; }
:deep(.van-tabs__line) { background: #176b5a; }
</style>
