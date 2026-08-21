<template>
  <div class="app-shell">
    <header class="app-topbar">
      <div class="topbar-leading">
        <button class="app-switcher" type="button" aria-label="打开应用菜单" :aria-expanded="appMenuOpen" @click="appMenuOpen = !appMenuOpen">
          <el-icon><Grid /></el-icon>
        </button>
        <button class="brand-lockup" type="button" @click="go('/parts')">
          <span class="brand-mark">Z</span>
          <span class="brand-name">Zephyr</span>
        </button>
        <span class="topbar-divider" aria-hidden="true" />
        <nav class="module-nav" aria-label="业务模块">
          <div v-for="item in primaryNav" :key="item.key" class="module-nav-entry">
            <button
              class="module-nav-item"
              :class="{ active: activeArea === item.key || openMenuKey === item.key, disabled: item.disabled }"
              type="button"
              :disabled="item.disabled"
              :aria-current="activeArea === item.key ? 'page' : undefined"
              :aria-haspopup="item.tabs.length ? 'menu' : undefined"
              :aria-expanded="item.tabs.length ? openMenuKey === item.key : undefined"
              @click="handlePrimaryClick(item, $event)"
            >
              <el-icon><component :is="item.icon" /></el-icon>
              <span>{{ item.label }}</span>
            </button>
          </div>
        </nav>
      </div>

      <div v-if="openMenuArea" class="module-nav-submenu" role="menu" :aria-label="`${openMenuArea.label}子菜单`" :style="submenuStyle">
        <button v-for="tab in openMenuArea.tabs" :key="tab.label" type="button" role="menuitem" :disabled="tab.disabled || !tab.route" @click="tab.route && go(tab.route)">
          {{ tab.label }}
        </button>
      </div>

      <div class="topbar-actions">
        <el-dropdown @command="handleCommand">
          <button class="profile-trigger" type="button">
            <span class="avatar">{{ userInitial }}</span>
            <span class="profile-name">{{ userStore.userInfo?.real_name || '用户' }}</span>
            <el-icon><ArrowDown /></el-icon>
          </button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="logout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </header>

    <div v-if="appMenuOpen" class="app-launcher" role="menu" aria-label="应用菜单">
      <div class="launcher-title">应用</div>
      <template v-for="item in primaryNav" :key="item.key">
        <button class="launcher-item" :class="{ disabled: item.disabled }" type="button" role="menuitem" :disabled="item.disabled" @click="item.route && go(item.route)">
          <span class="launcher-icon"><el-icon><component :is="item.icon" /></el-icon></span>
          <span>{{ item.label }}</span>
        </button>
        <div v-if="item.tabs.length" class="launcher-subitems" :aria-label="`${item.label}子入口`">
          <button v-for="tab in item.tabs" :key="tab.label" class="launcher-subitem" type="button" role="menuitem" :disabled="!tab.route" @click="tab.route && go(tab.route)">
            {{ tab.label }}
          </button>
        </div>
      </template>
    </div>

    <main class="workspace">
      <nav v-if="currentArea.tabs.length" class="secondary-nav" role="navigation" :aria-label="`${currentArea.label}页面`">
        <span class="secondary-title">{{ currentArea.label }}</span>
        <button
          v-for="tab in currentArea.tabs"
          :key="tab.route || tab.label"
          class="workspace-tab"
          :class="{ active: tab.route && isRouteActive(tab.route), disabled: tab.disabled }"
          type="button"
          :disabled="tab.disabled"
          @click="tab.route && go(tab.route)"
        >{{ tab.label }}</button>
      </nav>
      <router-view />
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, type Component } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowDown, Box, Document, Grid, House, Setting, Tools } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'

type AreaKey = 'productEngineering' | 'manufacturing' | 'procurement' | 'warehouseProcessing' | 'pricing' | 'afterSales' | 'permissions'

interface WorkspaceTab { label: string; route?: string; disabled?: boolean }
interface WorkspaceArea {
  key: AreaKey
  label: string
  route?: string
  icon: Component
  tabs: WorkspaceTab[]
  disabled?: boolean
}

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const appMenuOpen = ref(false)
const openMenuKey = ref<AreaKey | null>(null)
const submenuPosition = ref({ left: 0 })

