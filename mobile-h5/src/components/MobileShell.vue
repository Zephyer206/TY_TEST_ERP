<template>
  <div class="mobile-shell">
    <van-nav-bar :title="title" :left-arrow="back" @click-left="back ? router.back() : (openMore = true)">
      <template #left>
        <van-icon v-if="!back" name="apps-o" size="20" aria-label="打开更多" />
      </template>
      <template #right>
        <button class="profile-button" type="button" aria-label="退出登录" @click="logout">
          <van-icon name="contact" size="18" />
        </button>
      </template>
    </van-nav-bar>

    <main class="mobile-shell__content"><slot /></main>

    <van-tabbar v-model="activeTab" route safe-area-inset-bottom>
      <van-tabbar-item name="query" icon="search" to="/query">查询</van-tabbar-item>
      <van-tabbar-item name="production" icon="records" to="/production">生产</van-tabbar-item>
      <van-tabbar-item name="delivery" icon="logistics" to="/delivery">交付</van-tabbar-item>
      <van-tabbar-item name="scan" icon="scan" to="/scan">扫码</van-tabbar-item>
    </van-tabbar>

    <van-action-sheet v-model:show="openMore" title="更多入口">
      <van-cell-group inset>
        <van-cell title="零件查询" icon="orders-o" is-link to="/query?tab=parts" @click="openMore = false" />
        <van-cell title="退出登录" icon="close" is-link @click="logout" />
      </van-cell-group>
    </van-action-sheet>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

defineProps({
  title: { type: String, required: true },
  back: { type: Boolean, default: false },
})

const router = useRouter()
const route = useRoute()
const openMore = ref(false)
const activeTab = ref('query')

watch(() => route.path, (path) => {
  activeTab.value = path.startsWith('/production') ? 'production'
    : path.startsWith('/delivery') ? 'delivery'
      : path.startsWith('/scan') ? 'scan' : 'query'
}, { immediate: true })

const logout = () => {
  localStorage.removeItem('access_token')
  localStorage.removeItem('refresh_token')
  localStorage.removeItem('mobile_user')
  openMore.value = false
  router.replace('/login')
}
</script>

<style scoped>
.mobile-shell { min-height: 100dvh; padding-bottom: calc(50px + env(safe-area-inset-bottom)); background: #f3f6f5; color: #26353a; }
.mobile-shell__content { min-height: calc(100dvh - 46px); }
.profile-button { display: grid; width: 32px; height: 32px; place-items: center; border: 0; border-radius: 4px; color: #176b5a; background: transparent; }
.profile-button:active { background: #e4f2ee; }
:deep(.van-nav-bar) { --van-nav-bar-height: 48px; --van-nav-bar-title-font-size: 16px; --van-nav-bar-text-color: #176b5a; --van-nav-bar-icon-color: #176b5a; position: sticky; top: 0; z-index: 10; border-bottom: 1px solid #d8e1df; }
:deep(.van-tabbar) { border-top: 1px solid #d8e1df; }
:deep(.van-tabbar-item--active) { color: #176b5a; }
:deep(.van-action-sheet__content) { padding: 8px 0 16px; }
</style>
