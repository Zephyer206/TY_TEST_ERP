<template>
  <div class="workbench-entry">
    <nav v-if="canViewBoss" class="workbench-views" aria-label="工作台视角">
      <button type="button" :class="{ active: showBoss }" :aria-pressed="showBoss" @click="selectView('boss')"><el-icon><DataAnalysis /></el-icon>总览</button>
      <button type="button" :class="{ active: !showBoss }" :aria-pressed="!showBoss" @click="selectView('tasks')"><el-icon><List /></el-icon>岗位待办</button>
      <span>{{ showBoss ? '全公司经营视角' : '现有业务处理事项' }}</span>
    </nav>
    <BossOverview v-if="showBoss" />
    <TaskWorkbench v-else />
  </div>
</template>

<script setup lang="ts">
import { computed, defineAsyncComponent } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { DataAnalysis, List } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import { usePermissionStore } from '@/stores/permission'
const BossOverview = defineAsyncComponent(() => import('./BossOverview.vue'))
const TaskWorkbench = defineAsyncComponent(() => import('./TaskWorkbench.vue'))
const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const permissionStore = usePermissionStore()
const canViewBoss = computed(() => userStore.isBoss && permissionStore.canAccessBossButtons)
// Preserve existing deep links to filtered task queues.
const hasTaskQuery = computed(() => ['scope', 'module', 'search', 'due', 'page', 'page_size'].some(key => route.query[key] !== undefined))
const showBoss = computed(() => canViewBoss.value && (route.query.view === 'boss' || (!route.query.view && !hasTaskQuery.value)))
const selectView = (view: 'boss' | 'tasks') => router.push({ path: '/workbench', query: { ...route.query, view } })
</script>

<style scoped>
.workbench-entry{min-width:0}.workbench-views{display:flex;align-items:center;gap:7px;padding-top:18px;border-bottom:1px solid var(--zephyr-border-soft)}.workbench-views button{display:flex;align-items:center;gap:7px;min-height:42px;padding:0 15px;border:0;border-bottom:2px solid transparent;background:transparent;color:var(--zephyr-muted);font:inherit;font-size:13px;cursor:pointer}.workbench-views button.active{border-bottom-color:var(--zephyr-primary);color:var(--zephyr-primary);font-weight:600}.workbench-views>span{margin-left:auto;color:var(--zephyr-subtle);font-size:11px}.workbench-views button:focus-visible{outline:2px solid var(--zephyr-primary);outline-offset:-3px}@media(max-width:600px){.workbench-views{padding-top:9px}.workbench-views>span{display:none}.workbench-views button{min-height:44px}}
</style>
