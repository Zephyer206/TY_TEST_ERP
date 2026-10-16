<template>
  <div class="dashboard">
    <van-nav-bar title="工作台" left-text="退出" @click-left="handleLogout" />

    <div class="user-info">
      <van-cell-group>
        <van-cell title="用户名" :value="userInfo.username" />
        <van-cell title="部门" :value="userInfo.department" />
        <van-cell title="角色" :value="userInfo.position" />
      </van-cell-group>
    </div>

    <van-grid :column-num="2" class="quick-actions">
      <van-grid-item icon="scan" text="扫码" to="/scan" />
      <van-grid-item icon="records" text="报工" to="/report" />
      <van-grid-item icon="orders-o" text="零件" to="/parts" />
      <van-grid-item icon="setting-o" text="设置" @click="showSettings = true" />
    </van-grid>

    <van-cell-group title="今日概览" class="stats">
      <van-cell title="报工数量" :value="stats.reportCount + ' 件'" />
      <van-cell title="良品数量" :value="stats.goodCount + ' 件'" />
      <van-cell title="待处理" :value="stats.pendingCount + ' 项'" />
    </van-cell-group>

    <van-cell-group title="快捷操作">
      <van-cell title="扫码报工" is-link to="/scan" />
      <van-cell title="查看零件" is-link to="/parts" />
    </van-cell-group>

    <!-- 设置弹窗 -->
    <van-popup v-model:show="showSettings" position="bottom" style="height: 30%">
      <van-cell-group>
        <van-cell title="当前账号" :value="userInfo.username" />
      </van-cell-group>
    </van-popup>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { showToast } from 'vant'
import { getCurrentUser, logout } from '@/api/auth'

const router = useRouter()
const userInfo = ref({
  username: '未知用户',
  department: '-',
  position: '-',
})

const stats = ref({
  reportCount: 0,
  goodCount: 0,
  pendingCount: 0,
})

const showSettings = ref(false)

onMounted(async () => {
  try { userInfo.value = await getCurrentUser() } catch { /* auth guard handles expiry */ }
})

const handleLogout = async () => {
  try {
    await logout()
  } catch (error) {
    console.error('登出失败:', error)
  }
  localStorage.clear()
  router.push('/login')
}
</script>

<style scoped>
.dashboard {
  min-height: 100vh;
  background-color: #f5f5f5;
}

.user-info {
  margin-top: 16px;
}

.quick-actions {
  margin: 16px 0;
}

.stats {
  margin: 16px 0;
}
</style>