const areas: WorkspaceArea[] = [
  {
    key: 'productEngineering', label: '产品与工装', route: '/parts', icon: Box,
    tabs: [
      { label: '零件', route: '/parts' },
      { label: '模具', route: '/tooling' },
      { label: '工艺查询', disabled: true },
    ],
  },
  {
    key: 'manufacturing', label: '制造执行', icon: Tools,
    tabs: [
      { label: '生产计划', route: '/production' },
      { label: '生产排产', route: '/production/scheduling' },
      { label: '机台执行', disabled: true },
      { label: '工艺流转', disabled: true },
    ],
  },
  {
    key: 'procurement', label: '采购与外协', icon: Tools,
    tabs: [
      { label: '材料', disabled: true },
      { label: '外协', disabled: true },
    ],
  },
  {
    key: 'warehouseProcessing', label: '仓储与后处理', icon: House,
    tabs: [
      { label: '仓库', disabled: true },
      { label: '全检与包装', disabled: true },
      { label: '后处理', disabled: true },
    ],
  },
  {
    key: 'pricing', label: '价格中心', icon: Document,
    tabs: [
      { label: '价格查询', disabled: true },
      { label: '报价', disabled: true },
      { label: '客户', disabled: true },
    ],
  },
  {
    key: 'afterSales', label: '售后', icon: Box,
    tabs: [{ label: '售后档案', route: '/after-sales' }],
  },
  {
    key: 'permissions', label: '权限分配', icon: Setting, disabled: true,
    tabs: [],
  },
]

const activeArea = computed<AreaKey>(() => {
  const matchedArea = areas.find(area => area.tabs.some(tab => tab.route && isRouteActive(tab.route)))
  return matchedArea?.key || 'productEngineering'
})
const currentArea = computed(() => areas.find(area => area.key === activeArea.value) || areas[0])
const primaryNav = computed(() => areas)
const openMenuArea = computed(() => areas.find(area => area.key === openMenuKey.value) || null)
const submenuStyle = computed(() => ({ left: `${submenuPosition.value.left}px` }))
const userInitial = computed(() => (userStore.userInfo?.real_name || '用').slice(0, 1))

const go = (target: string) => {
  appMenuOpen.value = false
  openMenuKey.value = null
  if (route.path !== target) router.push(target)
}

const handlePrimaryClick = (item: WorkspaceArea, event: MouseEvent) => {
  if (item.disabled) return
  if (item.route) {
    go(item.route)
    return
  }
  openMenuKey.value = openMenuKey.value === item.key ? null : item.key
  if (!openMenuKey.value) return
  appMenuOpen.value = false
  const menuTrigger = event.currentTarget as HTMLElement | null
  if (!menuTrigger) return
  void nextTick(() => {
    const rect = menuTrigger.getBoundingClientRect()
    submenuPosition.value.left = Math.min(Math.max(rect.left, 12), window.innerWidth - 190)
  })
}

const isRouteActive = (target: string) => route.path === target || (target === '/tooling' && route.path.startsWith('/tooling'))

const handleCommand = (command: string) => {
  if (command === 'logout') {
    userStore.logout()
    router.push('/login')
  }
}
</script>

