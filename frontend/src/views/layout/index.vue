<template>
  <div class="app-shell">
    <header class="app-topbar">
      <div class="topbar-leading">
        <button ref="appSwitcherRef" class="app-switcher" type="button" aria-label="切换模块" title="切换模块" aria-haspopup="menu" aria-controls="application-launcher" :aria-expanded="appMenuOpen" @click="toggleLauncher" @keydown.down.prevent="openLauncher">
          <el-icon><Grid /></el-icon>
        </button>
        <button
          class="brand-lockup"
          type="button"
          :aria-label="'切换公司，当前' + companyLabel"
          :title="'切换至' + nextCompanyLabel"
          @click="toggleCompany"
        >
          <span class="brand-mark">Z</span>
          <span class="brand-name">{{ companyLabel }}</span>
          <el-icon class="company-switch-icon"><ArrowDown /></el-icon>
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
              :aria-controls="item.tabs.length ? 'module-submenu' : undefined"
              @click="handlePrimaryClick(item, $event)"
              @keydown.down.prevent="openPrimaryMenu(item, $event)"
            >
              <el-icon><component :is="item.icon" /></el-icon>
              <span>{{ item.label }}</span>
            </button>
          </div>
        </nav>
      </div>

      <div v-if="openMenuArea" id="module-submenu" ref="submenuRef" class="module-nav-submenu" role="menu" :aria-label="`${openMenuArea.label}子菜单`" :style="submenuStyle" @keydown="handleMenuKeydown">
        <button v-for="tab in openMenuArea.tabs" :key="tab.label" type="button" role="menuitem" :aria-current="tab.route && isRouteActive(tab.route) ? 'page' : undefined" :disabled="tab.disabled || !tab.route" @click="tab.route && go(tab.route)">
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
              <el-dropdown-item disabled>管理员模式 · LV4 全视角</el-dropdown-item>
              <el-dropdown-item command="technical-review">技术视角审核</el-dropdown-item>
              <el-dropdown-item command="admin-context">切换其他部门视角</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </header>


    <div v-if="appMenuOpen" id="application-launcher" ref="launcherRef" class="app-launcher" role="menu" aria-label="模块切换菜单" @keydown="handleMenuKeydown">
      <template v-for="item in primaryNav" :key="item.key">
        <button class="launcher-item" type="button" role="menuitem" :aria-current="activeArea === item.key ? 'page' : undefined" :disabled="item.disabled || (!item.route && !item.tabs.some(tab => tab.route && !tab.disabled))" @click="goToArea(item)">
          <span class="launcher-icon"><el-icon><component :is="item.icon" /></el-icon></span>
          <span>{{ item.label }}</span>
        </button>
        <div v-if="item.tabs.length" class="launcher-subitems" :aria-label="`${item.label}子入口`">
          <button v-for="tab in item.tabs" :key="tab.label" class="launcher-subitem" type="button" role="menuitem" :aria-current="tab.route && isRouteActive(tab.route) ? 'page' : undefined" :disabled="tab.disabled || !tab.route" @click="tab.route && go(tab.route)">{{ tab.label }}</button>
        </div>
      </template>
    </div>

    <main id="workspace" class="workspace">
      <nav v-if="currentArea.tabs.length" class="secondary-nav" role="navigation" :aria-label="`${currentArea.label}页面`">
        <span class="secondary-title">{{ currentArea.label }}</span>
        <button
          v-for="tab in currentArea.tabs"
          :key="tab.route || tab.label"
          class="workspace-tab"
          :class="{ active: tab.route && isRouteActive(tab.route), disabled: tab.disabled }"
          type="button"
          :disabled="tab.disabled"
          :aria-current="tab.route && isRouteActive(tab.route) ? 'page' : undefined"
          @click="tab.route && go(tab.route)"
        >{{ tab.label }}</button>
      </nav>
      <p v-if="route.path !== '/parts'" class="mobile-table-hint">表格可左右滑动，查看全部字段。</p>
      <router-view />
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch, type Component } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowDown, Box, Briefcase, Document, Grid, House, Setting, Tools, Warning } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import { useCompanyStore, type CompanyKey } from '@/stores/company'

type AreaKey = 'workbench' | 'productEngineering' | 'projectManagement' | 'manufacturing' | 'procurement' | 'warehouseProcessing' | 'nonconforming' | 'pricing' | 'permissions'

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
const companyStore = useCompanyStore()
const appMenuOpen = ref(false)
const appSwitcherRef = ref<HTMLButtonElement | null>(null)
const launcherRef = ref<HTMLElement | null>(null)
const openMenuKey = ref<AreaKey | null>(null)
const submenuPosition = ref({ left: 0 })
const submenuRef = ref<HTMLElement | null>(null)
let activeMenuTrigger: HTMLElement | null = null

