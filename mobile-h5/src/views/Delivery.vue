<template>
  <MobileShell title="交付">
    <section class="delivery-page">
      <van-tabs v-model:active="activeTab" sticky offset-top="48px">
        <van-tab title="库存" name="inventory">
          <div class="toolbar"><van-search v-model="keyword" placeholder="搜索零件号" @search="loadInventory" /><button class="refresh-button" type="button" @click="loadInventory"><van-icon name="replay" /></button></div>
          <van-loading v-if="loading" class="center-state" />
          <van-empty v-else-if="!filteredInventory.length" description="暂无库存记录" />
          <van-cell-group v-else inset><van-cell v-for="item in filteredInventory" :key="item.part_id || item.id" :title="item.part_number || item.part_name || '未命名零件'" :label="item.part_name || item.material_name || '库存记录'" :value="String(item.stock_pcs ?? item.quantity ?? 0) + ' 件'" /></van-cell-group>
        </van-tab>
        <van-tab title="包装/发货" name="packaging">
          <div class="toolbar"><van-search v-model="keyword" placeholder="搜索包装号或零件" @search="loadPackaging" /><button class="refresh-button" type="button" @click="loadPackaging"><van-icon name="replay" /></button></div>
          <van-loading v-if="loading" class="center-state" />
          <van-empty v-else-if="!filteredPackaging.length" description="暂无包装记录" />
          <van-cell-group v-else inset><van-cell v-for="item in filteredPackaging" :key="item.id" :title="item.package_no || '未命名包装'" :label="packagingLabel(item)"><template #value><van-tag :type="statusType(item.status)">{{ statusLabel(item.status) }}</van-tag></template></van-cell></van-cell-group>
        </van-tab>
      </van-tabs>
    </section>
  </MobileShell>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { showToast } from 'vant'
import MobileShell from '@/components/MobileShell.vue'
import { listInventory, listPackagingRecords } from '@/api/packaging'

const activeTab = ref('inventory')
const keyword = ref('')
const loading = ref(false)
const inventory = ref([])
const packaging = ref([])
const filteredInventory = computed(() => filterRows(inventory.value, ['part_number', 'part_name', 'material_name']))
const filteredPackaging = computed(() => filterRows(packaging.value, ['package_no', 'part_number', 'part_name']))
const filterRows = (rows, fields) => { const q = keyword.value.trim().toLowerCase(); return rows.filter((row) => !q || fields.some((field) => String(row[field] || '').toLowerCase().includes(q))) }
const packagingLabel = (item) => [item.part_number || item.part_name || '未命名零件', (item.package_qty || 0) + ' 件'].join(' · ')
const statusLabel = (status) => ({ scanned: '待全检', inspecting: '检验中', passed: '已入库', rejected: '不合格', shipped: '已发货' }[status] || status || '未知')
const statusType = (status) => ({ scanned: 'warning', inspecting: 'primary', passed: 'success', rejected: 'danger', shipped: 'default' }[status] || 'default')
const loadInventory = async () => { loading.value = true; try { inventory.value = await listInventory({ limit: 100 }) } catch (error) { showToast({ message: error.message || '获取库存失败', position: 'top' }) } finally { loading.value = false } }
const loadPackaging = async () => { loading.value = true; try { packaging.value = await listPackagingRecords({ limit: 100, skip: 0 }) } catch (error) { showToast({ message: error.message || '获取包装记录失败', position: 'top' }) } finally { loading.value = false } }
watch(activeTab, (tab) => { keyword.value = ''; tab === 'inventory' ? loadInventory() : loadPackaging() })
onMounted(loadInventory)
</script>

<style scoped>
.delivery-page { padding: 10px 0 20px; }
.toolbar { display: flex; align-items: center; gap: 6px; padding: 0 10px 10px; }
.toolbar :deep(.van-search) { flex: 1; padding: 0; background: transparent; }
.refresh-button { display: grid; width: 36px; height: 36px; place-items: center; border: 1px solid #d8e1df; border-radius: 4px; color: #176b5a; background: #fff; }
.center-state { padding: 36px 0; text-align: center; }
:deep(.van-tabs__line) { background: #176b5a; }
</style>