<style scoped>
.app-shell { display: flex; flex-direction: column; height: 100%; min-height: 100vh; background: #f6f7f8; color: #1f2933; }
.app-topbar { position: relative; z-index: 20; display: flex; align-items: center; justify-content: space-between; min-height: 58px; padding: 0 24px; background: #176b5a; color: #fff; }
.topbar-leading, .topbar-actions, .module-nav, .profile-trigger { display: flex; align-items: center; }
.topbar-leading { min-width: 0; height: 58px; }
.app-switcher { display: grid; place-items: center; width: 32px; height: 32px; margin-right: 8px; border: 0; border-radius: 4px; background: transparent; color: #fff; cursor: pointer; }
.app-switcher:hover, .app-switcher[aria-expanded='true'] { background: rgba(255, 255, 255, .18); }
.app-switcher .el-icon { font-size: 16px; }
.brand-lockup { display: flex; align-items: center; gap: 8px; margin-right: 12px; border: 0; background: transparent; color: #fff; font: inherit; cursor: pointer; }
.brand-mark { display: grid; place-items: center; width: 30px; height: 30px; border-radius: 4px; background: #fff; color: #176b5a; font-size: 16px; font-weight: 750; }
.brand-name { font-size: 17px; font-weight: 650; letter-spacing: -.02em; }
.topbar-divider { width: 1px; height: 30px; margin-right: 13px; background: rgba(255, 255, 255, .28); }
.module-nav { display: flex; height: 58px; gap: 0; min-width: 0; overflow-x: auto; }
.module-nav-entry { position: relative; display: flex; height: 58px; }
.module-nav-item { display: inline-flex; align-items: center; gap: 5px; height: 58px; padding: 0 10px; border: 0; outline: none; background: transparent; color: rgba(255, 255, 255, .84); font: inherit; font-size: 15px; font-weight: 550; white-space: nowrap; cursor: pointer; }
.module-nav-item:hover, .module-nav-item.active { background: rgba(255, 255, 255, .16); color: #fff; }
.module-nav-item .el-icon { flex: 0 0 auto; font-size: 14px; }
.module-nav-item:focus-visible { outline: 2px solid rgba(225, 255, 246, .92); outline-offset: -3px; }
.module-nav-item:disabled { cursor: default; opacity: .62; }
.module-nav-item:disabled:hover { background: transparent; color: rgba(255, 255, 255, .84); }
.module-nav-submenu { position: fixed; z-index: 50; top: 58px; display: grid; min-width: 170px; padding: 6px; border: 1px solid #d9dee1; background: #fff; box-shadow: 0 6px 16px rgba(15, 35, 31, .18); }
.module-nav-submenu button { min-height: 36px; padding: 0 12px; border: 0; background: #fff; color: #5f6b70; font: inherit; font-size: 13px; text-align: left; }
.module-nav-submenu button:disabled { cursor: default; opacity: .62; }
.topbar-actions { gap: 6px; }
.topbar-icon { color: #fff; }
.profile-trigger { gap: 7px; padding: 3px 5px 3px 8px; border: 0; border-radius: 3px; background: transparent; color: #fff; font: inherit; cursor: pointer; }
.profile-trigger:hover { background: rgba(255, 255, 255, .16); }
.profile-trigger .el-icon { font-size: 12px; }
.avatar { display: grid; place-items: center; width: 25px; height: 25px; border-radius: 3px; background: rgba(255, 255, 255, .2); font-size: 12px; font-weight: 700; }
.profile-name { font-size: 12px; }
.app-launcher { position: absolute; z-index: 30; top: 58px; left: 4px; display: grid; grid-template-columns: repeat(2, 150px); gap: 4px; width: 320px; padding: 12px; border: 1px solid #d9dee1; border-top: 0; background: #fff; box-shadow: 0 5px 14px rgba(15, 35, 31, .16); }
.launcher-title { grid-column: 1 / -1; padding: 2px 6px 8px; color: #6d6c75; font-size: 12px; font-weight: 650; }
.launcher-item { display: flex; align-items: center; gap: 8px; min-height: 38px; padding: 5px 6px; border: 0; border-radius: 3px; background: #fff; color: #464550; font: inherit; font-size: 13px; text-align: left; cursor: pointer; }
.launcher-item:hover { background: #eef6f3; color: #176b5a; }
.launcher-item:disabled { cursor: default; opacity: .48; }
.launcher-item:disabled:hover { background: #fff; color: #464550; }
.launcher-subitems { display: grid; grid-column: 1 / -1; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 4px; margin: -2px 0 2px 36px; }
.launcher-subitem { min-height: 28px; padding: 4px 8px; border: 0; border-radius: 3px; background: #f7f9f9; color: #7a8588; font: inherit; font-size: 12px; text-align: left; }
.launcher-icon { display: grid; place-items: center; width: 24px; height: 24px; border-radius: 3px; background: #e7f1ed; color: #176b5a; }
.launcher-icon .el-icon { font-size: 14px; }
.workspace { display: flex; flex: 1 1 auto; flex-direction: column; min-width: 0; min-height: 0; padding: 0 20px 28px; overflow: auto; }
.secondary-nav { display: flex; align-items: center; gap: 2px; min-height: 54px; margin: 0 -20px 16px; padding: 0 20px; border-bottom: 1px solid #dfe0e4; background: #fff; }
.secondary-title { margin-right: 18px; color: #34434b; font-size: 16px; font-weight: 650; }
.workspace-tab { height: 54px; padding: 0 13px; border: 0; border-bottom: 2px solid transparent; outline: none; background: transparent; color: #68747b; font: inherit; font-size: 15px; cursor: pointer; }
.workspace-tab:hover { color: #176b5a; }
.workspace-tab.active { border-bottom-color: #176b5a; color: #176b5a; font-weight: 650; }
.workspace-tab:focus-visible { outline: 2px solid rgba(23, 107, 90, .55); outline-offset: -4px; }
.workspace-tab:disabled { cursor: default; opacity: .48; }
.workspace-tab:disabled:hover { color: #68747b; }

:deep(.workspace > .after-sales-page) { flex: 1 1 auto; min-height: 0; }

/* Shared Zephyr workbench spine. Page views keep their business logic while
 * inheriting the same compact list, filter, and change-history surfaces. */
:global(:root) {
  --zephyr-primary: #176b5a;
  --zephyr-primary-soft: #e4f2ee;
  --zephyr-ink: #26353a;
  --zephyr-muted: #708087;
  --zephyr-surface: #ffffff;
  --zephyr-canvas: #f2f5f4;
  --zephyr-border: #d8e1df;
  --zephyr-warning: #b7791f;
  --zephyr-danger: #be514d;
  --zephyr-control: 32px;
  --zephyr-row: 38px;
}

:deep(.workspace > [class$='-container']),
:deep(.workspace > [class$='-workspace']) { min-width: 0; }
:deep(.workspace .parts-container),
:deep(.workspace .materials-container),
:deep(.workspace .packaging-container),
:deep(.workspace .tooling-container),
:deep(.workspace .production-container),
:deep(.workspace .quotes-container) { padding: 18px 0 0; color: var(--zephyr-ink); }

:deep(.workspace .list-view-toolbar) {
  display: grid;
  grid-template-columns: minmax(150px, .65fr) minmax(260px, 1.55fr) auto;
  align-items: center;
  gap: 10px;
  min-height: 58px;
  margin-bottom: 8px;
  padding: 7px 0;
}
:deep(.workspace .list-title-block) { min-width: 0; gap: 9px; }
:deep(.workspace .list-title-block h1) { color: var(--zephyr-ink); font-size: 19px; font-weight: 650; letter-spacing: -.015em; }
:deep(.workspace .list-caption) { color: var(--zephyr-muted); font-size: 11px; }
:deep(.workspace .search-control) {
  width: min(560px, 100%);
  height: var(--zephyr-control);
  padding: 0 9px;
  border: 1px solid var(--zephyr-border);
  border-radius: 4px;
  background: var(--zephyr-surface);
  color: #839197;
}
:deep(.workspace .search-control:focus-within) { border-color: var(--zephyr-primary); box-shadow: 0 0 0 3px rgba(23, 107, 90, .12); }
:deep(.workspace .search-control .el-input__wrapper) { box-shadow: none; padding: 0; }
:deep(.workspace .filter-controls) { gap: 6px; }
:deep(.workspace .filter-controls .el-input),
:deep(.workspace .filter-controls .el-select),
:deep(.workspace .filter-controls .el-date-editor) { min-width: 112px; height: var(--zephyr-control); }
:deep(.workspace .filter-controls .el-input__wrapper),
:deep(.workspace .filter-controls .el-select__wrapper) { min-height: var(--zephyr-control); box-shadow: none; border-color: var(--zephyr-border); }
:deep(.workspace .table-meta),
:deep(.workspace .record-summary) { margin: 0 2px 7px; color: var(--zephyr-muted); font-size: 11px; }
:deep(.workspace .table-meta span:last-child),
:deep(.workspace .record-summary span:last-child) { color: #8a989d; }

:deep(.workspace .el-table) {
  --el-table-header-bg-color: #edf2f1;
  --el-table-row-hover-bg-color: #f0f7f4;
  --el-table-border-color: var(--zephyr-border);
  --el-table-text-color: #44545a;
  --el-table-header-text-color: #617178;
  border: 1px solid var(--zephyr-border);
  border-radius: 5px;
  overflow: hidden;
  font-size: 12px;
}
:deep(.workspace .el-table th.el-table__cell) { height: 38px; padding: 0 9px; font-size: 10px; font-weight: 700; letter-spacing: .035em; }
:deep(.workspace .el-table td.el-table__cell) { height: var(--zephyr-row); padding: 0 9px; border-bottom-color: #e7edeb; }
:deep(.workspace .el-table .cell) { line-height: 1.35; }
:deep(.workspace .el-table tbody tr) { cursor: pointer; transition: background-color 160ms ease; }
:deep(.workspace .el-table tbody tr:hover > td.el-table__cell) { background: #f0f7f4 !important; }
:deep(.workspace .el-table .el-tag) { border-radius: 3px; font-size: 10px; }
:deep(.workspace .pagination),
:deep(.workspace .pagination-container) { min-height: 38px; margin-top: 10px; align-items: center; }
:deep(.workspace .el-pagination) { padding: 0; font-size: 11px; }
:deep(.workspace .el-button--primary) { --el-button-bg-color: var(--zephyr-primary); --el-button-border-color: var(--zephyr-primary); --el-button-hover-bg-color: #12594b; --el-button-hover-border-color: #12594b; }
:deep(.workspace .el-button.is-link) { font-size: 11px; }

/* Dossier/editor surfaces: keep the record central and the change trail visible. */
:deep(.workspace .part-editor-drawer .el-drawer__header) { margin-bottom: 0; padding: 15px 20px; border-bottom: 1px solid var(--zephyr-border); }
:deep(.workspace .part-editor-drawer .el-drawer__body) { padding: 0 20px 20px; background: #f6f8f7; }
:deep(.workspace .dossier-layout) { display: grid; grid-template-columns: minmax(0, 1fr) 260px; gap: 14px; }
:deep(.workspace .dossier-tabs) { min-width: 0; padding: 14px 16px; border: 1px solid var(--zephyr-border); background: var(--zephyr-surface); }
:deep(.workspace .change-history-rail) { align-self: start; padding: 15px; border: 1px solid var(--zephyr-border); background: #f8fbfa; }
:deep(.workspace .change-history-rail h3) { margin: 0 0 12px; color: var(--zephyr-ink); font-size: 13px; }

/* Manufacturing control console defaults. */
:deep(.workspace .production-container) { padding-top: 13px; }
:deep(.workspace .production-container .list-view-toolbar) { grid-template-columns: minmax(180px, .75fr) minmax(260px, 1.3fr) auto; }
:deep(.workspace .production-container .el-table td.el-table__cell) { height: 42px; }
:deep(.workspace .production-container .el-progress) { width: 100%; }
:deep(.workspace .page-header) { display: flex; align-items: flex-end; justify-content: space-between; gap: 20px; margin-bottom: 14px; }
:deep(.workspace .page-header h2) { margin: 0; color: #3d3b42; font-size: 20px; font-weight: 600; line-height: 1.25; }
:deep(.workspace .filter-card) { margin-bottom: 10px; border: 1px solid #dfe0e4; border-radius: 3px; box-shadow: none; }
:deep(.workspace .filter-card .el-card__body) { padding: 10px 12px 2px; }
:deep(.workspace .el-table) { --el-table-header-bg-color: #eef1f2; --el-table-header-text-color: #48545c; --el-table-border-color: #d9dee1; --el-table-row-hover-bg-color: #eef6f3; border: 1px solid #d9dee1; border-radius: 4px; overflow: hidden; }
:deep(.workspace .el-table th.el-table__cell) { font-size: 12px; font-weight: 650; }
:deep(.workspace .el-table td.el-table__cell) { border-bottom-color: #e5e5e8; }
:deep(.workspace .pagination) { min-height: 38px; align-items: center; }
:deep(.workspace .el-button--primary) { --el-button-bg-color: #176b5a; --el-button-border-color: #176b5a; --el-button-hover-bg-color: #12594b; --el-button-hover-border-color: #12594b; --el-button-active-bg-color: #0e463c; --el-button-active-border-color: #0e463c; }

@media (max-width: 920px) {
  .app-topbar { padding: 0 16px; }
  .module-nav-item { gap: 4px; padding: 0 8px; font-size: 14px; }
  .module-nav-item .el-icon, .topbar-divider { display: none; }
  .workspace { padding: 0 12px 20px; }
  .secondary-nav { min-height: 52px; margin: 0 -12px 16px; padding: 0 12px; overflow-x: auto; }
  .secondary-title, .workspace-tab { height: 52px; font-size: 15px; }
  :deep(.workspace .list-view-toolbar),
  :deep(.workspace .production-container .list-view-toolbar) { grid-template-columns: 1fr; align-items: stretch; }
  :deep(.workspace .search-control) { width: 100%; }
  :deep(.workspace .filter-controls) { justify-content: flex-start; flex-wrap: wrap; }
  :deep(.workspace .change-history-rail) { order: 2; }
  :deep(.workspace .dossier-layout) { grid-template-columns: 1fr; }
}
@media (max-width: 620px) {
  .module-nav { display: none; }
  .brand-name, .profile-name { display: none; }
  .app-launcher { grid-template-columns: 1fr 1fr; width: calc(100vw - 8px); }
  .topbar-actions { margin-left: 8px; }
  :deep(.workspace .page-header) { align-items: stretch; flex-direction: column; }
  :deep(.workspace .filter-controls .el-input),
  :deep(.workspace .filter-controls .el-select),
  :deep(.workspace .filter-controls .el-date-editor) { width: 100%; }
}
</style>
