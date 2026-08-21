import { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router'
import { useUserStore } from '@/stores/user'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/login/index.vue'),
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
  const token = localStorage.getItem('token')

  // Login check
  if (!token && to.path !== '/login' && !to.meta.public) {
    next('/login')
    return
  }

  if (to.path === '/login') {
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