const closeMenus = (restoreFocus = false) => {
  const trigger = appMenuOpen.value ? appSwitcherRef.value : activeMenuTrigger
  appMenuOpen.value = false
  openMenuKey.value = null
  if (restoreFocus) trigger?.focus()
}
const focusFirstMenuItem = (menu: HTMLElement | null) => {
  menu?.querySelector<HTMLButtonElement>('[role="menuitem"]:not(:disabled)')?.focus()
}
const openLauncher = async () => {
  openMenuKey.value = null
  appMenuOpen.value = true
  await nextTick()
  focusFirstMenuItem(launcherRef.value)
}
const toggleLauncher = () => {
  if (appMenuOpen.value) closeMenus(true)
  else void openLauncher()
}
const handleMenuKeydown = (event: KeyboardEvent) => {
  if (!['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) return
  const menu = event.currentTarget as HTMLElement
  const items = Array.from(menu.querySelectorAll<HTMLButtonElement>('[role="menuitem"]:not(:disabled)'))
  if (!items.length) return
  event.preventDefault()
  const current = items.indexOf(document.activeElement as HTMLButtonElement)
  const index = event.key === 'Home' ? 0 : event.key === 'End' ? items.length - 1
    : (current + (event.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length
  items[index]?.focus()
}
const handleOutsideInteraction = (event: Event) => {
  const target = event.target as Node | null
  if (!target) return
  if (appMenuOpen.value && !launcherRef.value?.contains(target) && !appSwitcherRef.value?.contains(target)) closeMenus()
  if (openMenuKey.value && !submenuRef.value?.contains(target) && !activeMenuTrigger?.contains(target)) closeMenus()
}
const handleEscape = (event: KeyboardEvent) => {
  if (event.key === 'Escape' && (appMenuOpen.value || openMenuKey.value)) {
    event.preventDefault()
    closeMenus(true)
  }
}
const handleResize = () => closeMenus()
watch(() => route.path, () => closeMenus())
onMounted(() => {
  document.addEventListener('pointerdown', handleOutsideInteraction)
  document.addEventListener('focusin', handleOutsideInteraction)
  document.addEventListener('keydown', handleEscape)
  window.addEventListener('resize', handleResize)
})
onUnmounted(() => {
  document.removeEventListener('pointerdown', handleOutsideInteraction)
  document.removeEventListener('focusin', handleOutsideInteraction)
  document.removeEventListener('keydown', handleEscape)
  window.removeEventListener('resize', handleResize)
})

const areas: WorkspaceArea[] = [
  {
    key: 'workbench', label: '工作台', route: '/workbench', icon: House, tabs: [],
  },
  {
    key: 'productEngineering', label: '零件', icon: Box,
    tabs: [
      { label: '零件台账', route: '/parts' },
      { label: '模具台账', route: '/tooling' },
      { label: 'PPAP', route: '/ppap' },
    ],
  },
  {
    key: 'projectManagement', label: '项目管理', icon: Briefcase,
    tabs: [
      { label: '项目总览', route: '/projects' },
      { label: '询价', route: '/projects/rfq' },
      { label: '报价', route: '/projects/quotes' },
      { label: '样件', route: '/projects/samples' },
      { label: '图纸变更', route: '/projects/changes' },
      { label: '研发合规', route: '/projects/research-compliance' },
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
      { label: '材料', route: '/materials' },
      { label: '外协', disabled: true },
    ],
  },
  {
    key: 'warehouseProcessing', label: '仓储与后处理', icon: House,
    tabs: [
      { label: '发货订单', route: '/shipping-orders' },
      { label: '仓库', route: '/warehouse' },
      { label: '全检与包装', disabled: true },
      { label: '后处理', disabled: true },
    ],
  },
  {
    key: 'nonconforming', label: '不良品', icon: Warning,
    tabs: [
      { label: '不良品处理', route: '/nonconforming' },
      { label: '返工模', route: '/tooling/rework' },
    ],
  },
  {
    key: 'pricing', label: '价格中心', icon: Document,
    tabs: [
      { label: '客户价格查询', route: '/price-management' },
      { label: '客户档案', route: '/customers' },
    ],
  },
  {
    key: 'permissions', label: '权限分配', icon: Setting, disabled: true,
    tabs: [],
  },
]

const activeArea = computed<AreaKey>(() => {
  const matchedArea = areas.find(area =>
    (area.route && isRouteActive(area.route)) ||
    area.tabs.some(tab => tab.route && isRouteActive(tab.route)),
  )
  return matchedArea?.key || 'productEngineering'
})
const currentArea = computed(() => areas.find(area => area.key === activeArea.value) || areas[0])
const primaryNav = computed(() => areas)
const openMenuArea = computed(() => areas.find(area => area.key === openMenuKey.value) || null)
const submenuStyle = computed(() => ({ left: `${submenuPosition.value.left}px` }))
const userInitial = computed(() => (userStore.userInfo?.real_name || '用').slice(0, 1))
const companyLabel = computed(() => companyStore.selectedCompany === 'gaibo' ? '盖博' : '天越')
const nextCompanyLabel = computed(() => companyStore.selectedCompany === 'gaibo' ? '天越' : '盖博')

const go = (target: string) => {
  closeMenus()
  if (target === '/parts' || (target.startsWith('/tooling') && !target.startsWith('/tooling/rework'))) companyStore.setCompany('tianyue')
  if (target === '/after-sales') companyStore.setCompany('gaibo')
  if (route.path !== target) router.push(target)
}
const goToArea = (item: WorkspaceArea) => {
  const target = item.route || item.tabs.find(tab => tab.route && !tab.disabled)?.route
  if (target) go(target)
}

const handleCompanySwitch = (company: CompanyKey) => {
  companyStore.setCompany(company)
  // Company-scoped quality pages keep the selected module when switching.
  if (activeArea.value === 'nonconforming') return
  if (route.path === '/ppap' || route.path.startsWith('/ppap/')) return
  const target = company === 'gaibo' ? '/after-sales' : '/parts'
  if (route.path !== target) void router.push(target)
}

const toggleCompany = () => {
  handleCompanySwitch(companyStore.selectedCompany === 'gaibo' ? 'tianyue' : 'gaibo')
}

const handlePrimaryClick = (item: WorkspaceArea, event: MouseEvent) => {
  if (item.disabled) return
  if (item.route) {
    go(item.route)
    return
  }
  appMenuOpen.value = false
  openMenuKey.value = openMenuKey.value === item.key ? null : item.key
  if (!openMenuKey.value) return
  const menuTrigger = event.currentTarget as HTMLElement | null
  if (!menuTrigger) return
  activeMenuTrigger = menuTrigger
  void nextTick(() => {
    const rect = menuTrigger.getBoundingClientRect()
    submenuPosition.value.left = Math.min(Math.max(rect.left, 12), window.innerWidth - 190)
  })
}

const openPrimaryMenu = async (item: WorkspaceArea, event: KeyboardEvent) => {
  if (item.disabled || !item.tabs.length) return
  appMenuOpen.value = false
  activeMenuTrigger = event.currentTarget as HTMLElement
  openMenuKey.value = item.key
  const rect = activeMenuTrigger.getBoundingClientRect()
  submenuPosition.value.left = Math.min(Math.max(rect.left, 12), window.innerWidth - 190)
  await nextTick()
  focusFirstMenuItem(submenuRef.value)
}

const isRouteActive = (target: string) => {
  if (target === '/projects') return route.path === target
  // Rework molds belong to quality; other tooling pages belong to parts.
  if (target === '/tooling' && (route.path === '/tooling/rework' || route.path.startsWith('/tooling/rework/'))) return false
  return route.path === target || route.path.startsWith(`${target}/`)
}

const handleCommand = (command: string) => {
  if (command === 'technical-review') {
    router.push('/projects/rfq?review=technical')
    return
  }
  if (command === 'admin-context') {
    router.push('/admin/context-switch')
    return
  }
  if (command === 'logout') {
    userStore.logout()
    router.push('/login')
  }
}
</script>

<style scoped>
.app-shell { display: flex; flex-direction: column; height: 100%; min-height: 100vh; background: var(--zephyr-canvas); color: var(--zephyr-ink); }
.app-topbar { position: relative; z-index: 20; display: flex; align-items: center; justify-content: space-between; flex: 0 0 56px; height: 56px; padding: 0 20px; background: #242b3d; color: #fff; box-shadow: 0 2px 8px rgb(19 27 46 / 10%); }
.topbar-leading, .topbar-actions, .module-nav, .profile-trigger { display: flex; align-items: center; }
.topbar-leading { min-width: 0; height: 56px; flex: 1; }
.app-switcher { display: grid; flex: 0 0 auto; place-items: center; width: 34px; height: 34px; margin-right: 12px; padding: 0; border: 1px solid rgb(255 255 255 / 14%); border-radius: 6px; background: transparent; color: #c8d0e2; cursor: pointer; }
.app-switcher:hover, .app-switcher[aria-expanded='true'] { border-color: rgb(255 255 255 / 28%); background: rgb(255 255 255 / 8%); color: #fff; }
.app-switcher .el-icon { font-size: 17px; }
.app-launcher { position: fixed; z-index: 60; top: 64px; left: 12px; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); align-items: start; gap: 8px; width: min(380px, calc(100vw - 24px)); max-height: calc(100dvh - 80px - env(safe-area-inset-bottom)); overflow-y: auto; overscroll-behavior: contain; padding: 10px; border: 1px solid var(--zephyr-border); border-radius: 9px; background: var(--zephyr-surface); box-shadow: var(--zephyr-shadow-overlay); }
.launcher-item { display: flex; align-items: center; gap: 8px; width: 100%; min-height: 40px; padding: 5px 7px; border: 0; border-radius: 5px; background: transparent; color: var(--zephyr-text); font: inherit; font-size: 13px; text-align: left; cursor: pointer; }
.launcher-icon { display: grid; flex: 0 0 auto; place-items: center; width: 26px; height: 26px; border-radius: 5px; background: var(--zephyr-primary-soft); color: var(--zephyr-primary); }
.launcher-icon .el-icon { font-size: 14px; }
.launcher-subitems { display: grid; grid-column: 1 / -1; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 4px; margin: -4px 0 4px 34px; }
.launcher-subitem { min-height: 34px; padding: 4px 8px; border: 0; border-radius: 4px; background: var(--zephyr-surface-muted); color: var(--zephyr-muted); font: inherit; font-size: 12px; text-align: left; cursor: pointer; }
.launcher-item:hover:not(:disabled), .launcher-subitem:hover:not(:disabled), .app-launcher [aria-current='page'] { background: var(--zephyr-primary-soft); color: var(--zephyr-primary-hover); }
.app-launcher button:disabled { cursor: default; opacity: .45; }
.app-launcher button:focus-visible { outline: 2px solid var(--zephyr-primary); outline-offset: -2px; }
.brand-lockup { display: flex; flex: 0 0 auto; align-items: center; gap: 8px; min-height: 36px; margin-right: 14px; padding: 0; border: 0; border-radius: 5px; background: transparent; color: #fff; font: inherit; cursor: pointer; }
.brand-lockup:hover .brand-name { color: #e2e7ff; }
.brand-mark { display: grid; place-items: center; width: 28px; height: 28px; border: 1px solid #c1c9e0; border-radius: 7px; background: #f4f6ff; color: #46558c; font-size: 17px; font-weight: 750; letter-spacing: -.04em; }
.brand-name { font-size: 14px; font-weight: 600; white-space: nowrap; }
.company-switch-icon { font-size: 10px; color: #9faac2; }
.topbar-divider { flex: 0 0 1px; height: 22px; margin-right: 12px; background: rgb(255 255 255 / 13%); }
.module-nav { flex: 1; height: 56px; gap: 2px; min-width: 0; overflow-x: auto; scrollbar-width: none; }
.module-nav-entry { position: relative; display: flex; flex: 0 0 auto; align-items: center; height: 56px; }
.module-nav-item { position: relative; display: inline-flex; align-items: center; gap: 6px; height: 34px; padding: 0 10px; border: 1px solid transparent; border-radius: 6px; background: transparent; color: #bfc8db; font: inherit; font-size: 13px; font-weight: 500; white-space: nowrap; cursor: pointer; }
.module-nav-item:hover { background: rgb(255 255 255 / 6%); color: #fff; }
.module-nav-item.active { border-color: #6575a5; background: #3d4b71; color: #fff; box-shadow: inset 0 1px 0 rgb(255 255 255 / 5%); }
.module-nav-item.active::after { position: absolute; right: 9px; bottom: -12px; left: 9px; height: 2px; border-radius: 2px 2px 0 0; background: #a6b4e8; content: ''; }
.module-nav-item .el-icon { flex: 0 0 auto; font-size: 14px; opacity: .9; }
.module-nav-item:disabled { cursor: default; opacity: .4; }
.module-nav-item:disabled:hover { background: transparent; color: #bfc8db; }
.app-topbar button:focus-visible { outline: 2px solid #b9c5f6; outline-offset: 3px; }
.module-nav-submenu { position: fixed; z-index: 50; top: 62px; display: grid; min-width: 182px; padding: 5px; border: 1px solid var(--zephyr-border); border-radius: 9px; background: var(--zephyr-surface); box-shadow: var(--zephyr-shadow-overlay); }
.module-nav-submenu button { min-height: 34px; padding: 0 12px; border: 0; border-radius: 5px; background: transparent; color: var(--zephyr-text); font: inherit; font-size: 13px; text-align: left; cursor: pointer; }
.module-nav-submenu button:hover:not(:disabled) { background: var(--zephyr-primary-soft); color: var(--zephyr-primary); }
.module-nav-submenu button:disabled { cursor: default; opacity: .45; }
.module-nav-submenu button[aria-current='page'] { background: var(--zephyr-primary-soft); color: var(--zephyr-primary); font-weight: 600; }
.topbar-actions { flex: 0 0 auto; gap: 6px; margin-left: 14px; }
.topbar-icon { color: #fff; }
.profile-trigger { gap: 8px; min-height: 34px; padding: 0 7px; border: 1px solid rgb(255 255 255 / 10%); border-radius: 6px; background: rgb(255 255 255 / 3%); color: #e3e8f2; font: inherit; cursor: pointer; }
.profile-trigger:hover { border-color: rgb(255 255 255 / 22%); background: rgb(255 255 255 / 8%); }
.profile-trigger .el-icon { color: #9faac2; font-size: 10px; }
.avatar { display: grid; place-items: center; width: 23px; height: 23px; border-radius: 50%; background: #45516d; color: #e6ecff; font-size: 11px; font-weight: 600; }
.profile-name { font-size: 12px; white-space: nowrap; }
.mobile-table-hint { display: none; }
.workspace { display: flex; flex: 1 1 auto; flex-direction: column; min-width: 0; min-height: 0; padding: 0 20px 20px; overflow: auto; }
.secondary-nav { display: flex; flex: 0 0 auto; align-items: center; gap: 4px; min-height: 46px; margin: 0 -20px 2px; padding: 0 20px; border-bottom: 1px solid var(--zephyr-border); background: #fff; }
.secondary-title { flex: 0 0 auto; margin-right: 14px; padding-right: 18px; border-right: 1px solid var(--zephyr-border); color: var(--zephyr-ink); font-size: 13px; font-weight: 650; }
.workspace-tab { position: relative; flex: 0 0 auto; height: 46px; padding: 0 12px; border: 0; border-bottom: 2px solid transparent; background: transparent; color: var(--zephyr-muted); font: inherit; font-size: 13px; cursor: pointer; }
.workspace-tab:hover { background: #f8f9fc; color: var(--zephyr-primary); }
.workspace-tab.active { border-bottom-color: var(--zephyr-primary); color: var(--zephyr-primary); font-weight: 650; }
.workspace-tab:focus-visible { outline: 2px solid var(--zephyr-primary); outline-offset: -4px; }
.workspace-tab:disabled { cursor: default; opacity: .45; }
.workspace-tab:disabled:hover { background: transparent; color: var(--zephyr-muted); }
:deep(.workspace > .after-sales-page) { flex: 1 1 auto; min-height: 0; }
:deep(.workspace > [class$='-container']), :deep(.workspace > [class$='-workspace']) { min-width: 0; }
@media (max-width: 1100px) {
  .app-topbar { padding: 0 14px; }
  .module-nav-item { gap: 5px; padding: 0 8px; font-size: 12px; }
  .module-nav-item .el-icon { display: none; }
  .topbar-actions { margin-left: 8px; }
  .workspace { padding: 0 14px 18px; }
  .secondary-nav { margin-right: -14px; margin-left: -14px; padding: 0 14px; overflow-x: auto; }
}
@media (max-width: 767px) {
  .app-shell { height: 100dvh; min-height: 100dvh; }
  .app-topbar { position: sticky; top: 0; padding: 0 12px; }
  .brand-lockup { margin-right: 0; }
  .app-switcher { width: 44px; height: 44px; margin-right: 10px; }
  .launcher-item, .launcher-subitem { min-height: 44px; }
  .profile-trigger { min-width: 44px; min-height: 44px; }
  .topbar-divider { display: none; }
  .module-nav { display: none; }
  .profile-name { display: none; }
  .workspace { padding: 0 12px calc(16px + env(safe-area-inset-bottom)); overscroll-behavior-y: contain; }
  .mobile-table-hint { display: block; margin: 12px 0 0; color: var(--zephyr-muted); font-size: 12px; }
  .secondary-nav { margin: 0 -12px 4px; padding: 0 12px; }
  .topbar-leading { flex: 1; }
  .secondary-title { margin-right: 4px; padding-right: 10px; }
  .workspace-tab { min-height: 44px; padding: 0 10px; font-size: 13px; }
}
</style>
