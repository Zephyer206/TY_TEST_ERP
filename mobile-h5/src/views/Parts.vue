<template>
  <div class="parts-page">
    <van-nav-bar title="我的零件" left-text="返回" @click-left="router.back()" />

    <van-pull-refresh v-model="refreshing" @refresh="onRefresh">
      <van-list
        v-model:loading="loading"
        :finished="finished"
        finished-text="没有更多了"
        @load="onLoad"
      >
        <van-cell
          v-for="item in partsList"
          :key="item.id"
          :title="item.part_number"
          :label="item.customer_name + ' | ' + item.status"
          @click="showDetail(item)"
        >
          <template #value>
            <van-tag :type="getStatusType(item.status)">
              {{ item.status }}
            </van-tag>
          </template>
        </van-cell>
      </van-list>
    </van-pull-refresh>

    <van-empty v-if="!loading && partsList.length === 0" description="暂无零件" />

    <!-- 零件详情弹窗 -->
    <van-popup v-model:show="showPartDetail" position="bottom" style="height: 60%">
      <div v-if="selectedPart" style="padding: 16px">
        <h3>{{ selectedPart.part_number }}</h3>
        <van-cell-group>
          <van-cell title="客户" :value="selectedPart.customer_name" />
          <van-cell title="状态" :value="selectedPart.status" />
          <van-cell title="数量" :value="selectedPart.quantity || '-'" />
          <van-cell title="模具" :value="selectedPart.mold_name || '-'" />
        </van-cell-group>
      </div>
    </van-popup>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { showToast } from 'vant'

const router = useRouter()
const serverUrl = localStorage.getItem('server_url') || 'http://124.222.29.229:8000'

const loading = ref(false)
const refreshing = ref(false)
const finished = ref(false)
const partsList = ref([])
const page = ref(1)

const showPartDetail = ref(false)
const selectedPart = ref(null)

const getStatusType = (status) => {
  const statusMap = {
    'draft': 'default',
    'pending': 'warning',
    'approved': 'success',
    'in_production': 'primary',
    'completed': 'success',
  }
  return statusMap[status?.toLowerCase()] || 'default'
}

const onLoad = async () => {
  try {
    const response = await fetch(`${serverUrl}/api/parts?page=${page.value}&limit=20`, {
      credentials: 'include',
    })
    if (response.ok) {
      const data = await response.json()
      if (data.items) {
        partsList.value.push(...data.items)
        page.value++
        if (data.items.length < 20) {
          finished.value = true
        }
      } else {
        finished.value = true
      }
    }
  } catch (error) {
    console.error('加载零件失败:', error)
  } finally {
    loading.value = false
  }
}

const onRefresh = async () => {
  partsList.value = []
  page.value = 1
  finished.value = false
  await onLoad()
  refreshing.value = false
  showToast({ message: '刷新成功', position: 'top' })
}

const showDetail = (item) => {
  selectedPart.value = item
  showPartDetail.value = true
}
</script>

<style scoped>
.parts-page {
  min-height: 100vh;
  background-color: #f5f5f5;
}
</style>
