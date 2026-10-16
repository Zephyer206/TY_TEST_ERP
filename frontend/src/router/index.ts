import { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router'
import { AUTH_DISABLED, useUserStore } from '@/stores/user'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    redirect: '/parts',
  },
  {
    path: '/design-preview',
    name: 'DesignPreview',
    component: () => import('@/views/design-preview/index.vue'),
    meta: { public: true },
  },
  {
    path: '/',
    component: () => import('@/views/layout/index.vue'),
    redirect: '/parts',
    children: [
      {
        path: 'parts',
        name: 'Parts',
        component: () => import('@/views/parts/index.vue'),
        meta: { roleLevel: 2 }, // LV2: technical staff manage parts
      },
      {
        path: 'tooling',
        name: 'Tooling',
        component: () => import('@/views/tooling/index.vue'),
        meta: { roleLevel: 2 }, // LV2: technical staff manage tooling
      },
      {
        path: 'tooling/detail/:id',
        name: 'ToolingDetail',
        component: () => import('@/views/tooling/detail.vue'),
        meta: { roleLevel: 2 }, // LV2: technical staff
      },
      {
        path: 'tooling/maintenance/:id',
        name: 'ToolingMaintenance',
        component: () => import('@/views/tooling/maintenance.vue'),
        meta: { roleLevel: 1 }, // LV1: maintenance workers record work
      },
      {
        path: 'projects',
        name: 'Projects',
        component: () => import('@/views/projects/index.vue'),
      },
      {
        path: 'projects/rfq',
        name: 'ProjectRfqs',
        component: () => import('@/views/projects/rfq.vue'),
      },
      {
        path: 'projects/quotes',
        name: 'ProjectQuoteGroups',
        component: () => import('@/views/projects/quotes.vue'),
      },
      {
        path: 'projects/samples',
        name: 'ProjectSamples',
        component: () => import('@/views/projects/samples.vue'),
      },
      {
        path: 'projects/changes',
        name: 'ProjectChanges',
        component: () => import('@/views/projects/changes.vue'),
      },
      {
        path: 'projects/research-compliance',
        name: 'ResearchCompliance',
        component: () => import('@/views/projects/research-compliance.vue'),
      },
      {
        path: 'materials',
        name: 'Materials',
        component: () => import('@/views/materials/index.vue'),
        meta: { roleLevel: 2 },
      },
      {
        path: 'admin/context-switch',
        name: 'AdminContextSwitch',
        component: () => import('@/views/admin/context-switch.vue'),
        meta: { roleLevel: 4 },
      },
      {
        path: 'production',
        name: 'ProductionPlanning',
        component: () => import('@/views/production/index.vue'),
        meta: { roleLevel: 2 },
      },
      {
        path: 'production/scheduling',
        name: 'ProductionScheduling',
        component: () => import('@/views/production/scheduling.vue'),
        meta: { roleLevel: 2 },
      },
      {
        path: 'after-sales',
        name: 'AfterSalesArchive',
        component: () => import('@/views/after-sales/index.vue'),
        meta: { roleLevel: 1 },
      },
      {
        path: 'after-sales/kits',
        name: 'AfterSalesInstallationKits',
        // The former FMG-only page is intentionally retired. Keep the route
        // as a bookmark-safe redirect while all customers share one archive.
        redirect: '/after-sales',
        meta: { roleLevel: 1 },
      },
      {
        path: 'shipping-orders',
        name: 'ShippingOrders',
        component: () => import('@/views/shipping-orders/index.vue'),
        meta: { roleLevel: 1 },
      },
      {
        path: 'shipping-orders/:id',
        name: 'ShippingOrderDetail',
        component: () => import('@/views/shipping-orders/detail.vue'),
        meta: { roleLevel: 1 },
      },
      {
        path: 'warehouse',
        name: 'WarehouseInventory',
        component: () => import('@/views/warehouse/index.vue'),
        meta: { roleLevel: 1 },
      },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/parts',
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// Routes that should be blocked when admin is in context-switched mode
router.beforeEach(async (to, _from, next) => {
  if (to.path === '/login') {
    next('/parts')
    return
  }

  // Temporary acceptance mode bypasses route-level role checks.
  if (AUTH_DISABLED) {
    next()
    return
  }

  // Role level check for route access (canonical LV1-LV4)
  const requiredLevel = to.meta.roleLevel as number | undefined
  if (requiredLevel !== undefined) {
    const userStore = useUserStore()
    const userRoleLevel = userStore.userInfo?.role_level ?? 0 // Default to 0 (no access) if unauthenticated

    if (userRoleLevel < requiredLevel) {
      console.warn(`Access denied: Route requires role level ${requiredLevel}, user has ${userRoleLevel}`)
      next('/parts')
      return
    }
  }

  next()
})

export default router
